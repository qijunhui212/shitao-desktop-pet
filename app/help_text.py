"""Tray help / usage copy."""

from __future__ import annotations

from config.pet_mode import is_survival_mode
from config.version import APP_NAME, APP_VERSION


def general_help_text() -> str:
    lines = [
        "【在哪里找宠物】",
        "任务栏右下角点击 ^，找到「桌面宠物」托盘图标。",
        "",
        "【常用操作】",
        "· 双击宠物或托盘图标：打开聊天",
        "· 左键拖动：移动宠物（不超出当前屏幕）",
        "· 托盘「设置…」：运行模式、宠物大小滑块、聊天 API、启动向导",
        "· 托盘「切换形象」：更换立绘（会重启）",
        "· 拖文件夹到宠物上：导入新形象包",
        "",
        "【聊天 API】",
        "不配置也能用桌宠；要 AI 聊天需在「设置」填 Key、地址、模型三项。",
        "支持 DeepSeek、OpenAI、Ollama 等 OpenAI 兼容接口。",
        "",
        "【提醒】",
        "· 配置 API 后可在聊天里说「明天下午 3 点提醒我…」",
        "· 或托盘「管理提醒」→「添加提醒」手动创建",
    ]
    if is_survival_mode():
        lines.extend(["", survival_help_text()])
    return "\n".join(lines)


def survival_help_text() -> str:
    return "\n".join(
        [
            "【生存模式】",
            "· 顶部 12 格 HP，约每小时减 1 格",
            "· 右键宠物 →「生成食物」，把食物拖到宠物身上喂食",
            "· HP 归零会变成骷髅；再右键生成食物，喂满 3 次可复活",
            "· 设置里「生存记忆」：开启后退出程序也计时，久不打开会离线饿死",
            "· 关闭生存记忆：仅程序开着时扣 HP",
            "· 右键「加速一小时」：快进时间（方便测试）",
        ]
    )


def about_text() -> str:
    return (
        f"{APP_NAME}\n"
        f"版本 {APP_VERSION}\n\n"
        "Windows 透明桌宠 · 2D 形象 · OpenAI 兼容聊天\n"
        "生存模式 · 本地提醒与记忆\n\n"
        "开源协议：MIT"
    )
