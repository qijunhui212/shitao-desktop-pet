import unittest
import zstandard
from wechat_group_bridge.mentions import match_mention
from wechat_group_bridge.models import BridgeSettings, IncomingGroupMessage
from wechat_group_bridge.policy import MessageGate, is_pet_mentioned


class MentionTests(unittest.TestCase):
    def event(self, text, target='wxid_bot', display='师小滔', compressed=True):
        xml = f'<msgsource><atuserlist><![CDATA[{target}]]></atuserlist></msgsource>'.encode()
        source = zstandard.ZstdCompressor().compress(xml) if compressed else xml
        mentioned, known, clean = match_mention(text, source, 4 if compressed else 0, 'wxid_bot', display)
        return IncomingGroupMessage(BridgeSettings().group_name, '测试成员', text, 'sample', False,
                                    mentioned, known, clean if mentioned else None)

    def test_real_wechat_nickname_and_compressed_target_list(self):
        for text, expected in [('@师小滔\u2005我萌吗', '我萌吗'), ('@师小滔\u2005你在干嘛', '你在干嘛')]:
            result = MessageGate(BridgeSettings()).check(self.event(text), now=20)
            self.assertTrue(result.accepted)
            self.assertEqual(result.text, expected)

    def test_changed_room_nickname_still_matches_same_account(self):
        message = self.event('@换了群昵称\u2005你好')
        self.assertTrue(is_pet_mentioned(message))
        self.assertEqual(MessageGate(BridgeSettings()).check(message, now=20).text, '你好')

    def test_different_account_named_shitao_does_not_trigger(self):
        message = self.event('@师滔\u2005你好', target='wxid_somebody_else')
        self.assertFalse(is_pet_mentioned(message))
        self.assertEqual(MessageGate(BridgeSettings()).check(message, now=20).reason, 'not_mentioned')

    def test_all_members_mention_does_not_trigger_individual_bot(self):
        self.assertFalse(is_pet_mentioned(self.event('@所有人\u2005你好', target='notify@all')))

    def test_mention_alone_does_not_request_completion(self):
        self.assertEqual(MessageGate(BridgeSettings()).check(self.event('@师小滔\u2005'), now=20).reason, 'mention_only')

    def test_multiple_targets_include_bot_and_keep_other_names(self):
        message = self.event('@师小滔\u2005@小明\u2005你们在干嘛', target='wxid_other, wxid_bot')
        result = MessageGate(BridgeSettings()).check(message, now=20)
        self.assertTrue(result.accepted)
        self.assertEqual(result.text, '@小明\u2005你们在干嘛')

    def test_manual_alias_is_supported_without_metadata(self):
        for text in ['@师小滔 你好', '＠师小滔：你好', '@师滔 你好']:
            mentioned, known, clean = match_mention(text, None, 0, 'wxid_bot', '师小滔')
            self.assertTrue(mentioned)
            self.assertFalse(known)
            self.assertEqual(clean, '你好')

    def test_similar_longer_name_is_not_a_literal_trigger(self):
        message = IncomingGroupMessage(BridgeSettings().group_name, '成员', '@师滔滔 你好')
        self.assertFalse(is_pet_mentioned(message))

    def test_xml_entity_is_not_expanded(self):
        xml = '<!DOCTYPE msgsource [<!ENTITY x "wxid_bot">]><msgsource><atuserlist>&x;</atuserlist></msgsource>'
        self.assertEqual(match_mention('普通消息', xml, 0, 'wxid_bot', '师小滔'), (False, False, '普通消息'))


if __name__ == '__main__': unittest.main()
