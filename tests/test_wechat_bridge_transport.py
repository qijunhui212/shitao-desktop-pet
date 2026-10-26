import sys
import types
import unittest
from types import SimpleNamespace

from wechat_group_bridge.models import BridgeSettings
from wechat_group_bridge.transport import PyweixinGroupTransport


class FakeElement:
    def __init__(self, text="", rid="1"):
        self.text = text
        self.element_info = SimpleNamespace(runtime_id=rid)
        self.was_clicked = False
        self.sent_text = None

    def window_text(self):
        return self.text

    def exists(self, timeout=0):
        return True

    def click_input(self):
        self.was_clicked = True

    def set_text(self, text):
        self.sent_text = text


class FakeDialog:
    def __init__(self, group="示例群"):
        self.title = FakeElement(group)
        self.rows = [FakeElement("旧消息", "old")]
        self.input = FakeElement()
        self.closed = False
        self.restored = False

    def child_window(self, **kwargs):
        if kwargs.get("control_type") == "Text":
            return self.title
        if kwargs.get("control_type") == "List":
            return FakeList(self.rows)
        return self.input

    def close(self):
        self.closed = True

    def restore(self):
        self.restored = True


class FakeList:
    def __init__(self, rows):
        self.rows = rows

    def exists(self, timeout=0):
        return True

    def children(self, control_type=None):
        return list(self.rows)


class FakeApi:
    def __init__(self, group="示例群"):
        self.dialog = FakeDialog(group)
        self.owner_args = None
        def is_my_bubble(*args):
            self.owner_args = args
            return False
        self.Tools = SimpleNamespace(
            is_group_chat=lambda window: True,
            is_my_bubble=is_my_bubble,
        )
        self.Lists = SimpleNamespace(FriendChatList={"title": "Messages", "control_type": "List"})
        self.Texts = SimpleNamespace(CurrentChatNameText={"control_type": "Text"})
        self.Edits = SimpleNamespace(InputEdit={"control_type": "Edit"})
        self.Navigator = SimpleNamespace(open_seperate_dialog_window=lambda **kwargs: self.dialog)


class TransportTests(unittest.TestCase):
    def test_only_new_visible_rows_are_emitted(self):
        api = FakeApi()
        transport = PyweixinGroupTransport(BridgeSettings(), api=api)
        transport.start()
        self.assertEqual(transport.poll(), [])
        api.dialog.rows.append(FakeElement("@师滔 看看", "new"))
        events = transport.poll()
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].is_group_mention)
        self.assertFalse(events[0].is_self)
        self.assertEqual(api.owner_args, (api.dialog, api.dialog.rows[-1], api.dialog.input))
        self.assertEqual(transport.poll(), [])

    def test_exact_group_mismatch_fails_and_does_not_send(self):
        api = FakeApi("另一个群")
        transport = PyweixinGroupTransport(BridgeSettings(), api=api)
        with self.assertRaisesRegex(RuntimeError, "完全一致"):
            transport.start()
        self.assertTrue(api.dialog.closed)

    def test_send_rechecks_group_header(self):
        api = FakeApi()
        transport = PyweixinGroupTransport(BridgeSettings(), api=api)
        transport.start()
        api.dialog.title.text = "另一个群"
        with self.assertRaisesRegex(RuntimeError, "未发送"):
            transport.send("不会误发")

    def test_send_uses_exact_group_input(self):
        api = FakeApi()
        transport = PyweixinGroupTransport(BridgeSettings(), api=api)
        transport.start()
        fake_pyautogui = types.ModuleType("pyautogui")
        fake_pyautogui.hotkey = lambda *args: None
        old = sys.modules.get("pyautogui")
        sys.modules["pyautogui"] = fake_pyautogui
        try:
            transport.send("hello")
        finally:
            if old is None:
                sys.modules.pop("pyautogui", None)
            else:
                sys.modules["pyautogui"] = old
        self.assertEqual(api.dialog.input.sent_text, "hello")
        self.assertTrue(api.dialog.restored)


if __name__ == "__main__":
    unittest.main()
