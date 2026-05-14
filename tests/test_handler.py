import pytest
from unittest.mock import patch, MagicMock
from handler import BotHandler
from config import EXERCISES_CONFIG


class TestHandlerRouting:
    @patch('handler.db')
    def test_process_message_unknown_command(self, mock_db, mock_vk, capsys):
        handler = BotHandler(mock_vk)
        handler.process_message(1, 'абракадабра', 'u', 'I', 'P')
        mock_vk.messages.send.assert_called_once()
        assert 'Неизвестная команда' in mock_vk.messages.send.call_args.kwargs['message']

    @patch('handler.db')
    def test_process_message_start_new_user(self, mock_db, mock_vk):
        mock_db.user_exists.return_value = False
        handler = BotHandler(mock_vk)
        handler.process_message(1, '/start', 'u', 'Ivan', 'Petrov')
        mock_db.register_user.assert_called_once_with(1, 'u', 'Ivan', 'Petrov')
        mock_vk.messages.send.assert_called_once()
        assert 'Привет, Ivan' in mock_vk.messages.send.call_args.kwargs['message']

    @patch('handler.db')
    def test_process_message_help(self, mock_db, mock_vk):
        handler = BotHandler(mock_vk)
        handler.process_message(1, '/help', 'u', 'I', 'P')
        mock_vk.messages.send.assert_called_once()
        assert 'Помощь' in mock_vk.messages.send.call_args.kwargs['message']


class TestStateMachineFlow:
    @patch('handler.db')
    def test_remind_time_validation(self, mock_db, mock_vk):
        mock_db.get_remind_time.return_value = None
        handler = BotHandler(mock_vk)

        # Запрос времени
        handler.handle_remind(1)
        assert handler.user_states[1]['state'] == 'waiting_remind_time'

        # Некорректный ввод
        handler.handle_set_remind_time(1, '25:00')
        assert 'Формат ЧЧ:ММ' in mock_vk.messages.send.call_args.kwargs['message']

        # Корректный ввод
        handler.handle_set_remind_time(1, '19:30')
        mock_db.set_remind_time.assert_called_with(1, '19:30')
        assert 1 not in handler.user_states