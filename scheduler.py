import time
import datetime
import random
import logging
from config import SUPPORT_MESSAGES
from database import db

logger = logging.getLogger(__name__)


def run_scheduler(vk_api):
    """
    Фоновый поток для отправки напоминаний с учётом часовых поясов (NFR-09).

    Работает в бесконечном цикле, проверяя время каждую минуту.
    Конвертирует UTC в локальное время каждого пользователя перед сравнением.

    Args:
        vk_api: Экземпляр VK API для отправки сообщений.
    """
    logger.info("🕒 Планировщик запущен (UTC-based).")

    while True:
        try:
            # Текущее время в UTC — эталон для всех расчётов
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            current_time_utc_str = now_utc.strftime("%H:%M")
            current_weekday = now_utc.weekday()  # 0=Пн, 6=Вс

            # --- 1. Ежедневные напоминания с учётом часовых поясов (NFR-09) ---
            # db.get_users_with_reminders() должен возвращать (user_id, remind_time, utc_offset)
            users_reminders = db.get_users_with_reminders()
            for user_id, remind_time, utc_offset in users_reminders:
                try:
                    # Конвертируем UTC в локальное время пользователя
                    user_local_time = (now_utc + datetime.timedelta(hours=utc_offset)).strftime("%H:%M")

                    if user_local_time == remind_time:
                        vk_api.messages.send(
                            user_id=user_id,
                            message="⏰ Пора тренироваться! Не забывай о своих целях!",
                            random_id=int(time.time()) % (2 ** 31)
                        )
                        logger.info(
                            f"Напоминание отправлено user {user_id} (локальное {remind_time}, UTC{utc_offset:+d})")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания user {user_id}: {e}")

            # --- 2. Поддерживающие сообщения при пропусках ≥3 дней (FR-12) ---
            inactive_users = db.get_inactive_users_for_support(min_days=3, max_days=4)
            for user_id in inactive_users:
                try:
                    msg = random.choice(SUPPORT_MESSAGES)
                    vk_api.messages.send(
                        user_id=user_id,
                        message=msg,
                        random_id=int(time.time()) % (2 ** 31)
                    )
                    logger.info(f"Поддержка отправлена неактивному user {user_id}")
                    time.sleep(1)  # Защита от спам-лимитов VK
                except Exception as e:
                    logger.error(f"Ошибка отправки поддержки user {user_id}: {e}")

            # --- 3. Еженедельная сводка (FR-09) — Воскресенье в 20:00 UTC ---
            if current_weekday == 6 and current_time_utc_str == "20:00":
                try:
                    vk_api.users.get(user_ids=1)  # Проверка связи
                    db.cursor.execute('SELECT user_id FROM users')
                    all_users = [row[0] for row in db.cursor.fetchall()]

                    for user_id in all_users:
                        try:
                            summary = db.get_weekly_summary(user_id)
                            if summary['total_workouts'] == 0:
                                msg = "📅 Неделя позади! Кажется, она была спокойной. Не расстраивайся, каждая новая тренировка — это шаг к цели! 💪"
                            else:
                                msg = (f"📊 Твой недельный отчет:\n\n"
                                       f"🏋️ Тренировок: {summary['total_workouts']}\n"
                                       f"🔥 Повторений: {summary['total_reps']}\n"
                                       f"✨ Заработано XP: {summary['total_xp']}\n"
                                       f"📅 Активных дней: {summary['active_days']}\n"
                                       f"🏆 Лучшее упражнение: {summary['best_exercise']}\n\n"
                                       "Так держать! 🚀")

                            vk_api.messages.send(
                                user_id=user_id,
                                message=msg,
                                random_id=int(time.time()) % (2 ** 31)
                            )
                            logger.info(f"Недельный отчет отправлен user {user_id}")
                            time.sleep(1)
                        except Exception as e:
                            logger.error(f"Ошибка отчета user {user_id}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка отправки еженедельных отчетов: {e}")

            # Пауза ~1 минута
            time.sleep(55)

        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            time.sleep(60)