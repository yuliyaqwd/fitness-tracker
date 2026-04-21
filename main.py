import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import logging
import os
import threading
from dotenv import load_dotenv

from database import db
from handler import BotHandler
from scheduler import run_scheduler


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    load_dotenv()
    VK_TOKEN = os.getenv("VK_TOKEN")
    GROUP_ID = int(os.getenv("GROUP_ID"))

    if not VK_TOKEN or not GROUP_ID:
        logger.error("❌ Не заданы VK_TOKEN или GROUP_ID в файле .env")
        return

    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.131')
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    except Exception as e:
        logger.error(f"Ошибка инициализации VK API: {e}")
        return

    scheduler_thread = threading.Thread(target=run_scheduler, args=(vk,), daemon=True)
    scheduler_thread.start()
    logger.info("🤖 Бот запущен и слушает сообщения...")

    handler = BotHandler(vk)

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW and event.object.message:
            msg = event.object.message
            user_id = msg['from_id']
            text = msg.get('text', '')
            try:
                user_info = vk.users.get(user_ids=user_id, fields='first_name,last_name,screen_name')[0]
                username = user_info.get('screen_name', '')
                first_name = user_info.get('first_name', '')
                last_name = user_info.get('last_name', '')
            except Exception:
                username = first_name = last_name = ''
            handler.process_message(user_id, text, username, first_name, last_name)


if __name__ == "__main__":
    main()