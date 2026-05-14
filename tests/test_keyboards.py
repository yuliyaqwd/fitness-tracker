from keyboards import *

def test_get_main_keyboard():
    kb = get_main_keyboard()
    assert kb is not None
    assert len(kb.keyboard['buttons']) == 1

def test_get_exercises_keyboard():
    kb = get_exercises_keyboard()
    # 4 упражнения + 1 кнопка Назад
    assert len(kb.keyboard['buttons']) == 5

def test_get_cancel_keyboard():
    kb = get_cancel_keyboard()
    assert kb is not None
    assert 'buttons' in kb.keyboard
    assert len(kb.keyboard['buttons']) >= 1
    first_button = kb.keyboard['buttons'][0][0]
    assert 'action' in first_button
    assert first_button['action']['label'] == 'Отмена'

def test_get_rating_keyboard():
    kb = get_rating_keyboard()
    # 1 общий + 4 упражнения + Назад
    assert len(kb.keyboard['buttons']) == 6