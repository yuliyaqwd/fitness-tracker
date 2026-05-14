from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from config import EXERCISES_CONFIG
from database import db


def get_main_keyboard(user_id: int = None) -> VkKeyboard:
    """
    Генерирует клавиатуру для стартового сообщения (команда /start).
    Содержит единственную кнопку 'Начать' для инициализации работы с ботом.

    Args:
        user_id (int, optional): ID пользователя (не используется в логике,
                                 сохранён для совместимости сигнатуры).

    Returns:
        VkKeyboard: Клавиатура с кнопкой старта.
    """
    kb = VkKeyboard(one_time=False)
    kb.add_button('Начать', color=VkKeyboardColor.POSITIVE)
    return kb


def get_exercises_keyboard() -> VkKeyboard:
    """
    Генерирует клавиатуру с кнопками для выбора упражнения.
    Динамически подгружает все доступные упражнения из EXERCISES_CONFIG.

    Returns:
        VkKeyboard: Клавиатура со списком упражнений и кнопкой 'Назад'.
    """
    kb = VkKeyboard(one_time=True)
    for ex in EXERCISES_CONFIG.keys():
        kb.add_button(ex, color=VkKeyboardColor.PRIMARY)
        kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb


def get_stats_action_keyboard() -> VkKeyboard:
    """
    Генерирует клавиатуру меню действий после просмотра статистики.
    Позволяет пользователю перейти в магазин, просмотреть купленные стили
    или получить подробную информацию.

    Returns:
        VkKeyboard: Клавиатура с кнопками: 'Магазин', 'Мои стили',
                    'Подробнее о стилях', 'Назад'.
    """
    kb = VkKeyboard(one_time=True)
    kb.add_button('Магазин', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('Мои стили', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('Подробнее о стилях', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb


def get_workout_types_keyboard(user_id: int, exercise_name: str) -> VkKeyboard:
    """
    Генерирует клавиатуру с доступными (купленными) стилями для записи тренировки.
    Запрашивает БД для проверки разблокированных стилей. Если стилей нет,
    выводит заглушку.

    Args:
        user_id (int): ID пользователя.
        exercise_name (str): Название упражнения.

    Returns:
        VkKeyboard: Клавиатура со списком доступных стилей + 'Назад' и 'Отмена'.
    """
    kb = VkKeyboard(one_time=True)
    purchased = db.get_purchased_types(user_id, exercise_name)

    if not purchased:
        kb.add_button("Нет доступных стилей", color=VkKeyboardColor.SECONDARY)
        kb.add_line()
    else:
        for t in purchased:
            kb.add_button(t, color=VkKeyboardColor.POSITIVE)
            kb.add_line()
        kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
        kb.add_line()
        kb.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)

    return kb


def get_store_keyboard(user_id: int, exercise_name: str) -> VkKeyboard:
    """
    Генерирует клавиатуру магазина стилей.
    Отображает только некупленные стили с указанием стоимости в XP.
    Если все стили уже разблокированы, показывает соответствующее сообщение.

    Args:
        user_id (int): ID пользователя.
        exercise_name (str): Название упражнения.

    Returns:
        VkKeyboard: Клавиатура с доступными для покупки стилями и кнопкой 'Назад'.
    """
    kb = VkKeyboard(one_time=True)
    purchased = db.get_purchased_types(user_id, exercise_name)
    all_types = EXERCISES_CONFIG[exercise_name]['types']

    # Фильтруем только те стили, которые ещё не куплены и имеют стоимость > 0
    available = [
        f"{t['name']} ({t['cost']} XP)"
        for t in all_types
        if t['cost'] > 0 and t['name'] not in purchased
    ]

    if available:
        for item in available:
            kb.add_button(item, color=VkKeyboardColor.PRIMARY)
            kb.add_line()
    else:
        kb.add_button("Все стили уже куплены!", color=VkKeyboardColor.SECONDARY)
        kb.add_line()

    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb


def get_exercise_info_keyboard(exercise_name: str) -> VkKeyboard:
    """
    Генерирует клавиатуру для выбора стиля с целью просмотра его описания.
    Содержит абсолютно все стили из конфигурации (независимо от статуса покупки).

    Args:
        exercise_name (str): Название упражнения.

    Returns:
        VkKeyboard: Клавиатура со списком всех стилей и кнопкой 'Назад'.
    """
    kb = VkKeyboard(one_time=True)
    for t in EXERCISES_CONFIG[exercise_name]['types']:
        kb.add_button(t['name'], color=VkKeyboardColor.PRIMARY)
        kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb


def get_rating_keyboard() -> VkKeyboard:
    """
    Генерирует клавиатуру выбора типа рейтинга.
    Содержит кнопку 'Общий рейтинг (по XP)' и отдельные рейтинги
    по каждому упражнению из конфигурации.

    Returns:
        VkKeyboard: Клавиатура с вариантами рейтингов и кнопкой 'Назад'.
    """
    kb = VkKeyboard(one_time=True)
    kb.add_button('Общий рейтинг (по XP)', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    for ex in EXERCISES_CONFIG.keys():
        kb.add_button(f"Рейтинг: {ex}", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb


def get_cancel_keyboard() -> VkKeyboard:
    """
    Генерирует минимальную клавиатуру с кнопкой 'Отмена'.
    Используется на этапах ввода пользовательских данных (например, ввод повторений
    или времени напоминаний).

    Returns:
        VkKeyboard: Клавиатура с единственной красной кнопкой 'Отмена'.
    """
    kb = VkKeyboard(one_time=True)
    kb.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)
    return kb


def get_remind_keyboard() -> VkKeyboard:
    """
    Генерирует клавиатуру для настройки времени напоминаний.
    Используется при первом вызове команды /remind.

    Returns:
        VkKeyboard: Клавиатура с кнопками 'Установить время' и 'Отмена'.
    """
    kb = VkKeyboard(one_time=True)
    kb.add_button('Установить время', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)
    return kb


def get_export_keyboard() -> VkKeyboard:
    """
    Генерирует клавиатуру выбора формата экспорта статистики.

    Returns:
        VkKeyboard: Клавиатура с опциями:
            - 'CSV (все тренировки)' — полный экспорт
            - 'CSV (по упражнению)' — фильтр по упражнению
            - 'Назад' — возврат в меню
    """
    kb = VkKeyboard(one_time=True)
    kb.add_button('CSV (все тренировки)', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('CSV (по упражнению)', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('Назад', color=VkKeyboardColor.SECONDARY)
    return kb