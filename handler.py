import random
import logging
from vk_api.keyboard import VkKeyboard
from database import db
from keyboards import *
from config import MOTIVATION_MESSAGES, PURCHASE_REMINDER_MESSAGES, MAX_REPS_MAP, EXERCISES_CONFIG

logger = logging.getLogger(__name__)

class BotHandler:
    def __init__(self, vk_api):
        self.vk = vk_api
        self.user_states = {}

    def get_full_menu_keyboard(self, user_id):
        kb = VkKeyboard(one_time=False)
        kb.add_button('Записать тренировку', color=VkKeyboardColor.PRIMARY); kb.add_line()
        kb.add_button('Статистика', color=VkKeyboardColor.PRIMARY); kb.add_line()
        kb.add_button('Рейтинг', color=VkKeyboardColor.PRIMARY); kb.add_line()
        kb.add_button('Напоминания', color=VkKeyboardColor.PRIMARY); kb.add_line()
        if db.get_remind_time(user_id):
            kb.add_button('Отключить напоминания', color=VkKeyboardColor.NEGATIVE); kb.add_line()
        kb.add_button('Помощь', color=VkKeyboardColor.PRIMARY)
        return kb

    def show_full_menu(self, user_id):
        self.send_message(user_id, "Главное меню:", self.get_full_menu_keyboard(user_id))

    def send_message(self, user_id, text, keyboard=None):
        try:
            params = {'user_id': user_id, 'message': text, 'random_id': random.randint(1, 2 ** 31)}
            if keyboard: params['keyboard'] = keyboard.get_keyboard()
            self.vk.messages.send(**params)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")

    def cancel_action(self, user_id):
        if user_id in self.user_states: del self.user_states[user_id]
        self.send_message(user_id, "❌ Действие отменено.", self.get_full_menu_keyboard(user_id))

    def handle_start(self, user_id, username, first_name, last_name):
        if not db.user_exists(user_id):
            db.register_user(user_id, username, first_name, last_name)
            text = f"👋 Привет, {first_name}!\n\nДобро пожаловать в Fitness Tracker!\n\n🏋️ Я помогу тебе:\n• Отслеживать тренировки\n• Получать XP и открывать новые стили\n• Соревноваться в рейтинге\n\n✨ Нажми 'Начать' чтобы продолжить!"
            self.send_message(user_id, text, get_main_keyboard(user_id))
        else:
            self.show_full_menu(user_id)

    def handle_help(self, user_id):
        text = ("🤖 Fitness Tracker - Помощь\n\n📌 Команды:\n"
                "/start - Начать\n/stats - Статистика\n/rating - Рейтинги\n"
                "/remind - Напоминания\n/stop_remind - Отключить напоминания\n/help - Справка\n\n"
                "💡 Совет: Покупайте новые стили, чтобы получать больше XP!")
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))

    def handle_stop_remind(self, user_id):
        if not db.get_remind_time(user_id):
            self.send_message(user_id, "🔕 У вас не настроены напоминания.", self.get_full_menu_keyboard(user_id))
            return
        db.set_remind_time(user_id, None)
        self.send_message(user_id, "🔕 Напоминания отключены.", self.get_full_menu_keyboard(user_id))

    def handle_rating_menu(self, user_id):
        self.user_states[user_id] = {'state': 'waiting_rating_type'}
        self.send_message(user_id, "Выберите рейтинг:", get_rating_keyboard())

    def handle_rating_selection(self, user_id, selection):
        if selection == 'общий рейтинг (по xp)': self.show_global_rating(user_id)
        elif selection.startswith('рейтинг:'): self.show_exercise_rating(user_id, selection.replace('рейтинг:', '').strip())
        elif selection == 'назад' or selection == 'отмена':
            self.send_message(user_id, "Главное меню:", get_main_keyboard())
            self.user_states.pop(user_id, None)

    def show_global_rating(self, user_id):
        rating = db.get_global_rating()
        total_xp = db.get_total_experience(user_id)
        text = f"🏆 ВАШ ОПЫТ: {total_xp} XP\n\n🏆 ОБЩИЙ РЕЙТИНГ (по XP)\n{'━'*30}\n"
        if not rating: text += "Пока нет участников."
        else:
            for idx, (uid, name, xp) in enumerate(rating, 1):
                medal = ["🥇","🥈","🥉","📌"][min(idx-1, 3)]
                text += f"{medal} {idx}. {name}: {xp} XP\n"
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def show_exercise_rating(self, user_id, exercise):
        if exercise not in EXERCISES_CONFIG:
            self.send_message(user_id, "Упражнение не найдено", self.get_full_menu_keyboard(user_id)); return
        rating = db.get_exercise_rating(exercise)
        text = f"🏆 РЕЙТИНГ ПО {exercise.upper()}\n{'━'*30}\n"
        if not rating: text += "Пока нет участников."
        else:
            for idx, (uid, name, type_name, reps) in enumerate(rating, 1):
                medal = ["🥇","🥈","🥉","📌"][min(idx-1, 3)]
                text += f"{medal} {idx}. {name}: {reps} раз ({type_name})\n"
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def handle_stats_menu(self, user_id):
        self.user_states[user_id] = {'state': 'waiting_stats_exercise'}
        self.send_message(user_id, "Выберите упражнение:", get_exercises_keyboard())

    def handle_stats_exercise(self, user_id, exercise_name):
        if exercise_name == 'назад': self.show_full_menu(user_id); self.user_states.pop(user_id, None); return
        if exercise_name not in EXERCISES_CONFIG:
            self.send_message(user_id, "Выберите из списка", get_exercises_keyboard()); return
        total_xp = db.get_total_experience(user_id)
        stats = db.get_exercise_stats(user_id, exercise_name)
        text = f"📊 СТАТИСТИКА: {exercise_name.upper()}\n🏆 Всего опыта: {total_xp} XP\n{'━'*30}\n\n"
        if not stats: text += "Нет тренировок. Начните тренироваться!"
        else:
            for stat in stats:
                text += f"💪 {stat['name'].upper()}\n   Уровень: {stat['level']}/{stat['total_levels']}\n"
                text += f"   Всего: {stat['total_reps']} | Рекорд: {stat['max_reps']} 🏆\n"
                text += f"   День/Нед/Мес: {stat['day_reps']}/{stat['week_reps']}/{stat['month_reps']}\n"
                if stat['next_type']: text += f"   ➡️ До {stat['next_type']['name']}: {stat['next_type']['needed']} повт.\n"
                elif stat['level'] < stat['total_levels']:
                    nxt = EXERCISES_CONFIG[exercise_name]['types'][stat['level']]
                    text += f"   🔒 {nxt['name']} за {nxt['cost']} XP\n"
                else: text += f"   🏆 МАКСИМУМ!\n"
                text += "\n"
        self.user_states[user_id] = {'state': 'waiting_stats_action', 'exercise': exercise_name}
        self.send_message(user_id, text, get_stats_action_keyboard())

    def handle_stats_action(self, user_id, action):
        if action == 'назад': self.handle_stats_menu(user_id); return
        exercise_name = self.user_states[user_id]['exercise']
        if action == 'магазин': self.handle_store(user_id, exercise_name)
        elif action == 'мои стили': self.handle_my_styles(user_id, exercise_name)
        elif action == 'подробнее о стилях': self.handle_info(user_id, exercise_name)

    def handle_store(self, user_id, exercise_name):
        total_xp = db.get_total_experience(user_id)
        self.send_message(user_id, f"🏪 МАГАЗИН: {exercise_name.upper()}\n💰 XP: {total_xp}\n\nВыберите стиль:", get_store_keyboard(user_id, exercise_name))
        self.user_states[user_id] = {'state': 'waiting_store_type', 'exercise': exercise_name}

    def handle_store_type(self, user_id, type_text):
        if type_text == 'назад': self.handle_stats_exercise(user_id, self.user_states[user_id]['exercise']); return
        if type_text == "Все стили уже куплены!":
            self.send_message(user_id, "Все стили уже куплены! 🎉", self.get_full_menu_keyboard()); self.user_states.pop(user_id, None); return
        exercise_name = self.user_states[user_id]['exercise']
        if '(' not in type_text or 'xp' not in type_text.lower():
            self.send_message(user_id, "❌ Выберите из списка", get_store_keyboard(user_id, exercise_name)); return
        last_open = type_text.rfind('(')
        type_name = type_text[:last_open].strip()
        try: cost = int(type_text[last_open + 1:].replace(')', '').replace('XP', '').replace('xp', '').strip())
        except ValueError:
            self.send_message(user_id, "❌ Ошибка формата", get_store_keyboard(user_id, exercise_name)); return
        if cost == 0:
            self.send_message(user_id, "Базовый стиль уже доступен!", self.get_full_menu_keyboard()); self.user_states.pop(user_id, None); return
        success, msg = db.purchase_type(user_id, exercise_name, type_name, cost)
        self.send_message(user_id, msg, self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def handle_my_styles(self, user_id, exercise_name):
        info = db.get_purchased_types_info(user_id, exercise_name)
        if not info:
            self.send_message(user_id, f"❌ Нет купленных стилей для {exercise_name}.", get_stats_action_keyboard()); return
        text = f"📦 КУПЛЕННЫЕ СТИЛИ: {exercise_name.upper()}\n{'━'*30}\n\n"
        for s in info:
            text += f"💪 {s['name'].upper()}\n   ✨ x{s['xp_multiplier']} | 📊 {s['total_reps']} | 🏆 {s['max_reps']}\n\n"
        self.user_states[user_id] = {'state': 'waiting_stats_action', 'exercise': exercise_name}
        self.send_message(user_id, text, get_stats_action_keyboard())

    def handle_info(self, user_id, exercise_name):
        self.user_states[user_id] = {'state': 'waiting_info_type', 'exercise': exercise_name}
        self.send_message(user_id, f"📖 {exercise_name.upper()}\nВыберите стиль:", get_exercise_info_keyboard(exercise_name))

    def handle_info_type(self, user_id, type_name):
        if type_name == 'назад': self.handle_stats_exercise(user_id, self.user_states[user_id]['exercise']); return
        exercise_name = self.user_states[user_id]['exercise']
        for t in EXERCISES_CONFIG[exercise_name]['types']:
            if t['name'] == type_name:
                self.send_message(user_id, f"📖 {exercise_name.upper()} - {type_name}\n\n{t['description']}", self.get_full_menu_keyboard(user_id)); self.user_states.pop(user_id, None); return
        self.send_message(user_id, "❌ Стиль не найден", self.get_full_menu_keyboard(user_id)); self.user_states.pop(user_id, None)

    def handle_workout_request(self, user_id):
        self.user_states[user_id] = {'state': 'waiting_workout_exercise'}
        self.send_message(user_id, "Выберите упражнение:", get_exercises_keyboard())

    def handle_workout_exercise(self, user_id, exercise_text):
        if exercise_text == 'назад': self.show_full_menu(user_id); self.user_states.pop(user_id, None); return
        ex_name = exercise_text.lower()
        if ex_name not in EXERCISES_CONFIG:
            self.send_message(user_id, "❌ Выберите из списка", get_exercises_keyboard()); return
        self.user_states[user_id] = {'state': 'waiting_workout_type', 'exercise': ex_name}
        self.send_message(user_id, f"🏋️ {ex_name.upper()}\nВыберите стиль:", get_workout_types_keyboard(user_id, ex_name))

    def handle_workout_type(self, user_id, type_text):
        if type_text in ('отмена', 'назад'): self.cancel_action(user_id) if type_text=='отмена' else self.handle_workout_request(user_id); return
        ex_name = self.user_states[user_id]['exercise']
        if type_text not in db.get_purchased_types(user_id, ex_name):
            self.send_message(user_id, "❌ Выберите доступный стиль", get_workout_types_keyboard(user_id, ex_name)); return
        multiplier = next(t['xp_multiplier'] for t in EXERCISES_CONFIG[ex_name]['types'] if t['name'] == type_text)
        self.user_states[user_id] = {'state': 'waiting_reps', 'exercise': ex_name, 'type_name': type_text}
        self.send_message(user_id, f"🏋️ {ex_name} - {type_text}\n✨ x{multiplier}\n\nВведите кол-во повторений:", get_cancel_keyboard())

    def handle_reps_input(self, user_id, reps_text):
        if reps_text == 'отмена': self.cancel_action(user_id); return
        try:
            reps = int(reps_text)
            if reps <= 0: raise ValueError
        except ValueError:
            self.send_message(user_id, "❌ Введите положительное число!", get_cancel_keyboard()); return
        ex_name = self.user_states[user_id]['exercise']
        type_name = self.user_states[user_id]['type_name']
        max_reps = MAX_REPS_MAP.get((ex_name, type_name), 100)
        if reps > max_reps:
            self.send_message(user_id, f"❌ Максимум {max_reps} для '{type_name}'", get_cancel_keyboard()); return
        result = db.add_workout(user_id, ex_name, type_name, reps)
        if not result:
            self.send_message(user_id, "❌ Ошибка сохранения", self.get_full_menu_keyboard(user_id)); del self.user_states[user_id]; return
        text = f"✅ {ex_name} - {type_name}\n🏋️ {reps} раз\n✨ +{result['xp_earned']} XP\n📊 Всего: {result['total_reps']}\n🏆 Лучший: {result['best_single_set']}"
        if result['is_record']:
            text += f"\n\n{random.choice(MOTIVATION_MESSAGES).format(exercise=ex_name, type=type_name, reps=result['record_reps'])}"
        if result['available_to_buy']:
            current_xp = db.get_total_experience(user_id)
            item = result['available_to_buy'][0]
            text += f"\n\n{random.choice(PURCHASE_REMINDER_MESSAGES).format(xp=current_xp, type_name=item['name'], cost=item['cost'])}"
        self.send_message(user_id, text, self.get_full_menu_keyboard(user_id))
        del self.user_states[user_id]

    def handle_remind(self, user_id):
        current = db.get_remind_time(user_id)
        text = f"🔔 Текущее время: {current}\n\nВведите новое (ЧЧ:ММ) или 'Отмена':" if current else "⏰ Введите время напоминаний (ЧЧ:ММ):"
        self.send_message(user_id, text, get_remind_keyboard())
        self.user_states[user_id] = {'state': 'waiting_remind_time'}

    def handle_set_remind_time(self, user_id, time_str):
        import re
        if time_str == 'отмена': self.cancel_action(user_id); return
        if time_str == 'установить время':
            self.send_message(user_id, "Введите время ЧЧ:ММ:", get_cancel_keyboard()); return
        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', time_str):
            self.send_message(user_id, "❌ Формат ЧЧ:ММ (напр. 19:30)", get_remind_keyboard()); return
        db.set_remind_time(user_id, time_str)
        self.send_message(user_id, f"✅ Напоминания на {time_str}", self.get_full_menu_keyboard(user_id))
        self.user_states.pop(user_id, None)

    def process_message(self, user_id, text, username, first_name, last_name):
        text = text.lower().strip()
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
                'waiting_rating_type': lambda: self.handle_rating_selection(user_id, text)
            }
            if state in state_map: state_map[state](); return
        cmd_map = {
            '/start': lambda: self.handle_start(user_id, username, first_name, last_name),
            'начать': lambda: self.handle_start(user_id, username, first_name, last_name) if not db.user_exists(user_id) else self.show_full_menu(user_id),
            '/help': lambda: self.handle_help(user_id), 'помощь': lambda: self.handle_help(user_id),
            '/stats': lambda: self.handle_stats_menu(user_id), 'статистика': lambda: self.handle_stats_menu(user_id),
            '/rating': lambda: self.handle_rating_menu(user_id), 'рейтинг': lambda: self.handle_rating_menu(user_id),
            '/remind': lambda: self.handle_remind(user_id), 'настройки': lambda: self.handle_remind(user_id), 'напоминания': lambda: self.handle_remind(user_id),
            '/stop_remind': lambda: self.handle_stop_remind(user_id), 'отключить напоминания': lambda: self.handle_stop_remind(user_id),
            'записать тренировку': lambda: self.handle_workout_request(user_id),
            'назад': lambda: self.show_full_menu(user_id)
        }
        handler = cmd_map.get(text)
        if handler: handler()
        else: self.send_message(user_id, "❌ Неизвестная команда. Нажмите 'Начать'", get_main_keyboard())