import sqlite3
import datetime
from config import EXERCISES_CONFIG

class Database:
    """
    Класс для управления взаимодействием с базой данных SQLite.
    Отвечает за создание таблиц, CRUD-операции пользователей,
    запись тренировок, управление опытом (XP) и получение статистики.
    """

    def __init__(self, db_path='fitness_tracker.db'):
        """
        Инициализация подключения к базе данных.

        Args:
            db_path (str): Путь к файлу базы данных SQLite.
        """
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")  # Включаем WAL для лучшей конкурентности
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """
        Создает необходимые таблицы в БД, если они еще не существуют.
        Таблицы: users, purchased_types, workouts.
        """
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
        """
        Регистрирует нового пользователя в системе.
        Если пользователь уже существует, действие игнорируется.
        Автоматически добавляет базовые (бесплатные) стили упражнений.

        Args:
            user_id (int): ID пользователя ВКонтакте.
            username (str): Имя пользователя (screen_name).
            first_name (str): Имя.
            last_name (str): Фамилия.
        """
        self.cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        if self.cursor.fetchone():
            return

        self.cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, registered_at, total_experience)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (user_id, username, first_name, last_name, datetime.datetime.now().isoformat()))

        # Добавляем базовые типы упражнений для нового пользователя
        for exercise, config in EXERCISES_CONFIG.items():
            base_type = config['types'][0]['name']
            self.cursor.execute('''
                INSERT INTO purchased_types (user_id, exercise_name, type_name, purchased_at, total_reps, max_reps, best_single_set)
                VALUES (?, ?, ?, ?, 0, 0, 0)
            ''', (user_id, exercise, base_type, datetime.datetime.now().isoformat()))

        self.conn.commit()

    def user_exists(self, user_id):
        """
        Проверяет наличие пользователя в базе данных.

        Args:
            user_id (int): ID пользователя.

        Returns:
            bool: True если пользователь существует, иначе False.
        """
        self.cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None

    def get_purchased_types(self, user_id, exercise_name):
        """
        Получает список названий стилей упражнения, купленных пользователем.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения (напр. 'подтягивания').

        Returns:
            list[str]: Список названий доступных стилей.
        """
        self.cursor.execute('SELECT type_name FROM purchased_types WHERE user_id = ? AND exercise_name = ?',
                            (user_id, exercise_name))
        return [row[0] for row in self.cursor.fetchall()]

    def get_purchased_types_info(self, user_id, exercise_name):
        """
        Получает подробную информацию о купленных стилях (статистика, множители).

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.

        Returns:
            list[dict]: Список словарей с информацией о каждом стиле.
        """
        purchased = self.get_purchased_types(user_id, exercise_name)
        all_types = EXERCISES_CONFIG[exercise_name]['types']
        result = []
        for type_data in all_types:
            if type_data['name'] in purchased:
                total_reps, max_reps, best_single = self.get_type_stats(user_id, exercise_name, type_data['name'])
                result.append({
                    'name': type_data['name'],
                    'xp_multiplier': type_data['xp_multiplier'],
                    'total_reps': total_reps,
                    'max_reps': max_reps,
                    'description': type_data['description']
                })
        return result

    def get_type_stats(self, user_id, exercise_name, type_name):
        """
        Получает агрегированную статистику по конкретному стилю упражнения.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.
            type_name (str): Название стиля.

        Returns:
            tuple: (total_reps, max_reps, best_single_set).
        """
        self.cursor.execute(
            'SELECT total_reps, max_reps, best_single_set FROM purchased_types WHERE user_id = ? AND exercise_name = ? AND type_name = ?',
            (user_id, exercise_name, type_name))
        return self.cursor.fetchone() or (0, 0, 0)

    def purchase_type(self, user_id, exercise_name, type_name, cost):
        """
        Покупает новый стиль упражнения за XP.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.
            type_name (str): Название покупаемого стиля.
            cost (int): Стоимость в XP.

        Returns:
            tuple: (bool success, str message).
        """
        try:
            # Проверка: уже куплено?
            self.cursor.execute(
                'SELECT 1 FROM purchased_types WHERE user_id = ? AND exercise_name = ? AND type_name = ?',
                (user_id, exercise_name, type_name))
            if self.cursor.fetchone():
                return False, f"❌ Стиль '{type_name}' уже куплен!"

            # Проверка баланса
            self.cursor.execute('SELECT total_experience FROM users WHERE user_id = ?', (user_id,))
            result = self.cursor.fetchone()
            if not result:
                return False, "❌ Пользователь не найден!"

            current_xp = result[0]
            if current_xp < cost:
                return False, f"❌ Недостаточно опыта! Нужно {cost} XP, у вас {current_xp} XP"

            # Покупка
            self.cursor.execute('''
                INSERT INTO purchased_types (user_id, exercise_name, type_name, purchased_at, total_reps, max_reps, best_single_set) 
                VALUES (?, ?, ?, ?, 0, 0, 0)
            ''', (user_id, exercise_name, type_name, datetime.datetime.now().isoformat()))

            # Списание XP
            self.cursor.execute('UPDATE users SET total_experience = total_experience - ? WHERE user_id = ?',
                                (cost, user_id))
            self.conn.commit()

            self.cursor.execute('SELECT total_experience FROM users WHERE user_id = ?', (user_id,))
            new_xp = self.cursor.fetchone()[0]
            return True, f"✅ Стиль '{type_name}' куплен! Потрачено {cost} XP\n💰 Осталось опыта: {new_xp} XP"

        except Exception as e:
            return False, f"❌ Ошибка при покупке: {str(e)}"

    def add_workout(self, user_id, exercise_name, type_name, reps):
        """
        Записывает выполненную тренировку, начисляет XP и обновляет статистику.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.
            type_name (str): Выполненный стиль.
            reps (int): Количество повторений.

        Returns:
            dict | None: Словарь с результатами (XP, рекорды, доступные покупки) или None при ошибке.
        """
        exercise_config = EXERCISES_CONFIG[exercise_name]
        type_data = next((t for t in exercise_config['types'] if t['name'] == type_name), None)
        if not type_data:
            return None

        # Расчет XP
        xp_earned = int(exercise_config['base_xp'] * type_data['xp_multiplier'] * reps)

        # Получение текущей статистики
        current_total, current_max, current_best = self.get_type_stats(user_id, exercise_name, type_name)
        new_total = current_total + reps
        new_max = max(current_max, reps)
        is_record = reps > current_max

        # Запись тренировки
        self.cursor.execute(
            'INSERT INTO workouts (user_id, exercise_name, type_name, reps, xp_earned, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, exercise_name, type_name, reps, xp_earned, datetime.datetime.now().isoformat())
        )

        # Обновление статистики стиля
        self.cursor.execute(
            'UPDATE purchased_types SET total_reps = ?, max_reps = ?, best_single_set = ? WHERE user_id = ? AND exercise_name = ? AND type_name = ?',
            (new_total, new_max, new_max, user_id, exercise_name, type_name)
        )

        # Начисление общего XP
        self.cursor.execute('UPDATE users SET total_experience = total_experience + ? WHERE user_id = ?',
                            (xp_earned, user_id))
        self.conn.commit()

        # Проверка доступных покупок
        available_to_buy = []
        current_xp = self.get_total_experience(user_id)
        purchased = self.get_purchased_types(user_id, exercise_name)
        for t in exercise_config['types']:
            if t['name'] not in purchased and t['cost'] > 0 and current_xp >= t['cost']:
                available_to_buy.append({'name': t['name'], 'cost': t['cost']})

        return {
            'xp_earned': xp_earned,
            'total_reps': new_total,
            'max_reps': new_max,
            'best_single_set': new_max,
            'is_record': is_record,
            'record_reps': reps,
            'available_to_buy': available_to_buy
        }

    def get_exercise_stats(self, user_id, exercise_name):
        """
        Формирует детальную статистику по упражнению за день, неделю и месяц.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.

        Returns:
            list[dict]: Список статистики по каждому доступному стилю.
        """
        purchased = self.get_purchased_types(user_id, exercise_name)
        all_types = EXERCISES_CONFIG[exercise_name]['types']
        stats = []

        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

        for i, type_data in enumerate(all_types):
            if type_data['name'] in purchased:
                total_reps, max_reps, best_single = self.get_type_stats(user_id, exercise_name, type_data['name'])

                # Запросы за периоды
                self.cursor.execute(
                    'SELECT COALESCE(SUM(reps), 0) FROM workouts WHERE user_id = ? AND exercise_name = ? AND type_name = ? AND DATE(created_at) = ?',
                    (user_id, exercise_name, type_data['name'], today))
                day_reps = self.cursor.fetchone()[0]

                self.cursor.execute(
                    'SELECT COALESCE(SUM(reps), 0) FROM workouts WHERE user_id = ? AND exercise_name = ? AND type_name = ? AND DATE(created_at) >= ?',
                    (user_id, exercise_name, type_data['name'], week_ago))
                week_reps = self.cursor.fetchone()[0]

                self.cursor.execute(
                    'SELECT COALESCE(SUM(reps), 0) FROM workouts WHERE user_id = ? AND exercise_name = ? AND type_name = ? AND DATE(created_at) >= ?',
                    (user_id, exercise_name, type_data['name'], month_ago))
                month_reps = self.cursor.fetchone()[0]

                # Расчет прогресса до следующего уровня
                next_type = None
                if i + 1 < len(all_types):
                    next_data = all_types[i + 1]
                    if next_data['name'] not in purchased:
                        needed = next_data['required_reps'] - total_reps
                        if needed > 0:
                            next_type = {'name': next_data['name'], 'needed': needed, 'cost': next_data['cost']}

                stats.append({
                    'name': type_data['name'],
                    'level': i + 1,
                    'total_levels': len(all_types),
                    'total_reps': total_reps,
                    'max_reps': max_reps,
                    'best_single': best_single,
                    'day_reps': day_reps,
                    'week_reps': week_reps,
                    'month_reps': month_reps,
                    'xp_multiplier': type_data['xp_multiplier'],
                    'next_type': next_type,
                    'description': type_data['description']
                })
        return stats

    def get_total_experience(self, user_id):
        """
        Получает общее количество опыта пользователя.

        Args:
            user_id (int): ID пользователя.

        Returns:
            int: Количество XP.
        """
        self.cursor.execute('SELECT total_experience FROM users WHERE user_id = ?', (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else 0

    def set_remind_time(self, user_id, remind_time):
        """
        Устанавливает или обновляет время ежедневных напоминаний.

        Args:
            user_id (int): ID пользователя.
            remind_time (str | None): Время в формате ЧЧ:ММ или None для отключения.
        """
        self.cursor.execute('UPDATE users SET remind_time = ? WHERE user_id = ?', (remind_time, user_id))
        self.conn.commit()

    def get_remind_time(self, user_id):
        """
        Получает установленное время напоминаний.

        Args:
            user_id (int): ID пользователя.

        Returns:
            str | None: Время в формате ЧЧ:ММ или None.
        """
        self.cursor.execute('SELECT remind_time FROM users WHERE user_id = ?', (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else None

    def get_users_with_reminders(self):
        """
        Получает список всех пользователей с активными напоминаниями.

        Returns:
            list[tuple]: Список кортежей (user_id, remind_time).
        """
        self.cursor.execute('SELECT user_id, remind_time FROM users WHERE remind_time IS NOT NULL')
        return self.cursor.fetchall()

    def get_global_rating(self):
        """
        Получает топ-10 пользователей по общему опыту.

        Returns:
            list[tuple]: Список (user_id, first_name, total_experience).
        """
        self.cursor.execute(
            'SELECT user_id, first_name, total_experience FROM users ORDER BY total_experience DESC LIMIT 10')
        return self.cursor.fetchall()

    def get_exercise_rating(self, exercise_name):
        """
        Получает топ-10 пользователей по максимальному количеству повторений в конкретном упражнении.

        Args:
            exercise_name (str): Название упражнения.

        Returns:
            list[tuple]: Список (user_id, first_name, type_name, max_reps).
        """
        self.cursor.execute('''
            SELECT u.user_id, u.first_name, p.type_name, p.max_reps 
            FROM purchased_types p 
            JOIN users u ON p.user_id = u.user_id 
            WHERE p.exercise_name = ? AND p.max_reps > 0 
            ORDER BY p.max_reps DESC LIMIT 10
        ''', (exercise_name,))
        return self.cursor.fetchall()

    def get_user_workouts(self, user_id, exercise_name=None, limit=None):
        """
        Получает историю тренировок пользователя для экспорта.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str, optional): Фильтр по названию упражнения.
            limit (int, optional): Ограничение количества записей.

        Returns:
            list[dict]: Список словарей с данными о тренировках.
                Каждая запись содержит: exercise, type, reps, xp, date.
        """
        query = '''
            SELECT w.exercise_name, w.type_name, w.reps, w.xp_earned, w.created_at
            FROM workouts w
            WHERE w.user_id = ?
        '''
        params = [user_id]

        if exercise_name:
            query += ' AND w.exercise_name = ?'
            params.append(exercise_name)

        query += ' ORDER BY w.created_at DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        self.cursor.execute(query, params)
        columns = ['exercise', 'type', 'reps', 'xp', 'date']
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_user_workouts_for_export(self, user_id):
        """
        Получает полную историю тренировок пользователя для экспорта.

        Args:
            user_id (int): ID пользователя.

        Returns:
            list[tuple]: Список кортежей (date, exercise, type, reps, xp).
        """
        self.cursor.execute('''
            SELECT created_at, exercise_name, type_name, reps, xp_earned 
            FROM workouts 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (user_id,))
        return self.cursor.fetchall()

# Глобальный экземпляр БД
db = Database()