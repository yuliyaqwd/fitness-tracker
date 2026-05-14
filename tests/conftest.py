import pytest
from database import Database
from vk_api.keyboard import VkKeyboard

@pytest.fixture
def test_db():
    """Создает изолированную БД в оперативной памяти для каждого теста."""
    db = Database(':memory:')
    yield db
    db.conn.close()

@pytest.fixture
def mock_vk(mocker):
    """Мок VK API для тестирования обработчика без реальных запросов."""
    vk = mocker.Mock()
    vk.messages.send = mocker.Mock()
    vk.users.get = mocker.Mock(return_value=[{
        'first_name': 'Иван', 'last_name': 'Петров', 'screen_name': 'ivan_p'
    }])
    vk.docs.getMessagesUploadServer = mocker.Mock(return_value={'upload_url': 'https://fake.url'})
    vk.docs.save = mocker.Mock(return_value={'id': 999, 'owner_id': 12345})
    return vk
