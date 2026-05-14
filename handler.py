import os
import random
import logging
import re
import csv
import io
import requests
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from database import db
from keyboards import *
from config import MOTIVATION_MESSAGES, PURCHASE_REMINDER_MESSAGES, MAX_REPS_MAP, EXERCISES_CONFIG

logger = logging.getLogger(__name__)


class BotHandler:
    """
    Основной обработчик сообщений бота.
    Управляет состояниями диалога (FSM), маршрутизацией команд
    и формированием ответов пользователю на основе данных из БД.
    """

    def __init__(self, vk_api):
        """
        Инициализация обработчика.

        Args:
            vk_api: Экземпляр API ВКонтакте.
        """
        self.vk = vk_api
        self.user_states = {}  # Хранилище состояний: {user_id: {'state': str, ...}}

    def get_full_menu_keyboard(self, user_id):
        """
        Генерирует клавиатуру главного меню.

        Args:
            user_id (int): ID пользователя (для проверки статуса напоминаний).

        Returns:
            VkKeyboard: Клавиатура главного меню.
        """
        kb = VkKeyboard(one_time=False)
        kb.add_button('Записать тренировку', color=VkKeyboardColor.PRIMARY);
        kb.add_line()
        kb.add_button('Статистика', color=VkKeyboardColor.PRIMARY);
        kb.add_line()
        kb.add_button('Рейтинг', color=VkKeyboardColor.PRIMARY);
        kb.add_line()
        kb.add_button('Экспорт', color=VkKeyboardColor.PRIMARY);
        kb.add_line()
        kb.add_button('Напоминания', color=VkKeyboardColor.PRIMARY);
        kb.add_line()
        kb.add_button('Часовой пояс', color=VkKeyboardColor.SECONDARY);
        kb.add_line()
        if db.get_remind_time(user_id):
            kb.add_button('Отключить напоминания', color=VkKeyboardColor.NEGATIVE);
            kb.add_line()
        kb.add_button('Помощь', color=VkKeyboardColor.PRIMARY)
        return kb

    def show_full_menu(self, user_id):
        """
        Отправляет пользователю главное меню.

        Args:
            user_id (int): ID пользователя.
        """
        self.send_message(user_id, "Главное меню: ", self.get_full_menu_keyboard(user_id))

    def send_message(self, user_id, text, keyboard=None, attachment=None):
        """
        Отправляет текстовое сообщение пользователю.

        Args:
            user_id (int): ID пользователя.
            text (str): Текст сообщения.
            keyboard (VkKeyboard, optional): Клавиатура.
            attachment (str, optional): Строка вложения (например, 'doc123_456').
        """
        try:
            params = {'user_id': user_id, 'message': text, 'random_id': random.randint(1, 2 ** 31)}
            if keyboard:
                params['keyboard'] = keyboard.get_keyboard()
            if attachment:
                params['attachment'] = attachment
            self.vk.messages.send(**params)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")

    def cancel_action(self, user_id):
        """
        Сбрасывает состояние пользователя и возвращает в главное меню.

        Args:
            user_id (int): ID пользователя.
        """
        if user_id in self.user_states:
            del self.user_states[user_id]
        self.send_message(user_id, "❌ Действие отменено. ", self.get_full_menu_keyboard(user_id))

    def handle_start(self, user_id, username, first_name, last_name):
        """
        Обрабатывает команду /start. Регистрирует новых пользователей или показывает меню.

        Args:
            user_id (int): ID пользователя.
            username (str): Screen name.
            first_name (str): Имя.
            last_name (str): Фамилия.
        """
        if not db.user_exists(user_id):
            db.register_user(user_id, username, first_name, last_name)
            text = (f"👋 Привет, {first_name}!\n\n"
                    f"Добро пожаловать в Fitness Tracker!\n\n"
                    f"🏋️ Я помогу тебе:\n"
                    f"• Отслеживать тренировки\n"
                    f"• Получать XP и открывать новые стили\n"
                    f"• Соревноваться в рейтинге\n\n"
                    f"✨ Нажми 'Начать' чтобы продолжить!")
            self.send_message(user_id, text, get_main_keyboard(user_id))
        else:
            self.show_full_menu(user_id)

    def handle_help(self, user_id):
        """
        Отправляет справочную информацию по командам.

        Args:
            user_id (int): ID пользователя.
        """
        text = ("🤖 Fitness Tracker - Помощь\n\n📌 Команды:\n"
                "/start - Начать\n/stats - Статистика\n/rating - Рейтинги\n"
                "/remind - Напоминания\n/stop_remind - Отключить напоминания\n/help - Справка\n\n"
                "💡 Совет: Покупайте новые стили, чтобы получать больше XP!")
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))

    def handle_stop_remind(self, user_id):
        """
        Отключает ежедневные напоминания для пользователя.

        Args:
            user_id (int): ID пользователя.
        """
        if not db.get_remind_time(user_id):
            self.send_message(user_id, "🔕 У вас не настроены напоминания. ", self.get_full_menu_keyboard(user_id))
            return
        db.set_remind_time(user_id, None)
        self.send_message(user_id, "🔕 Напоминания отключены. ", self.get_full_menu_keyboard(user_id))

    def handle_rating_menu(self, user_id):
        """
        Переводит пользователя в состояние ожидания выбора типа рейтинга.

        Args:
            user_id (int): ID пользователя.
        """
        self.user_states[user_id] = {'state': 'waiting_rating_type'}
        self.send_message(user_id, "Выберите рейтинг: ", get_rating_keyboard())

    def handle_rating_selection(self, user_id, selection):
        """
        Обрабатывает выбор типа рейтинга из меню.

        Args:
            user_id (int): ID пользователя.
            selection (str): Текст выбранной кнопки.
        """
        if selection == 'общий рейтинг (по xp)':
            self.show_global_rating(user_id)
        elif selection.startswith('рейтинг:'):
            self.show_exercise_rating(user_id, selection.replace('рейтинг:', '').strip())
        elif selection in ('назад', 'отмена'):
            self.send_message(user_id, "Главное меню: ", self.get_full_menu_keyboard(user_id))
            self.user_states.pop(user_id, None)

    def show_global_rating(self, user_id):
        """
        Формирует и отправляет глобальный рейтинг по XP.

        Args:
            user_id (int): ID пользователя (для отображения его XP).
        """
        rating = db.get_global_rating()
        total_xp = db.get_total_experience(user_id)
        text = f"🏆 ВАШ ОПЫТ: {total_xp} XP\n\n🏆 ОБЩИЙ РЕЙТИНГ (по XP)\n{'━' * 30}\n"
        if not rating:
            text += "Пока нет участников."
        else:
            for idx, (uid, name, xp) in enumerate(rating, 1):
                medal = ["🥇", "🥈", "🥉", "📌"][min(idx - 1, 3)]
                text += f"{medal} {idx}. {name}: {xp} XP\n"
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def show_exercise_rating(self, user_id, exercise):
        """
        Формирует и отправляет рейтинг по конкретному упражнению.

        Args:
            user_id (int): ID пользователя.
            exercise (str): Название упражнения.
        """
        if exercise not in EXERCISES_CONFIG:
            self.send_message(user_id, "Упражнение не найдено", self.get_full_menu_keyboard(user_id));
            return
        rating = db.get_exercise_rating(exercise)
        text = f"🏆 РЕЙТИНГ ПО {exercise.upper()}\n{'━' * 30}\n"
        if not rating:
            text += "Пока нет участников."
        else:
            for idx, (uid, name, type_name, reps) in enumerate(rating, 1):
                medal = ["🥇", "🥈", "🥉", "📌"][min(idx - 1, 3)]
                text += f"{medal} {idx}. {name}: {reps} раз ({type_name})\n"
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def handle_stats_menu(self, user_id):
        """
        Переводит пользователя в состояние выбора упражнения для просмотра статистики.

        Args:
            user_id (int): ID пользователя.
        """
        self.user_states[user_id] = {'state': 'waiting_stats_exercise'}
        self.send_message(user_id, "Выберите упражнение: ", get_exercises_keyboard())

    def handle_stats_exercise(self, user_id, exercise_name):
        """
        Обрабатывает выбор упражнения и показывает статистику по нему.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название выбранного упражнения.
        """
        if exercise_name == 'назад':
            self.show_full_menu(user_id);
            self.user_states.pop(user_id, None);
            return
        if exercise_name not in EXERCISES_CONFIG:
            self.send_message(user_id, "Выберите из списка", get_exercises_keyboard());
            return

        total_xp = db.get_total_experience(user_id)
        stats = db.get_exercise_stats(user_id, exercise_name)

        text = f"📊 СТАТИСТИКА: {exercise_name.upper()}\n🏆 Всего опыта: {total_xp} XP\n{'━' * 30}\n\n"
        if not stats:
            text += "Нет тренировок. Начните тренироваться!"
        else:
            for stat in stats:
                text += (f"💪 {stat['name'].upper()}\n"
                         f"   Уровень: {stat['level']}/{stat['total_levels']}\n"
                         f"   Всего: {stat['total_reps']} | Рекорд: {stat['max_reps']} 🏆\n"
                         f"   День/Нед/Мес: {stat['day_reps']}/{stat['week_reps']}/{stat['month_reps']}\n")
                if stat['next_type']:
                    text += f"   ➡️ До {stat['next_type']['name']}: {stat['next_type']['needed']} повт.\n"
                elif stat['level'] < stat['total_levels']:
                    nxt = EXERCISES_CONFIG[exercise_name]['types'][stat['level']]
                    text += f"   🔒 {nxt['name']} за {nxt['cost']} XP\n"
                else:
                    text += f"   🏆 МАКСИМУМ!\n"
                text += "\n"

        self.user_states[user_id] = {'state': 'waiting_stats_action', 'exercise': exercise_name}
        self.send_message(user_id, text, get_stats_action_keyboard())

    def handle_stats_action(self, user_id, action):
        """
        Обрабатывает действия в меню статистики (Магазин, Мои стили, Info).

        Args:
            user_id (int): ID пользователя.
            action (str): Выбранное действие.
        """
        if action == 'назад':
            self.handle_stats_menu(user_id);
            return
        exercise_name = self.user_states[user_id]['exercise']
        if action == 'магазин':
            self.handle_store(user_id, exercise_name)
        elif action == 'мои стили':
            self.handle_my_styles(user_id, exercise_name)
        elif action == 'подробнее о стилях':
            self.handle_info(user_id, exercise_name)

    def handle_store(self, user_id, exercise_name):
        """
        Открывает магазин стилей для выбранного упражнения.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.
        """
        total_xp = db.get_total_experience(user_id)
        self.send_message(user_id, f"🏪 МАГАЗИН: {exercise_name.upper()}\n💰 XP: {total_xp}\n\nВыберите стиль: ",
                          get_store_keyboard(user_id, exercise_name))
        self.user_states[user_id] = {'state': 'waiting_store_type', 'exercise': exercise_name}

    def handle_store_type(self, user_id, type_text):
        """
        Обрабатывает покупку стиля в магазине.

        Args:
            user_id (int): ID пользователя.
            type_text (str): Текст кнопки с названием стиля и стоимостью.
        """
        if type_text == 'назад':
            self.handle_stats_exercise(user_id, self.user_states[user_id]['exercise']);
            return
        if type_text == "Все стили уже куплены!":
            self.send_message(user_id, "Все стили уже куплены! 🎉", self.get_full_menu_keyboard(user_id));
            self.user_states.pop(user_id, None);
            return

        exercise_name = self.user_states[user_id]['exercise']

        # Парсинг названия и стоимости из текста кнопки "Style Name (100 XP)"
        if '(' not in type_text or 'xp' not in type_text.lower():
            self.send_message(user_id, "❌ Выберите из списка", get_store_keyboard(user_id, exercise_name));
            return

        last_open = type_text.rfind('(')
        type_name = type_text[:last_open].strip()
        try:
            cost = int(type_text[last_open + 1:].replace(')', '').replace('XP', '').replace('xp', '').strip())
        except ValueError:
            self.send_message(user_id, "❌ Ошибка формата", get_store_keyboard(user_id, exercise_name));
            return

        if cost == 0:
            self.send_message(user_id, "Базовый стиль уже доступен!", self.get_full_menu_keyboard(user_id));
            self.user_states.pop(user_id, None);
            return

        success, msg = db.purchase_type(user_id, exercise_name, type_name, cost)
        self.send_message(user_id, msg, self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def handle_my_styles(self, user_id, exercise_name):
        """
        Показывает список купленных стилей и их статистику.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.
        """
        info = db.get_purchased_types_info(user_id, exercise_name)
        if not info:
            self.send_message(user_id, f"❌ Нет купленных стилей для {exercise_name}.", get_stats_action_keyboard());
            return

        text = f"📦 КУПЛЕННЫЕ СТИЛИ: {exercise_name.upper()}\n{'━' * 30}\n\n"
        for s in info:
            text += (f"💪 {s['name'].upper()}\n"
                     f"   ✨ x{s['xp_multiplier']} | 📊 {s['total_reps']} | 🏆 {s['max_reps']}\n\n")

        self.user_states[user_id] = {'state': 'waiting_stats_action', 'exercise': exercise_name}
        self.send_message(user_id, text, get_stats_action_keyboard())

    def handle_info(self, user_id, exercise_name):
        """
        Переводит в состояние просмотра описания конкретного стиля.

        Args:
            user_id (int): ID пользователя.
            exercise_name (str): Название упражнения.
        """
        self.user_states[user_id] = {'state': 'waiting_info_type', 'exercise': exercise_name}
        self.send_message(user_id, f"📖 {exercise_name.upper()}\nВыберите стиль: ",
                          get_exercise_info_keyboard(exercise_name))

    def handle_info_type(self, user_id, type_name):
        """
        Показывает описание выбранного стиля упражнения.

        Args:
            user_id (int): ID пользователя.
            type_name (str): Название стиля.
        """
        if type_name == 'назад':
            self.handle_stats_exercise(user_id, self.user_states[user_id]['exercise']);
            return

        exercise_name = self.user_states[user_id]['exercise']
        for t in EXERCISES_CONFIG[exercise_name]['types']:
            if t['name'] == type_name:
                self.send_message(user_id, f"📖 {exercise_name.upper()} - {type_name}\n\n{t['description']}",
                                  self.get_full_menu_keyboard(user_id));
                self.user_states.pop(user_id, None);
                return
        self.send_message(user_id, "❌ Стиль не найден", self.get_full_menu_keyboard(user_id));
        self.user_states.pop(user_id, None)

    def handle_workout_request(self, user_id):
        """
        Начинает процесс записи тренировки (выбор упражнения).

        Args:
            user_id (int): ID пользователя.
        """
        self.user_states[user_id] = {'state': 'waiting_workout_exercise'}
        self.send_message(user_id, "Выберите упражнение: ", get_exercises_keyboard())

    def handle_workout_exercise(self, user_id, exercise_text):
        """
        Обрабатывает выбор упражнения и предлагает выбрать стиль.

        Args:
            user_id (int): ID пользователя.
            exercise_text (str): Название выбранного упражнения.
        """
        if exercise_text == 'назад':
            self.show_full_menu(user_id);
            self.user_states.pop(user_id, None);
            return

        ex_name = exercise_text.lower()
        if ex_name not in EXERCISES_CONFIG:
            self.send_message(user_id, "❌ Выберите из списка", get_exercises_keyboard());
            return

        self.user_states[user_id] = {'state': 'waiting_workout_type', 'exercise': ex_name}
        self.send_message(user_id, f"🏋️ {ex_name.upper()}\nВыберите стиль: ",
                          get_workout_types_keyboard(user_id, ex_name))

    def handle_workout_type(self, user_id, type_text):
        """
        Обрабатывает выбор стиля и запрашивает количество повторений.

        Args:
            user_id (int): ID пользователя.
            type_text (str): Название выбранного стиля.
        """
        if type_text in ('отмена', 'назад'):
            self.cancel_action(user_id) if type_text == 'отмена' else self.handle_workout_request(user_id);
            return

        ex_name = self.user_states[user_id]['exercise']
        if type_text not in db.get_purchased_types(user_id, ex_name):
            self.send_message(user_id, "❌ Выберите доступный стиль", get_workout_types_keyboard(user_id, ex_name));
            return

        multiplier = next(t['xp_multiplier'] for t in EXERCISES_CONFIG[ex_name]['types'] if t['name'] == type_text)
        self.user_states[user_id] = {'state': 'waiting_reps', 'exercise': ex_name, 'type_name': type_text}
        self.send_message(user_id, f"🏋️ {ex_name} - {type_text}\n✨ x{multiplier}\n\nВведите кол-во повторений: ",
                          get_cancel_keyboard())

    def handle_reps_input(self, user_id, reps_text):
        """
        Принимает количество повторений, валидирует и сохраняет тренировку.

        Args:
            user_id (int): ID пользователя.
            reps_text (str): Введенное число повторений.
        """
        if reps_text == 'отмена':
            self.cancel_action(user_id);
            return

        try:
            reps = int(reps_text)
            if reps <= 0: raise ValueError
        except ValueError:
            self.send_message(user_id, "❌ Введите положительное число!", get_cancel_keyboard());
            return

        ex_name = self.user_states[user_id]['exercise']
        type_name = self.user_states[user_id]['type_name']
        max_reps = MAX_REPS_MAP.get((ex_name, type_name), 100)

        if reps > max_reps:
            self.send_message(user_id, f"❌ Максимум {max_reps} для '{type_name}'", get_cancel_keyboard());
            return

        result = db.add_workout(user_id, ex_name, type_name, reps)
        if not result:
            self.send_message(user_id, "❌ Ошибка сохранения", self.get_full_menu_keyboard(user_id));
            del self.user_states[user_id];
            return

        text = (f"✅ {ex_name} - {type_name}\n"
                f"🏋️ {reps} раз\n"
                f"✨ +{result['xp_earned']} XP\n"
                f"📊 Всего: {result['total_reps']}\n"
                f"🏆 Лучший: {result['best_single_set']}")

        if result['is_record']:
            text += f"\n\n{random.choice(MOTIVATION_MESSAGES).format(exercise=ex_name, type=type_name, reps=result['record_reps'])}"

        if result['available_to_buy']:
            current_xp = db.get_total_experience(user_id)
            item = result['available_to_buy'][0]
            text += f"\n\n{random.choice(PURCHASE_REMINDER_MESSAGES).format(xp=current_xp, type_name=item['name'], cost=item['cost'])}"

        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))
        del self.user_states[user_id]

    def handle_remind(self, user_id):
        """
        Начинает процесс настройки времени напоминаний.

        Args:
            user_id (int): ID пользователя.
        """
        current = db.get_remind_time(user_id)
        text = f"🔔 Текущее время: {current}\n\nВведите новое (ЧЧ:ММ) или 'Отмена': " if current else "⏰ Введите время напоминаний (ЧЧ:ММ): "
        self.send_message(user_id, text, get_remind_keyboard())
        self.user_states[user_id] = {'state': 'waiting_remind_time'}

    def handle_set_remind_time(self, user_id, time_str):
        """
        Сохраняет время напоминаний после валидации формата.

        Args:
            user_id (int): ID пользователя.
            time_str (str): Строка времени.
        """
        if time_str == 'отмена':
            self.cancel_action(user_id);
            return
        if time_str == 'установить время':
            self.send_message(user_id, "Введите время ЧЧ:ММ: ", get_cancel_keyboard());
            return

        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', time_str):
            self.send_message(user_id, "❌ Формат ЧЧ:ММ (напр. 19:30)", get_remind_keyboard());
            return

        db.set_remind_time(user_id, time_str)
        self.send_message(user_id, f"✅ Напоминания на {time_str}", self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def process_message(self, user_id, text, username, first_name, last_name):
        """
        Главный метод маршрутизации входящих сообщений.
        Определяет, является ли сообщение частью диалога (state) или новой командой.

        Args:
            user_id (int): ID пользователя.
            text (str): Текст сообщения.
            username (str): Screen name.
            first_name (str): Имя.
            last_name (str): Фамилия.
        """
        text = text.lower().strip()

        # Проверка активных состояний диалога
        if user_id in self.user_states:
            state = self.user_states[user_id]['state']
            state_map = {
                'waiting_workout_exercise': lambda: self.handle_workout_exercise(user_id, text),
                'waiting_workout_type': lambda: self.handle_workout_type(user_id, text),
                'waiting_reps': lambda: self.handle_reps_input(user_id, text),
                'waiting_remind_time': lambda: self.handle_set_remind_time(user_id, text),
                'waiting_stats_exercise': lambda: self.handle_stats_exercise(user_id, text),
                'waiting_stats_action': lambda: self.handle_stats_action(user_id, text),
                'waiting_store_type': lambda: self.handle_store_type(user_id, text),
                'waiting_info_type': lambda: self.handle_info_type(user_id, text),
                'waiting_export_type': lambda: self.handle_export_type(user_id, text),
                'waiting_timezone': lambda: self.handle_set_timezone(user_id, text),
                'waiting_rating_type': lambda: self.handle_rating_selection(user_id, text)
            }
            if state in state_map:
                state_map[state]()
                return

        # Обработка команд главного меню
        cmd_map = {
            '/start': lambda: self.handle_start(user_id, username, first_name, last_name),
            'начать': lambda: self.handle_start(user_id, username, first_name, last_name) if not db.user_exists(
                user_id) else self.show_full_menu(user_id),
            '/help': lambda: self.handle_help(user_id),
            'помощь': lambda: self.handle_help(user_id),
            '/stats': lambda: self.handle_stats_menu(user_id),
            'статистика': lambda: self.handle_stats_menu(user_id),
            '/rating': lambda: self.handle_rating_menu(user_id),
            'рейтинг': lambda: self.handle_rating_menu(user_id),
            '/remind': lambda: self.handle_remind(user_id),
            'настройки': lambda: self.handle_remind(user_id),
            'напоминания': lambda: self.handle_remind(user_id),
            '/stop_remind': lambda: self.handle_stop_remind(user_id),
            'отключить напоминания': lambda: self.handle_stop_remind(user_id),
            'записать тренировку': lambda: self.handle_workout_request(user_id),
            '/export': lambda: self.handle_export_request(user_id),
            'экспорт': lambda: self.handle_export_request(user_id),
            'экспорт статистики': lambda: self.handle_export_request(user_id),
            '/timezone': lambda: self.handle_timezone_request(user_id),
            'часовой пояс': lambda: self.handle_timezone_request(user_id),
            'назад': lambda: self.show_full_menu(user_id)
        }

        handler = cmd_map.get(text)
        if handler:
            handler()
        else:
            self.send_message(user_id, "❌ Неизвестная команда. Нажмите 'Начать'", get_main_keyboard())

    def handle_export_type(self, user_id, export_type):
        """
        Обрабатывает выбор формата экспорта и генерирует CSV-файл.

        Для учебного проекта: CSV отправляется как текстовое сообщение,
        которое пользователь может скопировать.

        В продакшене: использовать docs.save + messages.send с attachment.

        Args:
            user_id (int): ID пользователя.
            export_type (str): Выбранный тип экспорта.
        """
        if export_type == 'назад':
            self.show_full_menu(user_id)
            self.user_states.pop(user_id, None)
            return

        exercise_filter = None
        if export_type == 'csv (по упражнению)':
            pass

        workouts = db.get_user_workouts(user_id, exercise_name=exercise_filter)

        if not workouts:
            self.send_message(
                user_id,
                "❌ Нет данных для экспорта. Сначала запишите тренировки!",
                self.get_full_menu_keyboard(user_id)
            )
            self.user_states.pop(user_id, None)
            return

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n')

        writer.writerow(['Дата', 'Упражнение', 'Стиль', 'Повторения', 'Получено XP'])

        for w in reversed(workouts):
            writer.writerow([
                w['date'],
                w['exercise'],
                w['type'],
                w['reps'],
                w['xp']
            ])

        csv_content = output.getvalue()
        output.close()

        lines = csv_content.strip().split('\n')
        preview = '\n'.join(lines[:10])
        total = len(lines) - 1

        message = (
            f"📊 Ваш экспорт готов!\n\n"
            f"📄 Формат: CSV (разделитель ';')\n"
            f"📈 Записей: {total}\n\n"
            f"🔍 Превью:\n"
            f"```\n{preview}\n```"
            f"\n\n💡 Чтобы сохранить полный файл:\n"
            f"1. Скопируйте это сообщение целиком\n"
            f"2. Вставьте в текстовый редактор (Блокнот, Excel, Google Sheets)\n"
            f"3. Сохраните как `fitness_export.csv`\n\n"
            f"⚠️ Примечание: В полной версии бот отправит файл автоматически."
        )

        try:
            self.send_message(user_id, message, self.get_full_menu_keyboard(user_id))
            logger.info(f"Экспорт статистики запрошен пользователем {user_id} ({total} записей)")
        except Exception as e:
            logger.error(f"Ошибка при отправке экспорта пользователю {user_id}: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при генерации экспорта. Попробуйте позже.",
                self.get_full_menu_keyboard(user_id)
            )

        self.user_states.pop(user_id, None)

    def handle_export_request(self, user_id):
        """
        Генерирует CSV-файл со статистикой пользователя и отправляет его как документ.
        """
        filepath = None
        try:
            logger.info(f"Начало экспорта для user {user_id}")

            workouts = db.get_user_workouts_for_export(user_id)

            if not workouts:
                self.send_message(user_id, "❌ У вас пока нет записанных тренировок.",
                                  self.get_full_menu_keyboard(user_id))
                return
            filename = f"fitness_stats_{user_id}.csv"
            filepath = os.path.join(os.getcwd(), filename)

            logger.info(f"Создание файла: {filepath}")
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                writer.writerow(['Дата', 'Упражнение', 'Стиль', 'Повторения', 'XP'])
                for w in workouts:
                    date_str = str(w[0]).split('T')[0] if 'T' in str(w[0]) else str(w[0])
                    writer.writerow([date_str, w[1], w[2], w[3], w[4]])

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                raise Exception("Файл не создан или пуст")

            logger.info("Запрос URL для загрузки...")
            upload_url = self.vk.docs.getMessagesUploadServer(type='doc', peer_id=user_id)['upload_url']

            logger.info("Загрузка файла на сервер VK...")
            with open(filepath, 'rb') as f:
                response = requests.post(upload_url, files={'file': f})

            logger.info(f"Ответ VK при загрузке: {response.status_code}")

            if response.status_code != 200:
                raise Exception(f"Ошибка загрузки файла: {response.text}")

            file_data = response.json()
            if 'file' not in file_data:
                raise Exception(f"VK не вернул поле 'file': {file_data}")

            logger.info("Сохранение документа...")
            saved_doc = self.vk.docs.save(file=file_data['file'], title=filename)
            logger.info(f"Ответ docs.save: {saved_doc}")

            doc_info = saved_doc.get('doc', saved_doc) if isinstance(saved_doc, dict) else saved_doc

            if not doc_info or 'id' not in doc_info or 'owner_id' not in doc_info:
                raise Exception(f"Некорректная структура ответа: {saved_doc}")

            doc_id = doc_info['id']
            owner_id = doc_info['owner_id']

            attachment = f"doc{owner_id}_{doc_id}"
            logger.info(f"Отправка сообщения с attachment: {attachment}")

            self.send_message(
                user_id,
                f"📊 Ваша статистика готова!\n\n📁 Файл: {filename}\n📈 Записей: {len(workouts)}",
                keyboard=self.get_full_menu_keyboard(user_id),
                attachment=attachment
            )
        except Exception as e:
            logger.error(f"Критическая ошибка при экспорте для user {user_id}: {e}", exc_info=True)
            self.send_message(user_id, f"❌ Произошла ошибка при создании файла: {str(e)}",
                              self.get_full_menu_keyboard(user_id))
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Временный файл {filepath} удален")
                except Exception as e:
                    logger.error(f"Не удалось удалить временный файл: {e}")

    def handle_timezone_request(self, user_id):
        """Запускает процесс установки часового пояса (NFR-09)"""
        self.user_states[user_id] = {'state': 'waiting_timezone'}
        self.send_message(user_id,
                          "⏰ Введите смещение вашего часового пояса относительно UTC.\n\nПримеры: `3` (Москва), `5` (Екатеринбург), `-5` (Нью-Йорк), `0` (Лондон):",
                          get_cancel_keyboard())

    def handle_set_timezone(self, user_id, text):
        """Сохраняет часовой пояс после валидации"""
        if text == 'отмена':
            self.cancel_action(user_id);
            return

        try:
            offset = int(text)
            if not (-12 <= offset <= 14):
                raise ValueError
            db.set_timezone(user_id, offset)
            self.send_message(user_id, f"✅ Часовой пояс установлен: UTC{offset:+d}",
                              self.get_full_menu_keyboard(user_id))
            self.user_states.pop(user_id, None)
        except ValueError:
            self.send_message(user_id, "❌ Введите целое число от -12 до 14", get_cancel_keyboard())