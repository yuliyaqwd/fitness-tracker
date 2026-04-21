import time
import datetime
from database import db

def run_scheduler(vk_api):
    while True:
        try:
            now = datetime.datetime.now().strftime("%H:%M")
            users = db.get_users_with_reminders()
            for user_id, remind_time in users:
                if remind_time == now:
                    try:
                        vk_api.messages.send(
                            user_id=user_id,
                            message="⏰ Пора тренироваться! Не забывай о своих целях!",
                            random_id=int(time.time()) % (2**31)
                        )
                    except Exception:
                        pass
            time.sleep(55)
        except Exception:
            time.sleep(60)