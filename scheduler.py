import random
import time
import datetime
import logging

from config import SUPPORT_MESSAGES
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
    logger.info("🕒 Планировщик запущен.")

    while True:
        try:
            now = datetime.datetime.now()
            current_time_str = now.strftime("%H:%M")
            current_weekday = now.weekday()  # 0=Пн, 6=Вс

            users_reminders = db.get_users_with_reminders()
            for user_id, remind_time in users_reminders:
                if remind_time == current_time_str:
                    try:
                        vk_api.messages.send(
                            user_id=user_id,
                            message="⏰ Пора тренироваться! Не забывай о своих целях!",
                            random_id=int(time.time()) % (2 ** 31)
                        )
                        logger.info(f"Напоминание отправлено user {user_id}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания user {user_id}: {e}")

            inactive_users = db.get_inactive_users_for_support(min_days=3, max_days=4)
            for user_id in inactive_users:
                try:
                    msg = random.choice(SUPPORT_MESSAGES)
                    vk_api.messages.send(
                        user_id=user_id,
                        message=msg,
                        random_id=int(time.time()) % (2 ** 31)
                    )
                    logger.info(f"Поддерживающее сообщение отправлено неактивному user {user_id}")
                    time.sleep(1)  
                except Exception as e:
                    logger.error(f"Ошибка отправки поддержки user {user_id}: {e}")

            if current_weekday == 6 and current_time_str == "20:00":
                vk_api.users.get(user_ids=1)
                db.cursor.execute('SELECT user_id FROM users')
                all_users = db.cursor.fetchall()

                for (user_id,) in all_users:
                    try:
                        summary = db.get_weekly_summary(user_id)

                        if summary['total_workouts'] == 0:
                            msg = (
                                "📅 Неделя позади!\n\n"
                                "Кажется, эта неделя была спокойной. "
                                "Не расстраивайся, каждая новая тренировка — это шаг к цели! "
                                "Начни с малого уже сегодня. 💪"
                            )
                        else:
                            msg = (
                                "📊 Твой недельный отчет:\n\n"
                                f"🏋️ Тренировок: {summary['total_workouts']}\n"
                                f"🔥 Повторений: {summary['total_reps']}\n"
                                f"✨ Заработано XP: {summary['total_xp']}\n"
                                f"📅 Активных дней: {summary['active_days']}\n"
                                f"🏆 Лучшее упражнение: {summary['best_exercise']}\n\n"
                                "Так держать! Продолжай в том же духе на следующей неделе! 🚀"
                            )

                        vk_api.messages.send(
                            user_id=user_id,
                            message=msg,
                            random_id=int(time.time()) % (2 ** 31)
                        )
                        logger.info(f"Недельный отчет отправлен user {user_id}")

                        time.sleep(1)

                    except Exception as e:
                        logger.error(f"Ошибка отправки отчета user {user_id}: {e}")

            time.sleep(55)

        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            time.sleep(60)