from types import SimpleNamespace
import unittest

from wechat_group_bridge.models import BridgeSettings, IncomingGroupMessage
from wechat_group_bridge.policy import (
    IdleNudgePolicy, MessageGate, message_from_uia_item,
    message_from_wxauto, strip_pet_mention,
)


class BridgePolicyTests(unittest.TestCase):
    def setUp(self):
        self.settings = BridgeSettings(cooldown_seconds=15)
        self.gate = MessageGate(self.settings)

    def event(self, **changes):
        values = dict(
            group_name=self.settings.group_name,
            sender_name="小林",
            content="@师滔 这事咋办",
            message_id="m1",
        )
        values.update(changes)
        return IncomingGroupMessage(**values)

    def test_only_exact_group_and_explicit_mention_are_accepted(self):
        self.assertEqual(self.gate.check(self.event(group_name="另一个群"), now=20).reason, "different_group")
        self.assertEqual(self.gate.check(self.event(content="师滔在吗"), now=20).reason, "not_mentioned")
        accepted = self.gate.check(self.event(), now=20)
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.text, "这事咋办")

    def test_own_messages_empty_mentions_duplicates_and_parallel_replies_are_ignored(self):
        self.assertEqual(self.gate.check(self.event(is_self=True), now=20).reason, "own_message")
        self.assertEqual(self.gate.check(self.event(content="@师滔"), now=20).reason, "mention_only")
        self.assertTrue(self.gate.check(self.event(), now=20).accepted)
        self.assertEqual(self.gate.check(self.event(message_id="m2"), now=21).reason, "reply_in_progress")
        self.gate.set_in_flight(False)
        self.assertEqual(self.gate.check(self.event(), now=40).reason, "duplicate")

    def test_cooldown_blocks_a_second_message_after_first_reply_finishes(self):
        self.assertTrue(self.gate.check(self.event(), now=100).accepted)
        self.gate.set_in_flight(False)
        self.assertEqual(self.gate.check(self.event(message_id="m2"), now=114).reason, "cooldown")
        self.assertTrue(self.gate.check(self.event(message_id="m2"), now=115).accepted)

    def test_message_adapter_normalizes_full_width_at_and_detects_self(self):
        incoming = message_from_wxauto(
            SimpleNamespace(content="＠师滔：看看", sender="小林", local_id=7),
            object(),
            self.settings.group_name,
        )
        self.assertTrue(incoming.is_group_mention)
        self.assertEqual(incoming.content, "@师滔：看看")
        own = message_from_wxauto(
            type("SelfMessage", (), {"content": "＠师滔：忽略我", "sender": "师滔"})(),
            object(),
            self.settings.group_name,
        )
        self.assertTrue(own.is_self)

    def test_settings_default_off_and_round_trip(self):
        self.assertFalse(self.settings.listening_enabled)
        self.assertFalse(self.settings.auto_reply_enabled)
        self.assertFalse(self.settings.idle_announcement_enabled)
        self.assertEqual(strip_pet_mention("@师滔：赶紧回话"), "赶紧回话")

    def test_idle_nudge_only_once_until_new_activity_and_never_before_twenty_minutes(self):
        policy = IdleNudgePolicy()
        policy.observe_activity(now=100)
        self.assertFalse(policy.is_due(now=100 + 19 * 60 + 59))
        self.assertTrue(policy.is_due(now=100 + 20 * 60))
        policy.mark_sent()
        self.assertFalse(policy.is_due(now=100 + 21 * 60))
        policy.observe_activity(now=1300)
        self.assertFalse(policy.is_still_quiet(now=1300 + 5))
        self.assertFalse(policy.is_due(now=1300 + 5))

    def test_pet_announcement_does_not_restart_idle_timer(self):
        policy = IdleNudgePolicy()
        policy.observe_activity(now=100)
        own = self.event(is_self=True)
        member = self.event(is_self=False)
        policy.observe_message(own, now=1100)
        self.assertTrue(policy.is_due(now=1300))
        policy.mark_sent()
        policy.observe_message(member, now=1400)
        self.assertFalse(policy.is_due(now=1400 + 20 * 60 - 1))

    def test_uia_message_owner_detection_fails_closed(self):
        class Item:
            window_text = lambda self: "@师滔 看看这个"
            element_info = SimpleNamespace(runtime_id=(1, 2, 3))

        incoming = message_from_uia_item(
            "window", Item(), "edit", SimpleNamespace(is_my_bubble=lambda *args: False), self.settings.group_name
        )
        self.assertEqual(incoming.message_id, "(1, 2, 3)")
        self.assertTrue(incoming.is_group_mention)
        uncertain = message_from_uia_item(
            "window", Item(), "edit", SimpleNamespace(is_my_bubble=lambda *args: (_ for _ in ()).throw(RuntimeError())),
            self.settings.group_name,
        )
        self.assertIsNone(uncertain.is_self)
        self.assertEqual(self.gate.check(uncertain, now=20).reason, "own_message")


if __name__ == "__main__":
    unittest.main()
