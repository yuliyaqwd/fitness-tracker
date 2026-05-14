import pytest
import datetime
from config import EXERCISES_CONFIG

class TestDatabaseCRUD:
    def test_register_user(self, test_db):
        test_db.register_user(1, 'user1', 'Иван', 'Иванов')
        assert test_db.user_exists(1) is True
        # Проверка дублирования
        test_db.register_user(1, 'user1', 'Иван', 'Иванов')
        test_db.cursor.execute('SELECT COUNT(*) FROM users')
        assert test_db.cursor.fetchone()[0] == 1

    def test_user_exists(self, test_db):
        assert test_db.user_exists(999) is False
        test_db.register_user(999, 'test', 'Test', 'Test')
        assert test_db.user_exists(999) is True

    def test_set_and_get_remind_time(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        test_db.set_remind_time(1, '19:30')
        assert test_db.get_remind_time(1) == '19:30'
        test_db.set_remind_time(1, None)
        assert test_db.get_remind_time(1) is None

    def test_get_users_with_reminders(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        test_db.register_user(2, 'u2', 'C', 'D')
        test_db.set_remind_time(1, '08:00')
        users = test_db.get_users_with_reminders()
        assert len(users) == 1
        assert users[0] == (1, '08:00')

class TestWorkoutLogic:
    def test_add_workout_and_xp(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        result = test_db.add_workout(1, 'подтягивания', 'обычные', 10)
        assert result is not None
        assert result['xp_earned'] == 100  # 10 * 10 * 1.0
        assert result['is_record'] is True
        assert test_db.get_total_experience(1) == 100

    def test_workout_record_detection(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        test_db.add_workout(1, 'подтягивания', 'обычные', 10)
        # Вторая тренировка с большим количеством
        res2 = test_db.add_workout(1, 'подтягивания', 'обычные', 15)
        assert res2['is_record'] is True
        assert res2['max_reps'] == 15
        # Третья с меньшим
        res3 = test_db.add_workout(1, 'подтягивания', 'обычные', 12)
        assert res3['is_record'] is False

class TestShopAndPurchase:
    def test_purchase_type_success(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        test_db.cursor.execute('UPDATE users SET total_experience = 50 WHERE user_id = 1')
        test_db.conn.commit()
        success, msg = test_db.purchase_type(1, 'подтягивания', 'австралийские', 30)
        assert success is True
        assert test_db.get_total_experience(1) == 20
        assert 'австралийские' in test_db.get_purchased_types(1, 'подтягивания')

    def test_purchase_type_insufficient_xp(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        success, msg = test_db.purchase_type(1, 'подтягивания', 'австралийские', 30)
        assert success is False
        assert 'Недостаточно опыта' in msg

    def test_purchase_type_already_bought(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        test_db.cursor.execute('UPDATE users SET total_experience = 100 WHERE user_id = 1')
        test_db.conn.commit()
        test_db.purchase_type(1, 'подтягивания', 'австралийские', 30)
        success, msg = test_db.purchase_type(1, 'подтягивания', 'австралийские', 30)
        assert success is False
        assert 'уже куплен' in msg

class TestStatsAndRatings:
    def test_exercise_stats_periods(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        today = datetime.date.today().isoformat()
        test_db.cursor.execute(
            "INSERT INTO workouts (user_id, exercise_name, type_name, reps, xp_earned, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (1, 'подтягивания', 'обычные', 5, 50, f"{today}T12:00:00")
        )
        test_db.conn.commit()
        stats = test_db.get_exercise_stats(1, 'подтягивания')
        assert len(stats) == 1
        assert stats[0]['day_reps'] == 5

    def test_global_rating(self, test_db):
        for i in range(1, 6):
            test_db.register_user(i, f'u{i}', 'N', 'S')
            test_db.cursor.execute('UPDATE users SET total_experience = ? WHERE user_id = ?', (i*100, i))
        test_db.conn.commit()
        rating = test_db.get_global_rating()
        assert len(rating) == 5
        assert rating[0][2] == 500  # Максимальный XP на первом месте

    def test_exercise_rating(self, test_db):
        test_db.register_user(1, 'u1', 'A', 'B')
        test_db.register_user(2, 'u2', 'C', 'D')
        test_db.add_workout(1, 'отжимания', 'классические', 20)
        test_db.add_workout(2, 'отжимания', 'классические', 30)
        rating = test_db.get_exercise_rating('отжимания')
        assert rating[0][3] == 30