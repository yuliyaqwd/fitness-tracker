from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from config import EXERCISES_CONFIG
from database import db

def get_main_keyboard(user_id=None):
    kb = VkKeyboard(one_time=False)
    kb.add_button('Начать', color=VkKeyboardColor.POSITIVE)
    return kb

def get_exercises_keyboard():
    kb = VkKeyboard(one_time=True)
    for ex in EXERCISES_CONFIG.keys():
        kb.add_button(ex, color=VkKeyboardColor.PRIMARY)
        kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb

def get_stats_action_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button('Магазин', color=VkKeyboardColor.PRIMARY); kb.add_line()
    kb.add_button('Мои стили', color=VkKeyboardColor.PRIMARY); kb.add_line()
    kb.add_button('Подробнее о стилях', color=VkKeyboardColor.PRIMARY); kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb

def get_workout_types_keyboard(user_id, exercise_name):
    kb = VkKeyboard(one_time=True)
    purchased = db.get_purchased_types(user_id, exercise_name)
    if not purchased:
        kb.add_button("Нет доступных стилей", color=VkKeyboardColor.SECONDARY); kb.add_line()
    else:
        for t in purchased:
            kb.add_button(t, color=VkKeyboardColor.POSITIVE); kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY); kb.add_line()
    kb.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)
    return kb

def get_store_keyboard(user_id, exercise_name):
    kb = VkKeyboard(one_time=True)
    purchased = db.get_purchased_types(user_id, exercise_name)
    all_types = EXERCISES_CONFIG[exercise_name]['types']
    available = [f"{t['name']} ({t['cost']} XP)" for t in all_types if t['cost'] > 0 and t['name'] not in purchased]
    if available:
        for item in available:
            kb.add_button(item, color=VkKeyboardColor.PRIMARY); kb.add_line()
    else:
        kb.add_button("Все стили уже куплены!", color=VkKeyboardColor.SECONDARY); kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb

def get_exercise_info_keyboard(exercise_name):
    kb = VkKeyboard(one_time=True)
    for t in EXERCISES_CONFIG[exercise_name]['types']:
        kb.add_button(t['name'], color=VkKeyboardColor.PRIMARY); kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb

def get_rating_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button('Общий рейтинг (по XP)', color=VkKeyboardColor.PRIMARY); kb.add_line()
    for ex in EXERCISES_CONFIG.keys():
        kb.add_button(f"Рейтинг: {ex}", color=VkKeyboardColor.PRIMARY); kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb

def get_cancel_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)
    return kb

def get_remind_keyboard():
    kb = VkKeyboard(one_time=True)
    kb.add_button('Установить время', color=VkKeyboardColor.PRIMARY); kb.add_line()
    kb.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)
    return kb