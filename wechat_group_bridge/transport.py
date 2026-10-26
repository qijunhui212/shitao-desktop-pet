from __future__ import annotations

from collections import deque

from .models import BridgeSettings, IncomingGroupMessage
from .policy import message_from_uia_item


class PyweixinGroupTransport:
    """UIA adapter for one independent, exact-name WeChat group window."""

    def __init__(self, settings: BridgeSettings, api=None):
        self.settings = settings.validated()
        self._api = api
        self._dialog = None
        self._chat_list = None
        self._input_edit = None
        self._tools = None
        self._lists = None
        self._texts = None
        self._edits = None
        self._seen: set[str] = set()
        self._seen_order: deque[str] = deque()

    def start(self) -> None:
        if self._api is None:
            try:
                from pyweixin.WeChatTools import Navigator, Tools
                from pyweixin.Uielements import Edits, Lists, Texts
            except ImportError as exc:
                raise RuntimeError(
                    "微信群接入的可选依赖尚未安装。请在桌宠目录运行："
                    "python -m pip install -r requirements-wechat-bridge.txt"
                ) from exc
            api = type("PyweixinApi", (), {
                "Navigator": Navigator, "Tools": Tools,
                "Edits": Edits, "Lists": Lists, "Texts": Texts,
            })
        else:
            api = self._api

        self._tools, self._lists, self._texts, self._edits = api.Tools, api.Lists, api.Texts, api.Edits
        self._dialog = api.Navigator.open_seperate_dialog_window(
            friend=self.settings.group_name,
            select=False,
            is_maximize=False,
            window_minimize=False,
            close_weixin=False,
        )
        if not self._tools.is_group_chat(self._dialog):
            self.stop()
            raise RuntimeError("打开的会话不是群聊，已停止监听。")
        if self._current_group() != self.settings.group_name:
            self.stop()
            raise RuntimeError("微信打开的群名称与设置不完全一致，已停止监听。")
        self._chat_list = self._dialog.child_window(**self._lists.FriendChatList)
        self._input_edit = self._dialog.child_window(**self._edits.InputEdit)
        if not self._chat_list.exists(timeout=1):
            self.stop()
            raise RuntimeError("找不到群消息列表，请确认微信已登录并打开目标群。")
        if not self._input_edit.exists(timeout=1):
            self.stop()
            raise RuntimeError("找不到微信输入框，无法安全识别消息归属。")
        # Snapshot currently visible rows so old messages never become events.
        for item in self._chat_list.children(control_type="ListItem"):
            self._remember(self._runtime_id(item))

    def poll(self) -> list[IncomingGroupMessage]:
        if self._dialog is None or self._chat_list is None:
            return []
        if self._current_group() != self.settings.group_name:
            raise RuntimeError("微信群窗口已切换或关闭，已停止监听以避免误发。")

        events: list[IncomingGroupMessage] = []
        for item in self._chat_list.children(control_type="ListItem"):
            runtime_id = self._runtime_id(item)
            if not runtime_id or runtime_id in self._seen:
                continue
            self._remember(runtime_id)
            message = message_from_uia_item(
                self._dialog, item, self._input_edit, self._tools, self.settings.group_name
            )
            if message is not None:
                events.append(message)
        return events

    def send(self, text: str) -> None:
        if not text or self._dialog is None:
            return
        if self._current_group() != self.settings.group_name:
            raise RuntimeError("微信群窗口已切换，未发送回复。")
        self._dialog.restore()
        input_edit = self._input_edit or self._dialog.child_window(**self._edits.InputEdit)
        if not input_edit.exists(timeout=1):
            raise RuntimeError("找不到微信输入框，未发送回复。")
        input_edit.click_input()
        input_edit.set_text(text[:1500])
        # This is the same send shortcut used by pyweixin for the focused chat input.
        from pyautogui import hotkey
        hotkey("alt", "s")

    def stop(self) -> None:
        dialog, self._dialog = self._dialog, None
        self._chat_list = None
        self._input_edit = None
        if dialog is not None:
            try:
                dialog.close()
            except Exception:
                pass

    def _current_group(self) -> str:
        if self._dialog is None:
            return ""
        title = self._dialog.child_window(**self._texts.CurrentChatNameText)
        if not title.exists(timeout=0.2):
            return ""
        return str(title.window_text() or "").strip()

    @staticmethod
    def _runtime_id(item) -> str:
        try:
            value = item.element_info.runtime_id
            return ".".join(map(str, value)) if isinstance(value, (tuple, list)) else str(value)
        except Exception:
            return ""

    def _remember(self, runtime_id: str) -> None:
        if not runtime_id or runtime_id in self._seen:
            return
        self._seen.add(runtime_id)
        self._seen_order.append(runtime_id)
        while len(self._seen_order) > 2048:
            self._seen.discard(self._seen_order.popleft())
