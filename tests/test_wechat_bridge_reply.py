import unittest
from threading import Event, Thread

from wechat_group_bridge.models import BridgeSettings, IncomingGroupMessage
from wechat_group_bridge.reply import GroupReplyEngine


class FakeChat:
    def __init__(self):
        self.calls = []

    def chat_stream(self, prompt, reminders, **kwargs):
        self.calls.append((prompt, reminders, kwargs))
        return "师滔式回复", None, None


class ReplyTests(unittest.TestCase):
    def setUp(self):
        self.chat = FakeChat()
        self.engine = GroupReplyEngine(lambda: self.chat)
        self.message = IncomingGroupMessage(
            group_name=BridgeSettings().group_name,
            sender_name="小林",
            content="@师滔 回群里说话",
            message_id="event-1",
            is_group_mention=True,
        )

    def test_reply_uses_bounded_session_without_persisting_personal_chat(self):
        self.assertEqual(self.engine.reply(self.message, "回群里说话"), "师滔式回复")
        _prompt, reminders, kwargs = self.chat.calls[0]
        self.assertEqual(reminders, [])
        self.assertEqual(kwargs["session_history"], [])
        self.assertEqual(kwargs["conversation_user_name"], "")
        self.assertFalse(kwargs["persist_history"])
        self.assertFalse(kwargs["personalize_reply"])

    def test_all_new_group_messages_form_context_for_mention_reply(self):
        earlier = IncomingGroupMessage(
            group_name=self.message.group_name,
            sender_name="小陈",
            content="刚才说的健身房几点关门？",
            message_id="event-before",
        )
        self.engine.observe_message(earlier)
        self.assertEqual(self.chat.calls, [])
        self.engine.observe_message(self.message)
        self.engine.reply(self.message, "回群里说话")
        history = self.chat.calls[0][2]["session_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "小陈: 刚才说的健身房几点关门？")
        self.assertIn("小林", self.chat.calls[0][0])

    def test_context_is_bounded_to_latest_messages(self):
        engine = GroupReplyEngine(lambda: self.chat, history_limit=3)
        for index in range(5):
            engine.observe_message(IncomingGroupMessage(
                group_name=self.message.group_name,
                sender_name="群成员",
                content=f"消息 {index}",
                message_id=str(index),
            ))
        engine.idle_message(self.message.group_name)
        history = self.chat.calls[0][2]["session_history"]
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["content"], "群成员: 消息 2")

    def test_new_messages_can_be_observed_while_api_generation_is_running(self):
        started = Event()
        release = Event()

        class BlockingChat(FakeChat):
            def chat_stream(self, prompt, reminders, **kwargs):
                started.set()
                release.wait(2)
                return "完成", None, None

        chat = BlockingChat()
        engine = GroupReplyEngine(lambda: chat)
        worker = Thread(target=engine.idle_message, args=(self.message.group_name,))
        worker.start()
        self.assertTrue(started.wait(1))
        engine.observe_message(IncomingGroupMessage(
            group_name=self.message.group_name,
            sender_name="新成员",
            content="刚进群说的一句话",
            message_id="concurrent",
        ))
        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
