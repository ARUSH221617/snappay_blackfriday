import pytest
from app import app, bot_manager
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_bot_manager(monkeypatch):
    # Reset bot manager state
    bot_manager.is_running = False
    bot_manager.input_needed = False
    bot_manager.log_queue.queue.clear()
    bot_manager.input_queue.queue.clear()
    return bot_manager

def test_index(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b"SnappBot Web Interface" in rv.data

def test_status_initial(client, mock_bot_manager):
    rv = client.get('/api/status')
    data = json.loads(rv.data)
    assert data['running'] == False
    assert data['waiting_for_input'] == False

def test_start_bot(client, mock_bot_manager, monkeypatch):
    # Mock threading.Thread to avoid actually running the bot
    class MockThread:
        def __init__(self, target=None):
            pass
        def start(self):
            pass

    monkeypatch.setattr("threading.Thread", MockThread)
    monkeypatch.setattr("main.SnappBot", lambda input_handler, log_handler: None)

    rv = client.post('/api/start')
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['status'] == 'started'
    assert mock_bot_manager.is_running == True

def test_input_handling(client, mock_bot_manager):
    mock_bot_manager.input_needed = True

    rv = client.post('/api/input', json={'value': '1234'})
    assert rv.status_code == 200
    assert mock_bot_manager.input_queue.get() == '1234'

def test_logs(client, mock_bot_manager):
    mock_bot_manager.log_queue.put("Test Log")
    rv = client.get('/api/logs')
    data = json.loads(rv.data)
    assert "Test Log" in data['logs']
