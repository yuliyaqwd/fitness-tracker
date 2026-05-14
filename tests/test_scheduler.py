import pytest
from unittest.mock import patch, MagicMock
from scheduler import run_scheduler
import time


def test_scheduler_sends_reminders():
    mock_vk = MagicMock()

    with patch('scheduler.db') as mock_db, \
            patch('scheduler.datetime') as mock_dt, \
            patch('scheduler.time.sleep') as mock_sleep:

        mock_db.get_users_with_reminders.return_value = [(1, '12:00'), (2, '13:00')]
        mock_dt.datetime.now.return_value.strftime.return_value = '12:00'

        mock_sleep.side_effect = StopIteration

        try:
            run_scheduler(mock_vk)
        except StopIteration:
            pass

        assert mock_vk.messages.send.call_count == 1
        mock_vk.messages.send.assert_called_with(
            user_id=1,
            message="⏰ Пора тренироваться! Не забывай о своих целях!",
            random_id=pytest.approx(int(time.time()), rel=0.1)
        )