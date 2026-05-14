import time
import datetime
import logging
from database import db

logger = logging.getLogger(__name__)


def run_scheduler(vk_api):
    """
    Фоновый поток для отправки ежедневных напоминаний о тренировках.

    Функция работает в бесконечном цикле, проверяя текущее время сервера
    каждую минуту. Если время совпадает с настроенным пользователем в БД,
    отправляется мотивационное сообщение через VK API.

    Args:
        vk_api: Экземпляр VK API, используемый для отправки сообщений.
    """
    logger.info("🕒 Планировщик напоминаний запущен.")

    while True:
        try:
            # Получаем текущее время в формате ЧЧ:ММ
            now = datetime.datetime.now().strftime("%H:%M")

            # Получаем список всех пользователей с активными напоминаниями
            users = db.get_users_with_reminders()

            for user_id, remind_time in users:
                # Если текущее время совпадает с установленным пользователем
                if remind_time == now:
                    try:
                        vk_api.messages.send(
                            user_id=user_id,
                            message="⏰ Пора тренироваться! Не забывай о своих целях!",
                            random_id=int(time.time()) % (2 ** 31)
                        )
                        logger.info(f"✅ Напоминание отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")

            # Пауза 55 секунд. Цикл выполняется ~1 раз в минуту,
            # что предотвращает двойную отправку в одну минуту и даёт запас
            # на время выполнения запросов к БД и API.
            time.sleep(55)

        except Exception as e:
            # При любой непредвиденной ошибке цикл не падает, а ждёт минуту и повторяется
            logger.error(f"❌ Критическая ошибка в планировщике: {e}")
            time.sleep(60)