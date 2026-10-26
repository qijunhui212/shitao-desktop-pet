import os

import pytest

from config.chat_api_config import (
    ChatApiConfig,
    chat_api_to_env,
    load_chat_api_config,
)


def test_is_complete_requires_all_three():
    assert not ChatApiConfig("k", "", "m").is_complete()
    assert not ChatApiConfig("", "http://x", "m").is_complete()
    assert ChatApiConfig("k", "http://x", "m").is_complete()


def test_load_prefers_chat_api_over_legacy(monkeypatch):
    monkeypatch.setenv("CHAT_API_KEY", "new-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "old-key")
    monkeypatch.setenv("CHAT_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://legacy.example.com")
    monkeypatch.setenv("CHAT_API_MODEL", "model-a")
    monkeypatch.setenv("DEEPSEEK_MODEL", "model-b")
    cfg = load_chat_api_config()
    assert cfg.api_key == "new-key"
    assert cfg.base_url == "https://api.example.com"
    assert cfg.model == "model-a"


def test_load_falls_back_to_legacy(monkeypatch):
    monkeypatch.delenv("CHAT_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    cfg = load_chat_api_config()
    assert cfg.api_key == "legacy-key"
    assert cfg.is_complete()


def test_chat_api_to_env_uses_canonical_keys():
    env = chat_api_to_env(
        ChatApiConfig("k", "https://x", "m")
    )
    assert set(env.keys()) == {
        "CHAT_API_KEY",
        "CHAT_API_BASE_URL",
        "CHAT_API_MODEL",
    }
