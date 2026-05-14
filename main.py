import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import logging
import os
import threading
from dotenv import load_dotenv
from database import db
from handler import BotHandler
from scheduler import run_scheduler

# Настройка базового логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """
    Точка входа в приложение.

    Инициализирует переменные окружения, подключается к VK API,
    запускает фоновый поток планировщика напоминаний и входит
    в основной цикл обработки событий Long Poll.
    """
    # Загрузка переменных из .env файла
    load_dotenv()
    VK_TOKEN = os.getenv("VK_TOKEN")
    GROUP_ID = int(os.getenv("GROUP_ID"))

    # Проверка наличия необходимых конфигурационных данных
    if not VK_TOKEN or not GROUP_ID:
        logger.error("❌ Не заданы VK_TOKEN или GROUP_ID в файле .env")
        return

    try:
        # Инициализация сессии VK API и объекта Long Poll
        vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.131')
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    except Exception as e:
        logger.error(f"Ошибка инициализации VK API: {e}")
        return

    # Запуск планировщика напоминаний в отдельном потоке (daemon=True для автозавершения при выходе)
    scheduler_thread = threading.Thread(target=run_scheduler, args=(vk,), daemon=True)
    scheduler_thread.start()

    logger.info("🤖 Бот запущен и слушает сообщения...")

    # Инициализация обработчика сообщений
    handler = BotHandler(vk)

    # Основной бесконечный цикл прослушивания событий от ВКонтакте
    for event in longpoll.listen():
        # Обработка только новых сообщений
        if event.type == VkBotEventType.MESSAGE_NEW and event.object.message:
            msg = event.object.message
            user_id = msg['from_id']
            text = msg.get('text', '')

            # Попытка получить имя и фамилию пользователя через API
            try:
                user_info = vk.users.get(user_ids=user_id, fields='first_name,last_name,screen_name')[0]
                username = user_info.get('screen_name', '')
                first_name = user_info.get('first_name', '')
                last_name = user_info.get('last_name', '')
            except Exception:
                # В случае ошибки API используем пустые значения
                username = first_name = last_name = ''

            # Передача управления сообщением в основной обработчик
            handler.process_message(user_id, text, username, first_name, last_name)


if __name__ == "__main__":
    main()