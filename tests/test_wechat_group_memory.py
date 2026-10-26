import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch, MagicMock

from wechat_group_bridge.models import BridgeSettings, IncomingGroupMessage
from wechat_group_bridge.group_memory import GroupMemoryStore, HOUR, recall_for_chat
from wechat_group_bridge.memory_summary import HourlyMemoryService
from wechat_group_bridge.reply import GroupReplyEngine

T = 1793000000
GROUP = '测试群'

def message(index=1, text='周六三点去操场打篮球', room='room', account='account', own=False):
    return IncomingGroupMessage(GROUP, '小林', text, str(index), is_self=own,
                                account_id=account, group_id=room, sender_id='person', sent_at=T+index)

def card(ids, text='小林约定周六三点在操场打篮球。', kind='plan'):
    return {'summary':text,'kind':kind,'participants':['小林'],'keywords':['篮球','操场'],'source_ids':ids}

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'memory.sqlite3'
        self.store = GroupMemoryStore(self.path)
    def tearDown(self): self.tmp.cleanup()
    def collect(self, *items):
        for item in items or (message(),): self.store.record(item,now=T)
    def finish(self, *, text=None, kind='plan', now=T+HOUR):
        batch=self.store.claim(GROUP,now=now)
        self.store.complete(batch,[card([batch['messages'][0]['id']],text or '小林约定周六三点在操场打篮球。',kind)],now=now)
        return batch

    def test_records_ordinary_messages_without_at_and_deduplicates(self):
        self.assertTrue(self.store.record(message(),now=T))
        self.assertFalse(self.store.record(message(),now=T))
        self.assertEqual(self.store.stats()['pending'],1)
    def test_requires_source_account_room_and_message_id(self):
        self.assertFalse(self.store.record(message(room=''),now=T))
        self.assertFalse(self.store.record(message(account=''),now=T))
        self.assertFalse(self.store.record(message(text=''),now=T))
    def test_due_after_hour_and_schedule_survives_restart(self):
        self.collect()
        restarted=GroupMemoryStore(self.path)
        self.assertIsNone(restarted.claim(GROUP,now=T+HOUR-1))
        batch=restarted.claim(GROUP,now=T+HOUR)
        self.assertEqual(len(batch['messages']),1)
        self.assertIsNone(GroupMemoryStore(self.path).claim(GROUP,now=T+HOUR+1))
    def test_one_atomic_budget_under_concurrent_schedulers(self):
        self.collect()
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda _: GroupMemoryStore(self.path).claim(GROUP,now=T+HOUR),range(2)))
        self.assertEqual(sum(result is not None for result in results),1)
    def test_no_messages_no_summarizer_call(self):
        summary=MagicMock()
        HourlyMemoryService(self.store,GROUP,summary).run_once(now=T+HOUR)
        summary.assert_not_called()
    def test_empty_hour_after_success_does_not_call_api(self):
        self.collect(); self.finish()
        summary=MagicMock()
        HourlyMemoryService(self.store,GROUP,summary).run_once(now=T+2*HOUR)
        summary.assert_not_called()
    def test_failure_retains_messages_and_never_retries_within_hour(self):
        self.collect()
        summary=MagicMock(side_effect=RuntimeError('secret response must not be logged'))
        service=HourlyMemoryService(self.store,GROUP,summary)
        service.run_once(now=T+HOUR)
        service.run_once(now=T+HOUR+60,force=True)
        self.assertEqual(summary.call_count,1)
        self.assertEqual(self.store.stats()['pending'],1)
        self.assertNotIn('secret',self.store.stats()['scopes'][0]['last_error'])
        service.run_once(now=T+2*HOUR)
        self.assertEqual(summary.call_count,2)
    def test_invalid_source_rejected_without_cursor_change(self):
        self.collect(); batch=self.store.claim(GROUP,now=T+HOUR)
        with self.assertRaises(ValueError): self.store.complete(batch,[card([99999])])
        self.assertEqual(self.store.stats()['pending'],1)
        self.assertEqual(self.store.stats()['memories'],0)
    def test_bot_cannot_establish_fact(self):
        self.collect(message(own=True)); batch=self.store.claim(GROUP,now=T+HOUR)
        with self.assertRaises(ValueError): self.store.complete(batch,[card([batch['messages'][0]['id']])])
    def test_memory_and_evidence_survive_restart(self):
        self.collect(); self.finish()
        restarted=GroupMemoryStore(self.path)
        self.assertIn('篮球',restarted.recall('篮球约在哪里？'))
        review=restarted.review_text(GROUP)
        self.assertIn('出处',review); self.assertIn('周六三点去操场打篮球',review)
        self.assertEqual(restarted.stats()['pending'],0)
    def test_group_scope_isolation_and_private_recall_all(self):
        self.collect(); self.finish()
        self.assertIn('篮球',self.store.recall('篮球',scope=('account','room')))
        self.assertEqual(self.store.recall('篮球',scope=('account','other')),'')
        self.assertEqual(self.store.recall('篮球',scope=('','')),'')
        self.assertIn('篮球',self.store.recall('篮球'))
    def test_rumor_is_labelled_and_not_rewritten_as_fact(self):
        self.collect(message(text='听说周六球赛取消了，还不确定'))
        self.finish(text='小林说听说周六球赛取消，但尚未证实。',kind='rumor')
        self.assertIn('未证实说法',self.store.recall('球赛取消了吗'))
    def test_batch_cap_keeps_overflow_for_later_hour(self):
        self.collect(*(message(i,text='篮球'*850) for i in range(20)))
        batch=self.store.claim(GROUP,now=T+HOUR)
        self.assertLess(len(batch['messages']),20)
        self.assertLessEqual(sum(len(item['text']) for item in batch['messages']),12000)
        self.store.complete(batch,[],now=T+HOUR)
        self.assertGreater(self.store.stats()['pending'],0)
    def test_message_count_cap(self):
        self.collect(*(message(i,text='好') for i in range(205)))
        batch=self.store.claim(GROUP,now=T+HOUR)
        self.assertLessEqual(len(batch['messages']),200)
    def test_double_complete_is_rejected(self):
        self.collect(); batch=self.finish()
        with self.assertRaises(ValueError): self.store.complete(batch,[])
        self.assertEqual(self.store.stats()['memories'],1)
    def test_stop_during_network_preserves_pending(self):
        self.collect()
        service=HourlyMemoryService(self.store,GROUP)
        def summarize(batch):
            service.stop()
            return [card([batch['messages'][0]['id']])]
        service.summarizer=summarize
        service.run_once(now=T+HOUR)
        self.assertEqual(self.store.stats()['pending'],1)
        self.assertEqual(self.store.stats()['memories'],0)
    def test_missing_store_does_not_break_chat_or_create_database(self):
        absent=Path(self.tmp.name)/'absent.sqlite3'
        with patch('wechat_group_bridge.group_memory.default_path',return_value=absent):
            self.assertEqual(recall_for_chat('篮球'),'')
        self.assertFalse(absent.exists())
    def test_chat_message_builder_private_and_group_recall(self):
        self.collect(); self.finish()
        import importlib.util
        import brain.chat as chat_module
        candidate=Path(__file__).parent/'brain'/'chat.py'
        if candidate.exists():
            spec=importlib.util.spec_from_file_location('brain.chat_memory_candidate',candidate)
            chat_module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chat_module)
        ChatService, EmotionState=chat_module.ChatService,chat_module.EmotionState
        chat=ChatService.__new__(ChatService)
        chat.memory=MagicMock()
        chat.memory.get_pet_name.return_value='师滔'
        chat.memory.get_user_name.return_value='测试'
        chat.memory.recent_memories.return_value=[]
        chat.memory.recent_chats.return_value=[]
        chat.emotion=EmotionState()
        with patch('wechat_group_bridge.group_memory.default_path',return_value=self.path):
            private=chat._build_messages('篮球约在哪里',[])
            group=chat._build_messages('篮球约在哪里',[],group_memory_scope=('account','room'),session_history=[])
            wrong=chat._build_messages('篮球约在哪里',[],group_memory_scope=('account','other'),session_history=[])
        for output in (private,group):
            records=[item for item in output if '<group_memory_records>' in item['content']]
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]['role'],'user')
            self.assertIn('操场',records[0]['content'])
        self.assertFalse(any('<group_memory_records>' in item['content'] for item in wrong))
    def test_reply_passes_exact_scope(self):
        chat=MagicMock()
        chat.chat_stream.return_value=('收到',None,None)
        engine=GroupReplyEngine(lambda:chat)
        engine.reply(message(),'篮球')
        self.assertEqual(chat.chat_stream.call_args.kwargs['group_memory_scope'],('account','room'))
    def test_setting_survives_save_and_legacy_defaults_enabled(self):
        config=Path(self.tmp.name)/'settings.json'
        config.write_text('{}',encoding='utf-8')
        self.assertTrue(BridgeSettings.load(config).hourly_memory_enabled)
        BridgeSettings(hourly_memory_enabled=False).save(config)
        self.assertFalse(BridgeSettings.load(config).hourly_memory_enabled)

if __name__ == '__main__': unittest.main()
