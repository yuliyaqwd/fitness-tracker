import time
import datetime
import random
import logging
import shutil
import os
from config import SUPPORT_MESSAGES
from database import db

logger = logging.getLogger(__name__)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')

def _ensure_backup_dir():
    """Создаёт директорию для бэкапов, если её нет."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def _backup_database():
    """
    Создаёт резервную копию базы данных (NFR-03).
    Возвращает путь к созданному файлу или None при ошибке.
    """
    try:
        _ensure_backup_dir()
        src = 'fitness_tracker.db'
        if not os.path.exists(src):
            logger.warning("Файл БД не найден, пропуск бэкапа")
            return None

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = os.path.join(BACKUP_DIR, f'fitness_tracker_{timestamp}.db')
        shutil.copy2(src, dst)
        logger.info(f"Бэкап БД создан: {dst}")
        return dst
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        return None


def _get_user_local_time(now_utc, utc_offset):
    """
    Конвертирует UTC-время в локальное время пользователя.

    Args:
        now_utc: datetime объект в часовом поясе UTC.
        utc_offset: Смещение часового пояса пользователя (целое число, часы).

    Returns:
        str: Локальное время в формате 'ЧЧ:ММ'.
    """
    try:
        offset = int(utc_offset) if utc_offset is not None else 3
        local_time = now_utc + datetime.timedelta(hours=offset)
        return local_time.strftime("%H:%M")
    except (ValueError, TypeError):
        return (now_utc + datetime.timedelta(hours=3)).strftime("%H:%M")


def run_scheduler(vk_api):
    """
    Фоновый поток для отправки напоминаний, еженедельных отчётов,
    поддерживающих сообщений и резервного копирования.

    Реализует требования:
    - FR-10: Ежедневные напоминания в заданное время
    - FR-09: Еженедельная сводка прогресса (воскресенье, 20:00)
    - FR-12: Поддержка при пропуске тренировок ≥3 дней
    - NFR-09: Учёт часового пояса пользователя
    - NFR-03: Ежедневное резервное копирование БД

    Args:
        vk_api: Экземпляр VK API для отправки сообщений.
    """
    logger.info("🕒 Планировщик запущен (UTC-based, multi-feature).")

    last_backup_date = None
    last_support_check = {}

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            current_time_utc_str = now_utc.strftime("%H:%M")
            current_weekday = now_utc.weekday()  # 0=Пн, 6=Вс
            today_date = now_utc.date()
            try:
                users_reminders = db.get_users_with_reminders()
                for item in users_reminders:
                    if len(item) == 3:
                        user_id, remind_time, utc_offset = item
                    else:
                        user_id, remind_time = item
                        utc_offset = 3

                    user_local_time = _get_user_local_time(now_utc, utc_offset)

                    if user_local_time == remind_time:
                        vk_api.messages.send(
                            user_id=user_id,
                            message="⏰ Пора тренироваться! Не забывай о своих целях!",
                            random_id=int(time.time()) % (2 ** 31)
                        )
                        logger.info(
                            f"Напоминание отправлено user {user_id} "
                            f"(локальное {remind_time}, UTC{int(utc_offset):+d})"
                        )
                        time.sleep(0.5)
            except Exception as e:
                logger.error(f"Ошибка при обработке напоминаний: {e}")

            try:
                current_hour = now_utc.hour
                if current_hour in [0, 6, 12, 18]:
                    inactive_users = db.get_inactive_users_for_support(min_days=3, max_days=4)

                    for user_id in inactive_users:
                        if last_support_check.get(user_id) == today_date:
                            continue

                        try:
                            msg = random.choice(SUPPORT_MESSAGES)
                            vk_api.messages.send(
                                user_id=user_id,
                                message=msg,
                                random_id=int(time.time()) % (2 ** 31)
                            )
                            logger.info(f"Поддержка отправлена неактивному user {user_id}")
                            last_support_check[user_id] = today_date
                            time.sleep(1)
                        except Exception as e:
                            logger.error(f"Ошибка отправки поддержки user {user_id}: {e}")
            except AttributeError:
                pass
            except Exception as e:
                logger.error(f"Ошибка при проверке неактивных пользователей: {e}")

            if current_weekday == 6 and current_time_utc_str == "20:00":
                try:
                    vk_api.users.get(user_ids=1)

                    all_users = []
                    try:
                        db.cursor.execute('SELECT user_id FROM users')
                        all_users = [row[0] for row in db.cursor.fetchall()]
                    except AttributeError:
                        pass

                    for user_id in all_users:
                        try:
                            try:
                                summary = db.get_weekly_summary(user_id)
                                if summary['total_workouts'] == 0:
                                    msg = ("📅 Неделя позади! Кажется, она была спокойной. "
                                           "Не расстраивайся, каждая новая тренировка — это шаг к цели! 💪")
                                else:
                                    msg = (f"📊 Твой недельный отчет:\n\n"
                                           f"🏋️ Тренировок: {summary['total_workouts']}\n"
                                           f"🔥 Повторений: {summary['total_reps']}\n"
                                           f"✨ Заработано XP: {summary['total_xp']}\n"
                                           f"📅 Активных дней: {summary['active_days']}\n"
                                           f"🏆 Лучшее упражнение: {summary['best_exercise']}\n\n"
                                           "Так держать! 🚀")
                            except AttributeError:
                                msg = "📊 Твой недельный отчет готов! Продолжай в том же духе! 💪"

                            vk_api.messages.send(
                                user_id=user_id,
                                message=msg,
                                random_id=int(time.time()) % (2 ** 31)
                            )
                            logger.info(f"Недельный отчет отправлен user {user_id}")
                            time.sleep(1)
                        except Exception as e:
                            logger.error(f"Ошибка отчета user {user_id}: {e}")

                    logger.info("Еженедельные отчеты отправлены.")
                except Exception as e:
                    logger.error(f"Ошибка отправки еженедельных отчетов: {e}")

            try:
                if current_time_utc_str == "03:00" and last_backup_date != today_date:
                    _backup_database()
                    last_backup_date = today_date
            except Exception as e:
                logger.error(f"Ошибка при создании бэкапа: {e}")

            time.sleep(55)

        except KeyboardInterrupt:
            logger.info("🛑 Планировщик остановлен пользователем")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка в планировщике: {e}", exc_info=True)
            time.sleep(60)