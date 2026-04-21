import sqlite3
import datetime
from config import EXERCISES_CONFIG

class Database:
    def __init__(self, db_path='fitness_tracker.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TEXT,
                remind_time TEXT,
                total_experience INTEGER DEFAULT 0
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchased_types (
                user_id INTEGER,
                exercise_name TEXT,
                type_name TEXT,
                purchased_at TEXT,
                total_reps INTEGER DEFAULT 0,
                max_reps INTEGER DEFAULT 0,
                best_single_set INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, exercise_name, type_name)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                exercise_name TEXT,
                type_name TEXT,
                reps INTEGER,
                xp_earned INTEGER,
                created_at TEXT
            )
        ''')
        self.conn.commit()

    def register_user(self, user_id, username, first_name, last_name):
        self.cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        if self.cursor.fetchone():
            return
        self.cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, registered_at, total_experience)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (user_id, username, first_name, last_name, datetime.datetime.now().isoformat()))
        for exercise, config in EXERCISES_CONFIG.items():
            base_type = config['types'][0]['name']
            self.cursor.execute('''
                INSERT INTO purchased_types (user_id, exercise_name, type_name, purchased_at, total_reps, max_reps, best_single_set)
                VALUES (?, ?, ?, ?, 0, 0, 0)
            ''', (user_id, exercise, base_type, datetime.datetime.now().isoformat()))
        self.conn.commit()

    def user_exists(self, user_id):
        self.cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None

    def get_purchased_types(self, user_id, exercise_name):
        self.cursor.execute('SELECT type_name FROM purchased_types WHERE user_id = ? AND exercise_name = ?', (user_id, exercise_name))
        return [row[0] for row in self.cursor.fetchall()]

    def get_purchased_types_info(self, user_id, exercise_name):
        purchased = self.get_purchased_types(user_id, exercise_name)
        all_types = EXERCISES_CONFIG[exercise_name]['types']
        result = []
        for type_data in all_types:
            if type_data['name'] in purchased:
                total_reps, max_reps, best_single = self.get_type_stats(user_id, exercise_name, type_data['name'])
                result.append({'name': type_data['name'], 'xp_multiplier': type_data['xp_multiplier'], 'total_reps': total_reps, 'max_reps': max_reps, 'description': type_data['description']})
        return result

    def get_type_stats(self, user_id, exercise_name, type_name):
        self.cursor.execute('SELECT total_reps, max_reps, best_single_set FROM purchased_types WHERE user_id = ? AND exercise_name = ? AND type_name = ?', (user_id, exercise_name, type_name))
        return self.cursor.fetchone() or (0, 0, 0)

    def purchase_type(self, user_id, exercise_name, type_name, cost):
        try:
            self.cursor.execute('SELECT 1 FROM purchased_types WHERE user_id = ? AND exercise_name = ? AND type_name = ?', (user_id, exercise_name, type_name))
            if self.cursor.fetchone(): return False, f"❌ Стиль '{type_name}' уже куплен!"
            self.cursor.execute('SELECT total_experience FROM users WHERE user_id = ?', (user_id,))
            result = self.cursor.fetchone()
            if not result: return False, "❌ Пользователь не найден!"
            current_xp = result[0]
            if current_xp < cost: return False, f"❌ Недостаточно опыта! Нужно {cost} XP, у вас {current_xp} XP"
            self.cursor.execute('''INSERT INTO purchased_types (user_id, exercise_name, type_name, purchased_at, total_reps, max_reps, best_single_set) VALUES (?, ?, ?, ?, 0, 0, 0)''', (user_id, exercise_name, type_name, datetime.datetime.now().isoformat()))
            self.cursor.execute('UPDATE users SET total_experience = total_experience - ? WHERE user_id = ?', (cost, user_id))
            self.conn.commit()
            self.cursor.execute('SELECT total_experience FROM users WHERE user_id = ?', (user_id,))
            new_xp = self.cursor.fetchone()[0]
            return True, f"✅ Стиль '{type_name}' куплен! Потрачено {cost} XP\n💰 Осталось опыта: {new_xp} XP"
        except Exception as e:
            return False, f"❌ Ошибка при покупке: {str(e)}"

    def add_workout(self, user_id, exercise_name, type_name, reps):
        exercise_config = EXERCISES_CONFIG[exercise_name]
        type_data = next((t for t in exercise_config['types'] if t['name'] == type_name), None)
        if not type_data: return None
        xp_earned = int(exercise_config['base_xp'] * type_data['xp_multiplier'] * reps)
        current_total, current_max, current_best = self.get_type_stats(user_id, exercise_name, type_name)
        new_total = current_total + reps
        new_max = max(current_max, reps)
        is_record = reps > current_max
        self.cursor.execute('INSERT INTO workouts (user_id, exercise_name, type_name, reps, xp_earned, created_at) VALUES (?, ?, ?, ?, ?, ?)', (user_id, exercise_name, type_name, reps, xp_earned, datetime.datetime.now().isoformat()))
        self.cursor.execute('UPDATE purchased_types SET total_reps = ?, max_reps = ?, best_single_set = ? WHERE user_id = ? AND exercise_name = ? AND type_name = ?', (new_total, new_max, new_max, user_id, exercise_name, type_name))
        self.cursor.execute('UPDATE users SET total_experience = total_experience + ? WHERE user_id = ?', (xp_earned, user_id))
        self.conn.commit()
        available_to_buy = []
        current_xp = self.get_total_experience(user_id)
        purchased = self.get_purchased_types(user_id, exercise_name)
        for t in exercise_config['types']:
            if t['name'] not in purchased and t['cost'] > 0 and current_xp >= t['cost']:
                available_to_buy.append({'name': t['name'], 'cost': t['cost']})
        return {'xp_earned': xp_earned, 'total_reps': new_total, 'max_reps': new_max, 'best_single_set': new_max, 'is_record': is_record, 'record_reps': reps, 'available_to_buy': available_to_buy}

    def get_exercise_stats(self, user_id, exercise_name):
        purchased = self.get_purchased_types(user_id, exercise_name)
        all_types = EXERCISES_CONFIG[exercise_name]['types']
        stats = []
        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        for i, type_data in enumerate(all_types):
            if type_data['name'] in purchased:
                total_reps, max_reps, best_single = self.get_type_stats(user_id, exercise_name, type_data['name'])
                self.cursor.execute('SELECT COALESCE(SUM(reps), 0) FROM workouts WHERE user_id = ? AND exercise_name = ? AND type_name = ? AND DATE(created_at) = ?', (user_id, exercise_name, type_data['name'], today))
                day_reps = self.cursor.fetchone()[0]
                self.cursor.execute('SELECT COALESCE(SUM(reps), 0) FROM workouts WHERE user_id = ? AND exercise_name = ? AND type_name = ? AND DATE(created_at) >= ?', (user_id, exercise_name, type_data['name'], week_ago))
                week_reps = self.cursor.fetchone()[0]
                self.cursor.execute('SELECT COALESCE(SUM(reps), 0) FROM workouts WHERE user_id = ? AND exercise_name = ? AND type_name = ? AND DATE(created_at) >= ?', (user_id, exercise_name, type_data['name'], month_ago))
                month_reps = self.cursor.fetchone()[0]
                next_type = None
                if i + 1 < len(all_types):
                    next_data = all_types[i + 1]
                    if next_data['name'] not in purchased:
                        needed = next_data['required_reps'] - total_reps
                        if needed > 0: next_type = {'name': next_data['name'], 'needed': needed, 'cost': next_data['cost']}
                stats.append({'name': type_data['name'], 'level': i + 1, 'total_levels': len(all_types), 'total_reps': total_reps, 'max_reps': max_reps, 'best_single': best_single, 'day_reps': day_reps, 'week_reps': week_reps, 'month_reps': month_reps, 'xp_multiplier': type_data['xp_multiplier'], 'next_type': next_type, 'description': type_data['description']})
        return stats

    def get_total_experience(self, user_id):
        self.cursor.execute('SELECT total_experience FROM users WHERE user_id = ?', (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else 0

    def set_remind_time(self, user_id, remind_time):
        self.cursor.execute('UPDATE users SET remind_time = ? WHERE user_id = ?', (remind_time, user_id))
        self.conn.commit()

    def get_remind_time(self, user_id):
        self.cursor.execute('SELECT remind_time FROM users WHERE user_id = ?', (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else None

    def get_users_with_reminders(self):
        self.cursor.execute('SELECT user_id, remind_time FROM users WHERE remind_time IS NOT NULL')
        return self.cursor.fetchall()

    def get_global_rating(self):
        self.cursor.execute('SELECT user_id, first_name, total_experience FROM users ORDER BY total_experience DESC LIMIT 10')
        return self.cursor.fetchall()

    def get_exercise_rating(self, exercise_name):
        self.cursor.execute('''SELECT u.user_id, u.first_name, p.type_name, p.max_reps FROM purchased_types p JOIN users u ON p.user_id = u.user_id WHERE p.exercise_name = ? AND p.max_reps > 0 ORDER BY p.max_reps DESC LIMIT 10''', (exercise_name,))
        return self.cursor.fetchall()

# Экземпляр БД
db = Database()