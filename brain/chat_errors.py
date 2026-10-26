"""User-facing messages for chat API failures."""

from __future__ import annotations


def friendly_chat_error(exc: BaseException) -> str:
    raw = str(exc).strip()
    lower = raw.lower()

    if "401" in lower or "authentication" in lower or "invalid api key" in lower:
        return (
            "API Key 无效或未授权。请在托盘「设置」中检查 Key，"
            "或在平台重新生成后保存。"
        )
    if "404" in lower and ("model" in lower or "not found" in lower):
        return (
            "模型不存在或当前地址不支持该模型。"
            "请在「设置」中核对模型名称（区分大小写）。"
        )
    if "connection" in lower or "connect" in lower or "network" in lower:
        return (
            "无法连接到 API 地址。请检查网络、API 地址是否完整"
            "（需含 https://，本地 Ollama 示例：http://127.0.0.1:11434/v1）。"
        )
    if "timeout" in lower or "timed out" in lower:
        return "请求超时，请稍后重试或换更快的模型。"
    if "429" in lower or "rate limit" in lower:
        return "请求过于频繁或额度不足，请稍后再试或检查账户余额。"
    if "403" in lower:
        return "访问被拒绝（403）。请检查 Key 权限或账户是否欠费。"
    if "502" in lower or "503" in lower or "bad gateway" in lower:
        return "API 服务暂时不可用，请稍后重试。"

    if len(raw) > 280:
        return raw[:280] + "…"
    return raw or "聊天请求失败，请检查「设置」中的 API 配置。"
