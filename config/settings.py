import os

from dotenv import load_dotenv

from config.paths import app_root, resolve_resource_path, resource_root

ROOT = app_root()
RESOURCE_ROOT = resource_root()
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "pet.db"

# 聊天 API 请用 config.chat_api_config.load_chat_api_config()

PET_NAME = os.getenv("PET_NAME", "槿棠")
USER_NAME = os.getenv("USER_NAME", "")

def get_character_display_name() -> str:
    """角色名字独立于外观；师滔的两种形态使用同一个名字。"""
    from config.character_config import CHARACTER_PACK

    pack = (CHARACTER_PACK or "").strip()
    if pack in ("像素肌肉小人", "像素微胖小人"):
        return "师滔"
    if pack:
        return pack
    return PET_NAME

# 形象配置见 config/character_config.py（CHARACTER_ROOT / CHARACTER_PACK）

_icon = RESOURCE_ROOT / "assets" / "app_icon.ico"
if not _icon.is_file():
    _icon = ROOT / "assets" / "app_icon.ico"
APP_ICON_PATH = _icon

_raw_icon_src = os.getenv("APP_ICON_SOURCE", "形象/银杰动漫形象/歪头.png").strip()
APP_ICON_SOURCE = str(resolve_resource_path(_raw_icon_src))
SHOW_SPLASH = os.getenv("SHOW_SPLASH", "1").strip().lower() not in ("0", "false", "no")
SPLASH_MS = int(os.getenv("SPLASH_MS", "1200"))
# 启动时显示形象选择窗口；0=跳过（仍可从托盘切换）
SHOW_CHARACTER_PICKER = os.getenv("SHOW_CHARACTER_PICKER", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)

# 无素材时的占位尺寸
PET_WIDTH = 128
PET_HEIGHT = 160
WALK_INTERVAL_MS = 40
WALK_SPEED = 2
