from config.chat_api_config import (
    ChatApiConfig,
    LEGACY_CHAT_ENV_KEYS,
    chat_api_to_env,
)
from config.env_update import update_env_file


def test_update_env_drops_legacy_chat_keys(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "DEEPSEEK_API_KEY=old\n"
        "DEEPSEEK_BASE_URL=https://old.com\n"
        "DEEPSEEK_MODEL=old-model\n"
        "PET_MODE=survival\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("config.env_update.ENV_PATH", env)

    update_env_file(
        chat_api_to_env(ChatApiConfig("new", "https://new.com", "new-m")),
        drop_keys=frozenset(LEGACY_CHAT_ENV_KEYS),
    )

    text = env.read_text(encoding="utf-8")
    assert "CHAT_API_KEY=new" in text
    assert "DEEPSEEK_API_KEY" not in text
    assert "PET_MODE=survival" in text
