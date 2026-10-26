from brain.chat_errors import friendly_chat_error


def test_401_message():
    msg = friendly_chat_error(Exception("Error 401 Unauthorized"))
    assert "API Key" in msg
    assert "设置" in msg


def test_model_not_found():
    msg = friendly_chat_error(Exception("404 model not found"))
    assert "模型" in msg


def test_connection_hint():
    msg = friendly_chat_error(Exception("Connection error"))
    assert "连接" in msg or "地址" in msg
