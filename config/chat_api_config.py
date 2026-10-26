"""OpenAI 兼容聊天 API（优先 CHAT_API_*，兼容 DEEPSEEK_* 旧变量名）。"""



from __future__ import annotations



import os

from dataclasses import dataclass



# 写入 .env 时使用；保存 API 时会从文件中移除旧名

CHAT_ENV_KEYS = ("CHAT_API_KEY", "CHAT_API_BASE_URL", "CHAT_API_MODEL")

LEGACY_CHAT_ENV_KEYS = ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL")



EXAMPLE_BASE_URLS = (

    "https://api.deepseek.com",

    "https://api.openai.com/v1",

    "http://127.0.0.1:11434/v1",

)

EXAMPLE_MODELS = (

    "deepseek-chat",

    "gpt-4o-mini",

    "gpt-4o",

    "qwen-plus",

    "llama3",

)





@dataclass(frozen=True)

class ChatApiConfig:

    api_key: str

    base_url: str

    model: str



    def is_complete(self) -> bool:

        return bool(

            self.api_key.strip()

            and self.base_url.strip()

            and self.model.strip()

        )





def _env_first(*keys: str) -> str:

    for key in keys:

        val = os.getenv(key, "").strip()

        if val:

            return val

    return ""





def load_chat_api_config() -> ChatApiConfig:

    return ChatApiConfig(

        api_key=_env_first("CHAT_API_KEY", "DEEPSEEK_API_KEY"),

        base_url=_env_first("CHAT_API_BASE_URL", "DEEPSEEK_BASE_URL"),

        model=_env_first("CHAT_API_MODEL", "DEEPSEEK_MODEL"),

    )





def chat_api_to_env(cfg: ChatApiConfig) -> dict[str, str]:

    return {

        "CHAT_API_KEY": cfg.api_key.strip(),

        "CHAT_API_BASE_URL": cfg.base_url.strip(),

        "CHAT_API_MODEL": cfg.model.strip(),

    }


