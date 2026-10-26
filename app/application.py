import sys
import time
import random
from brain import stickers
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt, QThread, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QSystemTrayIcon

from app.chat_dialog import ChatDialog
from app.speech_bubble import SpeechBubbleLabel
from app.reminders_dialog import RemindersDialog
from app.icon_util import make_tray_icon
from app.tray import TrayIcon
from app.window import PetWindow
from app.workers import ChatWorker
from brain.chat import ChatService
from brain.prompts import resolve_persona_kind
from config.pet_mode import is_survival_mode, mode_display_name
from config.settings import (
    APP_ICON_PATH,
    PET_HEIGHT,
    PET_NAME,
    PET_WIDTH,
    SHOW_SPLASH,
    SPLASH_MS,
    USER_NAME,
    get_character_display_name,
)
from memory.store import MemoryStore
from pet.character_assets import CharacterAssets
from pet.controller import PetController
from pet.vitality import PetVitality
from reminder.service import ReminderService


class DesktopPetApp(QObject):
    def _save_chat_memory(self):
        from app.event_memory_dialog import EventMemoryDialog
        dialog = self.chat_dialog
        selected = dialog.input.textCursor().selectedText().replace('\u2029', '\n')
        draft = selected or dialog.input.toPlainText().strip()
        history = self.memory.recent_chats(30)
        if dialog._last_sent and not any(m['role']=='user' and m['content']==dialog._last_sent for m in history):
            history.append({'role':'user','content':dialog._last_sent})
        editor = EventMemoryDialog(dialog,draft=draft,history=history)
        if editor.exec() and editor.saved_card:
            text = '这条记忆已经存在。' if editor.duplicate else '已存入知识库，下次聊到相关话题就能检索。'
            self.reply_bubble.show_message(text)

    def _manage_chat_memories(self):
        from app.event_memory_dialog import EventMemoryManager
        EventMemoryManager(self.chat_dialog).exec()

    def _import_companion_memory(self):
        import json
        from config.paths import app_root
        filename, _ = QFileDialog.getOpenFileName(self.chat_dialog, '导入整理后的 memory.json', '', 'JSON (*.json)')
        if not filename:
            return
        try:
            source = Path(filename)
            if source.stat().st_size > 1024 * 1024:
                raise ValueError('请选择整理后的 memory.json，大小不超过 1MB')
            data = json.loads(source.read_text(encoding='utf-8-sig'))
            if data.get('schema_version') != 1 or not isinstance(data.get('profile'), str) or not isinstance(data.get('cards'), list):
                raise ValueError('记忆格式不正确')
            target = app_root() / 'data' / 'persona' / 'memory.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(target)
            self.reply_bubble.show_message(f'记住了，导入了 {len(data["cards"])} 条事件记忆。')
        except Exception as exc:
            QMessageBox.warning(self.chat_dialog, '导入失败', str(exc))

    def __init__(self):
        super().__init__()
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        existing = QApplication.instance()
        if existing is not None:
            self.qt_app = existing
        else:
            self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setApplicationName("Desktop Pet")
        self._splash = None
        self._startup_done = False
        if APP_ICON_PATH.is_file():
            self.qt_app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(
                None,
                "桌面宠物",
                "系统托盘不可用，无法在任务栏右下角显示图标。\n请检查 Windows 通知区域设置。",
            )

        self.memory = MemoryStore()
        if USER_NAME and not self.memory.get_user_name():
            self.memory.set_user_name(USER_NAME)
        display_name = get_character_display_name()
        if display_name:
            self.memory.set_pet_name(display_name)
        elif PET_NAME and not self.memory.get_pet_name():
            self.memory.set_pet_name(PET_NAME)

        persona = resolve_persona_kind()
        prev_persona = self.memory.get_profile("persona_kind", "")
        if prev_persona and prev_persona != persona:
            self.memory.clear_chats()
        elif not prev_persona and persona == "dog" and self.memory.recent_chats(1):
            self.memory.clear_chats()
        self.memory.set_profile("persona_kind", persona)

        self.chat = ChatService(self.memory)
        self.reminders = ReminderService(on_trigger=self._on_reminder)
        self.reminders.load_pending_jobs()

        self.character = CharacterAssets()
        use_sprites = self.character.is_ready
        w = self.character.width if use_sprites else PET_WIDTH
        h = self.character.height if use_sprites else PET_HEIGHT
        self.controller = PetController(w, h, walk_enabled=not use_sprites)
        self._survival_mode = is_survival_mode()
        self.vitality = PetVitality(self.memory, enabled=self._survival_mode)
        self._food_window = None

        self.window = PetWindow(
            self.controller,
            character=self.character if use_sprites else None,
            on_open_chat=self.open_chat,
            on_pack_dropped=self.import_pack_from_folder,
            on_spawn_food=self._spawn_food if self._survival_mode else None,
            on_advance_hour=self._advance_one_hour if self._survival_mode else None,
            survival_mode=self._survival_mode,
        )
        if self._survival_mode:
            self.vitality.hp_changed.connect(self.window.update_hp)
            self.vitality.starved_changed.connect(self._on_starved_changed)
            self.window.update_hp(
                self.vitality.hp,
                self.vitality.hp_max,
                starved=self.vitality.is_starved,
            )
            if self.vitality.is_starved:
                self._on_starved_changed(True)

        self._pet_name = self._resolve_pet_name()
        self.reply_bubble = SpeechBubbleLabel(self.window)
        self.window.pickup.retort.connect(self._show_drop_retort)
        self.window.pickup.started.connect(self.reply_bubble.hide)
        self._pending_form = None
        self.window.on_switch_form = self.switch_form
        self.character.action_finished.connect(self._finish_form_transition)
        self.chat_dialog: ChatDialog | None = None

        self.tray = TrayIcon(self)
        self.tray.show()
        self._update_tray_tooltip()

        self._chat_thread = None
        self._chat_worker = None
        self._chat_cancel_flag = [False]
        from config.paths import app_root
        from wechat_group_bridge.models import BridgeSettings
        self._wechat_session_id = 0
        self._wechat_settings_path = app_root() / "data" / "wechat_bridge.json"
        self._wechat_settings = BridgeSettings.load(self._wechat_settings_path)
        self._wechat_runtime = None
        self._wechat_dialog = None
        self._wechat_reply_engine = None
        self._wechat_reply_active = False
        self._wechat_reply_mode_idle = False
        self._wechat_reply_thread = None
        self._wechat_reply_worker = None
        self._wechat_cancel_event = None
        self._wechat_pending_message = None
        self._wechat_last_error = ""
        self._wechat_memory_timer = QTimer(self)
        self._wechat_memory_timer.timeout.connect(self._refresh_wechat_memory_status)
        self._wechat_memory_timer.start(10000)
        from wechat_group_bridge.policy import IdleNudgePolicy
        self._wechat_idle_policy = IdleNudgePolicy()
        self._sticker_settings = stickers.settings()
        self._last_user_activity = time.monotonic()
        self._last_idle_sticker = None
        self._last_idle_costume = float('-inf')
        from brain.proactive import ProactiveState
        self._proactive = ProactiveState()
        self._next_idle_sticker = time.monotonic()+random.uniform(75,150)
        self._idle_sticker_timer = QTimer(self)
        self._idle_sticker_timer.timeout.connect(self._maybe_idle_sticker)
        self._idle_sticker_timer.start(5000)

    def open_wechat_bridge(self) -> None:
        from wechat_group_bridge.dialog import WechatBridgeDialog
        from wechat_group_bridge.models import BridgeSettings

        if self._wechat_dialog is None:
            self._wechat_dialog = WechatBridgeDialog(
                self._wechat_settings,
                parent=self.chat_dialog,
            )
            self._wechat_dialog.start_requested.connect(self._start_wechat_bridge)
            self._wechat_dialog.stop_requested.connect(self._stop_wechat_bridge)
            self._wechat_dialog.view_memory_requested.connect(self._view_wechat_memories)
        self._refresh_wechat_memory_status()
        self._wechat_dialog.show()
        self._wechat_dialog.raise_()
        self._wechat_dialog.activateWindow()

    def _refresh_wechat_memory_status(self) -> None:
        if not self._wechat_dialog:
            return
        from wechat_group_bridge.group_memory import GroupMemoryStore, default_path, local_time
        try:
            stats = GroupMemoryStore().stats(self._wechat_settings.group_name) if default_path().exists() else {'pending': 0, 'memories': 0, 'scopes': []}
            running = bool(self._wechat_runtime and self._wechat_runtime.is_running)
            parts = [f"已整理 {stats['memories']} 条记忆 · 待整理 {stats['pending']} 条消息"]
            if running and self._wechat_settings.hourly_memory_enabled:
                scopes = stats['scopes']
                if any(item['active_run'] and time.time()-item['last_attempt'] < 120 for item in scopes):
                    parts.append('正在后台整理…')
                elif scopes:
                    parts.append('下次整理：' + local_time(min(item['next_due'] for item in scopes)))
                else:
                    parts.append('收到第一条新消息后开始按小时整理')
                error = self._wechat_runtime.memory_error or next((item['last_error'] for item in scopes if item['last_error']), '')
                if error: parts.append(error)
            else:
                parts.append('收集和整理已暂停，已有记忆仍可回忆')
            successes = [item['last_success'] for item in stats['scopes'] if item['last_success']]
            if successes: parts.append('最近完成：' + local_time(max(successes)))
            self._wechat_dialog.memory_status.setText('\n'.join(parts))
        except Exception:
            self._wechat_dialog.memory_status.setText('暂时无法读取群记忆状态，文字聊天仍可使用。')

    def _view_wechat_memories(self) -> None:
        from wechat_group_bridge.group_memory import GroupMemoryStore, default_path
        try:
            content = GroupMemoryStore().review_text(self._wechat_settings.group_name) if default_path().exists() else '还没有群记忆。开启监听后，将收集新消息并按小时整理。'
        except Exception:
            content = '群记忆文件暂时无法读取，请检查磁盘空间。'
        self._wechat_dialog.show_memories(content)

    def _start_wechat_bridge(self, settings) -> None:
        from wechat_group_bridge.qt_runtime import WechatBridgeRuntime
        from wechat_group_bridge.policy import MessageGate, IdleNudgePolicy

        if self._wechat_runtime and self._wechat_runtime.is_running:
            return
        self._wechat_session_id += 1
        self._wechat_settings = settings.validated()
        self._wechat_settings.save(self._wechat_settings_path)
        self._wechat_last_error = ""
        self._wechat_gate = MessageGate(self._wechat_settings)
        self._wechat_idle_policy = IdleNudgePolicy()
        self._wechat_reply_active = bool(self._wechat_reply_thread and self._wechat_reply_thread.isRunning())
        self._wechat_reply_engine = None
        self._wechat_runtime = WechatBridgeRuntime(self._wechat_settings, parent=self)
        runtime = self._wechat_runtime
        self._wechat_runtime.incoming.connect(lambda msg: self._on_wechat_message(msg) if self._wechat_runtime is runtime else None, Qt.ConnectionType.QueuedConnection)
        self._wechat_runtime.status.connect(lambda msg: self._on_wechat_bridge_status(msg) if self._wechat_runtime is runtime else None, Qt.ConnectionType.QueuedConnection)
        self._wechat_runtime.error.connect(lambda msg: self._on_wechat_bridge_error(msg) if self._wechat_runtime is runtime else None, Qt.ConnectionType.QueuedConnection)
        self._wechat_dialog.set_active(True)
        self._wechat_dialog.set_status("正在连接微信…")
        self._wechat_runtime.start()

    def _stop_wechat_bridge(self) -> None:
        self._wechat_session_id += 1
        runtime = self._wechat_runtime
        self._wechat_last_error = ""
        if self._wechat_cancel_event:
            self._wechat_cancel_event.set()
        self._wechat_pending_message = None
        stopped = True
        if runtime:
            stopped = runtime.stop(5000)
            if stopped and self._wechat_runtime is runtime:
                self._wechat_runtime = None
        if self._wechat_dialog:
            self._wechat_dialog.set_active(not stopped)
            self._wechat_dialog.set_status("已停止监听" if stopped else "正在停止微信监听，请稍候…")

    def _on_wechat_bridge_status(self, status: str) -> None:
        self._write_wechat_status("接入出错：" + self._wechat_last_error if status == "已停止监听" and self._wechat_last_error else status)
        if status == "已停止监听":
            self._wechat_session_id += 1
            if self._wechat_cancel_event:
                self._wechat_cancel_event.set()
            self._wechat_pending_message = None
            if self._wechat_dialog:
                if self._wechat_last_error:
                    self._wechat_dialog.set_status("接入出错：" + self._wechat_last_error)
                else:
                    self._wechat_dialog.set_status(status)
            if self._wechat_dialog:
                self._wechat_dialog.set_active(False)
            self._wechat_runtime = None
            self._wechat_reply_active = False
            return
        if self._wechat_dialog:
            self._wechat_dialog.set_status(status)

    def _write_wechat_status(self, status: str) -> None:
        import json
        try:
            path = self._wechat_settings_path.with_name("wechat_bridge_status.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"status": status, "updated_at": time.time(), "backend": "native-database",
                "last_event": getattr(self, '_wechat_last_event', None)}, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            pass

    def _on_wechat_bridge_error(self, message: str) -> None:
        self._write_wechat_status("接入出错：" + message)
        self._wechat_last_error = message
        if self._wechat_dialog:
            self._wechat_dialog.set_status("接入出错：" + message)
        self._wechat_reply_active = False

    def _on_wechat_message(self, message) -> None:
        from wechat_group_bridge.models import IncomingGroupMessage
        from wechat_group_bridge.policy import is_pet_mentioned
        if not isinstance(message, IncomingGroupMessage):
            return
        if message.group_name.strip() != self._wechat_settings.group_name:
            return
        self._ensure_wechat_reply_engine().observe_message(message)
        self._wechat_idle_policy.observe_message(message)
        is_mention = is_pet_mentioned(message)
        self._wechat_last_event = {'message_id': message.message_id, 'is_self': message.is_self,
            'mentioned': is_mention, 'account_target_checked': message.mention_targets_known}
        if self._wechat_reply_active:
            if self._wechat_settings.auto_reply_enabled and is_mention:
                self._wechat_pending_message = message
            if self._wechat_reply_mode_idle:
                if self._wechat_cancel_event:
                    self._wechat_cancel_event.set()
            return
        if not self._wechat_settings.auto_reply_enabled:
            return
        if not self.chat.available:
            if self._wechat_dialog:
                self._wechat_dialog.set_status("聊天 API 未配置；群监听仍在运行，但不能回复。")
            return
        result = self._wechat_gate.check(message)
        self._wechat_last_event['gate'] = result.reason
        if not result.accepted:
            if is_mention:
                reason = {'own_message': '本账号发出的消息不触发回复', 'mention_only': '只收到 @，没有问题正文',
                    'cooldown': '回复间隔中，请稍候再发一条', 'duplicate': '这条消息已经处理过'}.get(result.reason, result.reason)
                self._on_wechat_bridge_status('已收到 @ · ' + reason)
            return
        self._on_wechat_bridge_status('已识别 @ · 师滔正在生成回复…')
        self._wechat_reply_active = True
        self._wechat_reply_mode_idle = False
        self._wechat_gate.set_in_flight(True)
        self._run_wechat_reply(message, result.text)

    def _ensure_wechat_reply_engine(self):
        if self._wechat_reply_engine is None:
            from wechat_group_bridge.reply import GroupReplyEngine
            from brain.chat import ChatService
            memory = self.memory
            self._wechat_reply_engine = GroupReplyEngine(lambda: ChatService(memory))
        return self._wechat_reply_engine

    def _run_wechat_reply(self, message, text: str, idle: bool = False) -> None:
        from wechat_group_bridge.qt_reply import GroupReplyWorker, GroupReplyRelay
        from wechat_group_bridge.models import IncomingGroupMessage
        from threading import Event
        if self._wechat_reply_thread and self._wechat_reply_thread.isRunning():
            return
        if idle:
            account_id, group_id = self._wechat_runtime.memory_scope if self._wechat_runtime else ('', '')
            worker_message = IncomingGroupMessage(
                group_name=self._wechat_settings.group_name,
                sender_name="",
                content="",
                message_id="quiet-period",
                account_id=account_id,
                group_id=group_id,
            )
        else:
            worker_message = message
        self._wechat_reply_worker = GroupReplyWorker(
            self._ensure_wechat_reply_engine(),
            worker_message,
            text,
            cancel_event=Event(),
            idle=idle,
        )
        self._wechat_cancel_event = self._wechat_reply_worker._cancel_event
        self._wechat_reply_mode_idle = idle
        self._wechat_reply_thread = QThread(self)
        self._wechat_reply_worker.moveToThread(self._wechat_reply_thread)
        self._wechat_reply_thread.started.connect(self._wechat_reply_worker.run)
        session_id = self._wechat_session_id
        relay = GroupReplyRelay(self, session_id)
        self._wechat_reply_worker.finished.connect(relay.finished, Qt.ConnectionType.QueuedConnection)
        self._wechat_reply_worker.failed.connect(relay.failed, Qt.ConnectionType.QueuedConnection)
        self._wechat_reply_worker.finished.connect(self._wechat_reply_thread.quit)
        self._wechat_reply_worker.failed.connect(self._wechat_reply_thread.quit)
        self._wechat_reply_thread.finished.connect(self._wechat_reply_worker.deleteLater)
        self._wechat_reply_thread.finished.connect(relay.deleteLater)
        self._wechat_reply_thread.finished.connect(self._on_wechat_reply_thread_finished)
        self._wechat_reply_thread.finished.connect(self._wechat_reply_thread.deleteLater)
        self._wechat_reply_thread.start()

    def _on_wechat_reply_thread_finished(self) -> None:
        self._wechat_reply_thread = None
        self._wechat_reply_worker = None
        self._wechat_reply_active = False
        self._wechat_reply_mode_idle = False
        self._wechat_cancel_event = None
        self._process_pending_wechat_message()

    def _on_wechat_reply_finished(self, message, text: str, idle: bool) -> None:
        should_send = (not self._wechat_cancel_event or not self._wechat_cancel_event.is_set()) and (not idle or self._wechat_idle_policy.is_still_quiet())
        if should_send and self._wechat_runtime and self._wechat_runtime.is_running:
            self._wechat_runtime.send(text)
        if hasattr(self, "_wechat_gate"):
            self._wechat_gate.set_in_flight(False)

    def _on_wechat_reply_failed(self, _message, error: str, _idle: bool) -> None:
        self._write_wechat_status('回复失败：' + error)
        if hasattr(self, "_wechat_gate"):
            self._wechat_gate.set_in_flight(False)
        if self._wechat_dialog:
            self._wechat_dialog.set_status("回复失败：" + error)

    def _process_pending_wechat_message(self) -> None:
        message, self._wechat_pending_message = self._wechat_pending_message, None
        if message is not None and self._wechat_runtime and self._wechat_runtime.is_running:
            self._on_wechat_message(message)

    def _maybe_wechat_idle_message(self) -> None:
        if not (self._wechat_runtime and self._wechat_runtime.is_running):
            return
        if not self._wechat_settings.idle_announcement_enabled:
            return
        if self._wechat_reply_active or not self.chat.available:
            return
        if self._wechat_idle_policy.is_due():
            self._wechat_idle_policy.mark_sent()
            self._wechat_reply_active = True
            self._run_wechat_reply(None, "", idle=True)

    def _show_drop_retort(self, text):
        if not self._chat_thread:
            self.reply_bubble.show_message(text)

    def _resolve_pet_name(self) -> str:
        return get_character_display_name() or self.memory.get_pet_name() or PET_NAME

    def _refresh_pet_display_name(self) -> None:
        name = self._resolve_pet_name()
        self._pet_name = name
        self.memory.set_pet_name(name)
        if self.chat_dialog:
            self.chat_dialog.set_pet_name(name)

    def _warn_character_pack_mismatch(self) -> None:
        """多包且无法自动匹配时提示用户选择。"""
        from config.character_config import CHARACTER_PACK, resolve_character_dir
        from config.pack_discovery import (
            character_library_root,
            list_pack_folder_names,
            reconcile_character_pack,
        )

        if resolve_character_dir() is not None:
            return
        result = reconcile_character_pack(write_env=True)
        if result and result.reason in ("ok", "renamed", "single_fallback"):
            from config.env_update import reload_config_modules

            reload_config_modules()
            return
        lib = character_library_root()
        if not lib.is_dir():
            return
        available = list_pack_folder_names()
        hint = (
            f"无法自动匹配形象包（当前配置 CHARACTER_PACK={CHARACTER_PACK!r}）。\n\n"
            "请任选其一：\n"
            "· 托盘「切换形象」选择文件夹\n"
            "· 确认 形象/ 下文件夹名与立绘、人设.txt 在同一目录\n\n"
        )
        if available:
            hint += "当前形象/ 下的文件夹：\n" + "\n".join(
                f"  · {n}" for n in available
            )
        QTimer.singleShot(
            800,
            lambda: QMessageBox.warning(None, "请选择形象包", hint),
        )

    def _on_reminder(self, rid: int, title: str) -> None:
        self.tray.notify("提醒", f"{title}")
        if self.chat_dialog and self.chat_dialog.isVisible():
            self.chat_dialog.append_pet(f"⏰ 提醒到啦：{title}")

    def open_chat(self) -> None:
        pet_name = self._resolve_pet_name()
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(pet_name)
            self.chat_dialog.user_name_changed.connect(self._save_user_name)
            self.chat_dialog.set_user_name(self.memory.get_user_name())
            self.chat_dialog.message_sent.connect(self._on_user_message)
            self.chat_dialog.sticker_settings_changed.connect(self._set_sticker_settings)
            self.chat_dialog.stop_requested.connect(self._stop_chat)
            self.chat_dialog.import_memory_requested.connect(self._import_companion_memory)
            self.chat_dialog.save_memory_requested.connect(self._save_chat_memory)
            self.chat_dialog.manage_memory_requested.connect(self._manage_chat_memories)
            self.chat_dialog.reply_text.connect(self.reply_bubble.show_message)
            self.chat_dialog.reply_chunk.connect(self.reply_bubble.append_token)
            self.chat_dialog.reply_started.connect(self.reply_bubble.start_reply)
            self.chat_dialog.reply_finished.connect(self.reply_bubble.finish_reply)
        else:
            self.chat_dialog.set_pet_name(pet_name)
        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()

    def center_pet(self) -> None:
        self.controller.center_on_screen()
        self.tray.notify("桌面宠物", "已移到当前屏幕中央。")

    def _spawn_food(self) -> None:
        if not self._survival_mode:
            return
        from app.desktop_spawn import random_desktop_position
        from app.food_item import FoodItemWindow
        from pet.vitality_art import random_food_kind

        if self._food_window is not None:
            try:
                self._food_window.close()
            except RuntimeError:
                pass
            self._food_window = None

        kind = random_food_kind()
        food_size = 44

        def on_fed() -> None:
            self._food_window = None
            ok, msg, delta = self.vitality.try_feed()
            if ok:
                self.window.update_hp(
                    self.vitality.hp,
                    self.vitality.hp_max,
                    self.vitality.is_starved,
                )
                self.window.show_feed_bonus(
                    delta,
                    hp=self.vitality.hp,
                    starved=self.vitality.is_starved,
                )
                self._update_tray_tooltip(msg)

        pos = random_desktop_position(
            food_size,
            food_size,
            avoid=self.window,
        )
        self._food_window = FoodItemWindow(
            pos,
            kind,
            pet_window=self.window,
            on_fed=on_fed,
        )

    def _advance_one_hour(self) -> None:
        if not self._survival_mode:
            return
        ok, msg, delta = self.vitality.advance_hours(1.0)
        if ok:
            self.window.show_hp_delta(
                delta,
                hp=self.vitality.hp,
                starved=self.vitality.is_starved,
            )
        self._update_tray_tooltip(msg)

    def _on_starved_changed(self, starved: bool) -> None:
        self.window.set_starved(starved)
        if starved:
            name = self._resolve_pet_name()
            self._update_tray_tooltip(
                f"{name} 已饿死 · 右键「生成食物」，拖给骷髅喂满 3 次复活"
            )
        else:
            self._update_tray_tooltip("复活啦！")

    def _update_tray_tooltip(self, status: str | None = None) -> None:
        name = self._pet_name or "桌宠"
        lines = [f"桌面宠物 · {name}"]
        if self._survival_mode:
            lines.append(self.vitality.hp_label())
            if status:
                lines.append(status)
        else:
            lines.append(mode_display_name())
        self.tray.setToolTip("\n".join(lines))

    def pick_and_import_pack(self) -> None:
        from pet.pack_drop import character_library_root

        start = str(character_library_root())
        folder = QFileDialog.getExistingDirectory(
            None,
            "选择形象文件夹（内含 PNG / GIF）",
            start,
        )
        if folder:
            self.import_pack_from_folder(Path(folder))

    def import_pack_from_folder(self, source: Path) -> None:
        from config.env_update import reload_config_modules, update_env_file
        from pet.pack_drop import (
            character_library_root,
            install_pack,
            resolve_drop_path,
        )

        src = Path(source)
        resolved, kind = resolve_drop_path(src)
        if not resolved:
            self.tray.notify(
                "导入失败",
                "请拖入：\n"
                "· 形象文件夹（PNG/GIF + 可选 persona.txt 人设）\n"
                "· 或一张横向图集 PNG（透明底横排）",
            )
            return

        lib = character_library_root()
        pack_name_hint = resolved.stem if kind == "image" else resolved.name
        dest_hint = lib / pack_name_hint
        if dest_hint.exists():
            ok = QMessageBox.question(
                None,
                "覆盖形象",
                f"「{pack_name_hint}」已存在，是否覆盖并切换为该形象？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ok != QMessageBox.StandardButton.Yes:
                return

        installed = install_pack(src, overwrite=True)
        if not installed:
            self.tray.notify("导入失败", "无法复制到形象目录，请检查路径与权限。")
            return

        _dir, pack_name, slice_count = installed
        from brain.prompts import resolve_persona_kind
        from config.pack_discovery import _write_pack_env, compute_pack_signature
        from pet.pack_prompt import find_pack_prompt_file

        sig = compute_pack_signature(_dir)
        _write_pack_env(pack_name, sig)
        reload_config_modules()
        self._refresh_pet_display_name()

        persona = resolve_persona_kind()
        prev_pack = self.memory.get_profile("active_pack", "")
        prev_persona = self.memory.get_profile("persona_kind", "")
        if prev_pack != pack_name or prev_persona != persona:
            self.memory.clear_chats()
        self.memory.set_profile("persona_kind", persona)
        self.memory.set_profile("active_pack", pack_name)

        if self.character.reload():
            self.controller.set_walk_enabled(False)
            self.window._on_size(self.character.width, self.character.height)
            self.tray.setIcon(make_tray_icon(self.character))
            if self._survival_mode and self.vitality.is_starved:
                self.window.set_starved(True)
            extra = ""
            if slice_count >= 2:
                extra = f"\n已从图集自动切分为 {slice_count} 个动作（动作1～动作{slice_count}）"
            prompt_file = find_pack_prompt_file(_dir)
            if prompt_file:
                extra += f"\n已绑定人设：{prompt_file.name}"
            self.tray.notify(
                "形象已更新",
                f"已导入「{pack_name}」{extra}\n路径：{lib / pack_name}",
            )
        else:
            self.tray.notify(
                "导入失败",
                f"文件夹已复制为「{pack_name}」，但未找到可用立绘（需要 .png 或 .gif）",
            )

    def clear_chat_history(self) -> None:
        ok = QMessageBox.question(
            None,
            "清空对话",
            "确定清空与宠物的聊天记录吗？\n（不影响名字记忆与待办提醒）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        self.memory.clear_chats()
        if self.chat_dialog:
            self.chat_dialog.append_pet("对话记录已清空，我们重新开始吧～")
        self.tray.notify("桌面宠物", "对话记录已清空。")

    def _apply_pet_max_height(self, height: int) -> bool:
        """Reload sprites at new CHARACTER_MAX_HEIGHT (preview or after save)."""
        import os

        from config.character_config import clamp_character_height
        from config.env_update import reload_config_modules

        h = clamp_character_height(height)
        os.environ["CHARACTER_MAX_HEIGHT"] = str(h)
        reload_config_modules()
        if not self.character.reload():
            return False
        self.controller.set_walk_enabled(False)
        self.window._on_size(self.character.width, self.character.height)
        if self._survival_mode and self.vitality.is_starved:
            self.window.set_starved(True)
        return True

    def open_settings(self) -> None:
        from app.settings_dialog import run_settings_dialog
        from config.env_update import apply_settings, relaunch_app

        dlg = run_settings_dialog(
            parent=self.chat_dialog,
            on_height_preview=self._apply_pet_max_height,
        )
        if dlg is None:
            return
        apply_settings(
            survival_mode=dlg.survival_mode_selected(),
            chat_api=dlg.chat_api_config(),
            show_character_picker=dlg.show_character_picker(),
            max_height=dlg.max_height_selected(),
            survival_memory=dlg.survival_memory_selected(),
        )
        self.chat = ChatService(self.memory)
        if dlg.max_height_changed():
            self._apply_pet_max_height(dlg.max_height_selected())
        if dlg.mode_changed():
            QMessageBox.information(
                None,
                "设置已保存",
                "运行模式已更改，需要重新启动后生效。\n程序即将重启…",
            )
            relaunch_app()
            self.quit()
            return
        if dlg.survival_memory_changed() and dlg.survival_mode_selected():
            from config.env_update import reload_config_modules

            reload_config_modules()
            self.vitality.reload_state()
            self.window.update_hp(
                self.vitality.hp,
                self.vitality.hp_max,
                self.vitality.is_starved,
            )
            if self.vitality.is_starved:
                self._on_starved_changed(True)
        self._update_tray_tooltip()
        parts = ["设置已保存。"]
        if dlg.max_height_changed():
            parts.append(f"宠物大小：{dlg.max_height_selected()} px。")
        if dlg.survival_memory_changed():
            parts.append(
                "生存记忆已开启。"
                if dlg.survival_memory_selected()
                else "生存记忆已关闭（仅运行时扣 HP）。"
            )
        if self.chat.available:
            parts.append("聊天 API 已更新。")
        elif dlg.chat_api_config().is_complete():
            parts.append("聊天 API 已更新。")
        else:
            parts.append("未填写完整 API，聊天功能暂不可用。")
        self.tray.notify("桌面宠物", "".join(parts))

    def switch_character(self) -> None:
        from app.character_picker import run_switch_character_dialog
        from config.env_update import relaunch_app

        if not run_switch_character_dialog():
            return
        preset_title = ""
        from config.character_presets import detect_current_preset_id, preset_by_id

        pid = detect_current_preset_id()
        if pid:
            p = preset_by_id(pid)
            if p:
                preset_title = p.title
        self.tray.notify(
            "切换形象",
            f"已选择「{preset_title or '新形象'}」，正在重新启动…",
        )
        relaunch_app()
        self.quit()

    def switch_form(self, form: str) -> None:
        if self.window.pickup.busy:
            return
        from config.character_config import CHARACTER_PACK, CHARACTER_ROOT
        names = {'muscle':'像素肌肉小人','chubby':'像素微胖小人'}
        name = names.get(form)
        if self._pending_form or not name or name == CHARACTER_PACK:
            return
        if not (CHARACTER_ROOT/name).is_dir():
            self.reply_bubble.show_message('这个形态的素材还没安装。')
            return
        action = '11_transform_chubby' if form == 'chubby' else '12_transform_muscle'
        if self.character.play_action(action):
            self._pending_form = (name,action)
            self.character.transition_locked = True
            self.reply_bubble.hide()

    def _finish_form_transition(self, action: str) -> None:
        if not self._pending_form or self._pending_form[1] != action:
            return
        name,_ = self._pending_form
        self._pending_form = None
        from config.character_config import CHARACTER_ROOT
        from config.pack_discovery import _write_pack_env, compute_pack_signature
        from config.env_update import reload_config_modules
        from dotenv import load_dotenv
        from config.paths import app_root
        _write_pack_env(name,compute_pack_signature(CHARACTER_ROOT/name))
        load_dotenv(app_root()/'.env',override=True)
        reload_config_modules()
        self.character.reload()
        self.character.play_action('01_idle')
        self._refresh_pet_display_name()
        self.tray.setIcon(make_tray_icon(self.character))
        self._update_tray_tooltip()

    def show_help(self) -> None:
        from app.help_dialog import show_help_dialog
        from app.help_text import general_help_text

        show_help_dialog("使用说明", general_help_text(), parent=self.chat_dialog)

    def show_about(self) -> None:
        from app.help_dialog import show_help_dialog
        from app.help_text import about_text

        show_help_dialog("关于", about_text(), parent=self.chat_dialog)

    def show_reminders(self) -> None:
        pending = self.reminders.list_pending()
        dlg = RemindersDialog(
            pending,
            on_cancel=self.reminders.cancel,
            on_add=self._add_reminder_from_dialog,
            parent=self.chat_dialog,
        )
        dlg.exec()

    def _add_reminder_from_dialog(self) -> list[dict]:
        from app.add_reminder_dialog import AddReminderDialog

        dlg = AddReminderDialog(parent=self.chat_dialog)
        from PySide6.QtWidgets import QDialog

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return self.reminders.list_pending()
        rid = self.reminders.add(dlg.title(), dlg.trigger_at())
        self.tray.notify("提醒", f"已添加「{dlg.title()}」（#{rid}）")
        return self.reminders.list_pending()

    def _save_user_name(self, value):
        from brain.user_identity import clean_name
        try:
            name = clean_name(value)
            self.memory.set_user_name(name)
            self.memory.set_profile('user_name_confirmed','1')
            self.chat_dialog.set_user_name(name)
            self.chat_dialog._status.setText('称呼已保存：'+name)
        except (ValueError, OSError) as exc:
            self.chat_dialog._status.setText(str(exc))

    def _set_sticker_settings(self, value):
        try:
            stickers.save_settings(value)
            self._sticker_settings = value
            if not value['chat']:
                self.reply_bubble._set_sticker(None)
        except OSError:
            self.reply_bubble.show_message('表情设置保存失败，请检查本地目录权限。')

    def _maybe_idle_sticker(self):
        self._maybe_wechat_idle_message()
        now = time.monotonic()
        if now < self._next_idle_sticker or now-self._last_user_activity < 40:
            return
        if not self.window.isVisible() or self.reply_bubble.isVisible() or self._chat_thread or self._pending_form or not self.character.idle_for_sticker:
            return
        if self.chat_dialog and (self.chat_dialog._busy or self.chat_dialog.input.toPlainText().strip() or (self.chat_dialog.isVisible() and self.chat_dialog.input.hasFocus())):
            return
        self._next_idle_sticker = now+random.uniform(75,150)
        from brain.companion_persona import load_memory
        item = self._proactive.attempt(load_memory(),self._sticker_settings,now)
        if item:
            self.reply_bubble.show_message(item['text'],duration_ms=14000)
            self.memory.add_chat('assistant',item['text'])
            self._proactive.mark(item,now)
            import logging
            logging.getLogger(__name__).debug('Local idle speech: %s / %s',item['kind'],item['card_id'])
            return
        # A costume action can play even when idle pictures are turned off.
        if now-self._last_idle_costume >= 180 and random.random() < 0.35:
            if self.character.play_action('14_costume_laugh'):
                self._last_idle_costume = now
                if self._sticker_settings['idle']:
                    card = stickers.CATALOG.get('laugh')
                    if card:
                        self.reply_bubble._stickers_enabled = True
                        self.reply_bubble.show_message(card['idle'], sticker='laugh', duration_ms=10000)
                        self._last_idle_sticker = 'laugh'
                return
        if not self._sticker_settings['idle']:
            return
        card = stickers.idle_choice(self._last_idle_sticker, allow_costume=False)
        if card and self.character.play_action(card['action']):
            self.reply_bubble._stickers_enabled = True
            self.reply_bubble.show_message(card['idle'], sticker=card['id'], duration_ms=10000)
            self._last_idle_sticker = card['id']
            self._next_idle_sticker = now+random.uniform(75,150)

    def _on_user_message(self, text: str) -> None:
        self._last_user_activity = time.monotonic()
        self.reply_bubble._user_context = text
        self.reply_bubble._stickers_enabled = self._sticker_settings['chat']
        if not self.chat.available:
            self.chat_dialog.mark_failed()
            self.chat_dialog.set_busy(False)
            self.chat_dialog.append_pet(
                "聊天尚未配置。请打开托盘「设置」，填写 API Key、API 地址和模型（三项都需填写）。"
            )
            return
        if self._chat_thread and self._chat_thread.isRunning():
            self.chat_dialog.mark_failed()
            self.chat_dialog.append_pet("稍等，我还在想上一句…")
            return

        self._chat_cancel_flag[0] = False
        pending = self.reminders.list_pending()
        self._chat_worker = ChatWorker(
            self.chat, text, pending, self._chat_cancel_flag
        )
        self._chat_thread = QThread()
        self._chat_worker.moveToThread(self._chat_thread)
        self._chat_worker.token.connect(self._on_token)
        self._chat_worker.finished.connect(self._on_chat_finished)
        self._chat_worker.cancelled.connect(self._on_chat_cancelled)
        self._chat_worker.error.connect(self._on_chat_error)
        self._chat_worker.finished.connect(self._end_chat_ui)
        self._chat_worker.cancelled.connect(self._end_chat_ui)
        self._chat_worker.error.connect(self._end_chat_ui)
        self._chat_worker.finished.connect(self._cleanup_chat_thread)
        self._chat_worker.cancelled.connect(self._cleanup_chat_thread)
        self._chat_worker.error.connect(self._cleanup_chat_thread)
        self._chat_thread.started.connect(self._chat_worker.run)
        self._chat_thread.finished.connect(self._chat_thread.deleteLater)
        self._chat_worker.finished.connect(self._chat_worker.deleteLater)
        self._chat_worker.cancelled.connect(self._chat_worker.deleteLater)
        self._chat_worker.error.connect(self._chat_worker.deleteLater)
        self.chat_dialog.set_busy(True)
        self.chat_dialog.start_pet_reply()
        self._chat_thread.start()

    def _stop_chat(self) -> None:
        if self._chat_thread and self._chat_thread.isRunning():
            self._chat_cancel_flag[0] = True

    def _on_token(self, token: str) -> None:
        if self.chat_dialog:
            self.chat_dialog.append_pet_stream(token)

    def _end_chat_ui(self) -> None:
        if self.chat_dialog:
            self.chat_dialog.finish_pet_reply()
            self.chat_dialog.set_busy(False)

    def _on_chat_finished(self, display: str, reminder, memory) -> None:
        selected = getattr(self.chat, "last_sticker", None) if self._sticker_settings["chat"] else None
        self.reply_bubble.set_reply(display, sticker=selected)
        from brain.companion_persona import EmotionState
        action = stickers.CATALOG[selected]['action'] if selected in stickers.CATALOG else EmotionState.ACTIONS.get(self.chat.last_emotion,'01_idle')
        self.character.play_action(action)
        if memory:
            self.chat.apply_memory_action(memory)
            if memory.user_name and self.chat_dialog:
                self.chat_dialog.append_pet(f"（记住了，{memory.user_name}）")
        if reminder:
            err = self.chat.validate_reminder(reminder)
            if err:
                self.chat_dialog.append_pet(err)
            else:
                rid = self.reminders.add(reminder.title, reminder.datetime)
                self.chat_dialog.append_pet(
                    f"好，已设置提醒「{reminder.title}」— {reminder.datetime}（#{rid}）"
                )

    def _on_chat_cancelled(self, _partial: str) -> None:
        if self.chat_dialog:
            self.chat_dialog.mark_failed()
            self.chat_dialog.append_pet("（已停止生成）")

    def _on_chat_error(self, msg: str) -> None:
        if self.chat_dialog:
            self.chat_dialog.mark_failed()
            if msg.startswith(("API ", "无法连接", "请求", "模型", "访问被拒绝")):
                self.chat_dialog.append_pet(msg)
            else:
                self.chat_dialog.append_pet(f"出错了：{msg}")

    def _cleanup_chat_thread(self) -> None:
        if self._chat_thread and self._chat_thread.isRunning():
            self._chat_thread.quit()
            self._chat_thread.wait(3000)
        self._chat_thread = None
        self._chat_worker = None
        self._chat_cancel_flag[0] = False

    def quit(self) -> None:
        if getattr(self, "_quitting", False):
            return
        self._quitting = True

        self._idle_sticker_timer.stop()
        self._wechat_memory_timer.stop()
        self.vitality.stop()
        self.character.stop()
        self.controller.stop()
        if self._food_window is not None:
            try:
                self._food_window.close()
            except RuntimeError:
                pass
        self.window.hide()
        self.window.close()
        if self.chat_dialog:
            self.chat_dialog.hide()
            self.chat_dialog.close()
        self.tray.hide()
        self.tray.setVisible(False)

        self._cleanup_chat_thread()
        if self._wechat_cancel_event:
            self._wechat_cancel_event.set()
        self._stop_wechat_bridge()
        if self._wechat_reply_thread and self._wechat_reply_thread.isRunning():
            self._wechat_reply_thread.wait(2000)
        self.reminders.shutdown()
        self.memory.close()
        self.qt_app.quit()

    def _finish_startup(self) -> None:
        if self._startup_done:
            return
        self._startup_done = True
        if self._splash:
            self._splash.close()
            self._splash = None

        self.window.show_pet()
        if not self.memory.get_user_name():
            QTimer.singleShot(500, self.open_chat)
        name = self._resolve_pet_name()
        pack_hint = ""
        if self.character.is_ready and self.character.pack_path:
            pack_hint = f"\n形象：{self.character.pack_path}"
        self._update_tray_tooltip()
        self._warn_character_pack_mismatch()
        self.tray.notify(
            f"桌面宠物 · {name}",
            "宠物已在屏幕中央出现。\n"
            "我在任务栏右下角托盘（点 ^ 展开）— 右键可「使用说明」「设置」。\n"
            f"{mode_display_name()} · 双击聊天{pack_hint}"
            + (" · 宠物右键可喂食" if self._survival_mode else ""),
        )
        if not self.chat.available:
            QTimer.singleShot(
                2500,
                lambda: self.tray.notify(
                    "提示",
                    "未配置聊天 API：桌宠与提醒仍可用。\n"
                    "托盘「设置」填 Key/地址/模型；或「管理提醒」手动添加。",
                ),
            )

    def run(self) -> int:
        if SHOW_SPLASH and self.character.is_ready:
            from app.splash import SplashScreen

            pix = self.character.current_pixmap()
            self._splash = SplashScreen.from_character_pixmap(pix)
            if self._splash:
                self._splash.show_centered()
                QTimer.singleShot(SPLASH_MS, self._finish_startup)
                return self.qt_app.exec()

        self._finish_startup()
        return self.qt_app.exec()
