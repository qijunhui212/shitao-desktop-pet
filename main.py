"""AI Desktop Pet — Windows desktop companion."""

import sys
import traceback
from pathlib import Path


def _bootstrap_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = _bootstrap_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

os.chdir(ROOT)


def _show_fatal_error(msg: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, msg, "桌面宠物 · 启动失败", 0x10)
    except Exception:
        print(msg, file=sys.stderr)


def main() -> int:
    try:
        from dotenv import load_dotenv

        from config.paths import is_frozen

        env_path = ROOT / ".env"
        example = ROOT / ".env.example"
        if not env_path.is_file() and example.is_file():
            env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        load_dotenv(env_path)

        from config.pack_discovery import reconcile_character_pack

        result = reconcile_character_pack(write_env=True)
        if result and result.updated_env:
            load_dotenv(env_path, override=True)

        from PySide6.QtWidgets import QApplication

        qt = QApplication(sys.argv)

        from app.character_picker import run_startup_character_selection

        if "--wechat-start" not in sys.argv and not run_startup_character_selection():
            return 0

        from app.application import DesktopPetApp

        app = DesktopPetApp()
        if "--wechat-start" in sys.argv:
            from PySide6.QtCore import QTimer
            def start_requested_bridge():
                app.open_wechat_bridge()
                app._start_wechat_bridge(app._wechat_settings)
            QTimer.singleShot(1000, start_requested_bridge)
        code = app.run()
        return code if code is not None else 0
    except ImportError as e:
        if getattr(sys, "frozen", False):
            _show_fatal_error(
                f"依赖加载失败：{e}\n\n"
                "请重新下载完整安装包，或安装 VC++ 运行库：\n"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
        else:
            _show_fatal_error(
                f"依赖加载失败：{e}\n\n"
                "【常见原因】用了 Anaconda / Python 3.13 创建虚拟环境。\n\n"
                "请双击运行项目里的 setup_env.bat\n"
                "（会用 Python 3.12 重建 .venv 并安装 PySide6）\n\n"
                "或手动：\n"
                "  1. 删除 .venv 文件夹\n"
                "  2. py -3.12 -m venv .venv\n"
                "  3. .venv\\Scripts\\activate\n"
                "  4. pip install -r requirements.txt\n\n"
                "仍失败请安装 VC++ 运行库：\n"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
        return 1
    except Exception:
        _show_fatal_error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
