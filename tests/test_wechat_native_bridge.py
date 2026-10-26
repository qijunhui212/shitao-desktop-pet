import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from wechat_group_bridge.models import BridgeSettings, IncomingGroupMessage
from wechat_group_bridge.native_transport import NativeGroupTransport, EXPECTED_HASH
from wechat_group_bridge.db_reader import GROUP_ID, GroupDatabaseReader, TABLE
from wechat_group_bridge.policy import MessageGate
from wechat_group_bridge.reply import GroupReplyEngine


class Response:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return json.dumps(self.data).encode()


class Client:
    def __init__(self):
        self.calls = []
        self.fail_send = False
        self.status = {'pid': 1, 'group': GROUP_ID, 'sha256': EXPECTED_HASH, 'runtime_ready': True}
    def open(self, request, timeout):
        body = json.loads(request.data) if request.data else None
        self.calls.append((request.full_url.rsplit('/',1)[-1], body))
        if request.full_url.endswith('/status'): return Response(self.status)
        if request.full_url.endswith('/send'):
            if self.fail_send: raise URLError('timeout after submit')
            return Response({'state':'submitted_unconfirmed', 'delivered':False})
        return Response({'active': body['action'] != 'stop'})


class Reader:
    pid = 1
    def start(self): pass
    def check_identity(self, force=False): pass
    def poll(self): return []
    def send_baseline(self): return 42
    def delivered(self, baseline, text): return True


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root/'bridge.private.json').write_text(json.dumps({'token':'x'*48,'group':GROUP_ID,'port':30216}))
        self.client = Client()
        self.reader = Reader()
        self.transport = NativeGroupTransport(BridgeSettings(auto_reply_enabled=True), runtime_dir=root,
            reader=self.reader, client=self.client)
        self.transport.start()
    def tearDown(self):
        self.transport.stop()
        self.temp.cleanup()
    def sends(self): return [b for route,b in self.client.calls if route == 'send']
    def test_start_does_not_send_or_replay_history(self):
        self.assertEqual(self.sends(), [])
    def test_receipt_is_checked_after_one_native_request(self):
        self.assertIn('服务器', self.transport.send('测试回复'))
        self.assertEqual(len(self.sends()), 1)
        self.assertEqual(self.sends()[0]['group'], GROUP_ID)
    def test_uncertain_http_result_is_never_retried(self):
        self.client.fail_send = True
        with self.assertRaisesRegex(RuntimeError, '不会自动重发'): self.transport.send('测试')
        self.assertEqual(len(self.sends()), 1)
    def test_missing_receipt_is_never_retried(self):
        self.reader.delivered = lambda *_: False
        with patch.object(self.transport._cancel, 'wait', return_value=False):
            with self.assertRaisesRegex(RuntimeError, '本条不会自动重发'): self.transport.send('测试')
        self.assertEqual(len(self.sends()), 1)
    def test_stop_cancels_queued_send(self):
        self.transport.stop()
        self.transport.send('不应该发')
        self.assertEqual(self.sends(), [])
    def test_read_only_setting_cannot_send(self):
        self.transport.settings = BridgeSettings()
        self.transport.send('不应该发')
        self.assertEqual(self.sends(), [])
    def test_utf8_limit_never_cuts_a_character(self):
        self.transport.send('师滔🙂'*1000)
        text = self.sends()[0]['text']
        self.assertLessEqual(len(text.encode()), 3000)
        self.assertNotIn('\ufffd', text)
    def test_wrong_account_backend_is_rejected(self):
        self.transport.stop()
        self.client.status['pid'] = 2
        self.transport._cancel.clear()
        with self.assertRaisesRegex(RuntimeError, '不匹配'): self.transport.start()
        self.assertFalse(self.transport._active)


class PipelineTests(unittest.TestCase):
    def test_context_waits_for_mention_and_ignores_self(self):
        calls = []
        class Chat:
            def chat_stream(self, text, _, **kwargs):
                calls.append((text, kwargs)); return '模拟回复', None, None
        engine = GroupReplyEngine(Chat)
        gate = MessageGate(BridgeSettings(auto_reply_enabled=True))
        group = BridgeSettings().group_name
        normal = IncomingGroupMessage(group, '成员甲', '今天去健身', '101')
        own = IncomingGroupMessage(group, '自己', '@师滔 自己发的消息', '102', True)
        mention = IncomingGroupMessage(group, '成员乙', '@师滔 一起去吗', '103')
        for msg in (normal, own):
            engine.observe_message(msg)
            self.assertFalse(gate.check(msg, now=100).accepted)
        self.assertEqual(calls, [])
        result = gate.check(mention, now=101)
        self.assertTrue(result.accepted)
        engine.reply(mention, result.text)
        self.assertIn('今天去健身', str(calls[0][1]['session_history']))
        self.assertFalse(calls[0][1]['persist_history'])
        gate.set_in_flight(False)
        self.assertFalse(gate.check(mention, now=200).accepted)

    def test_database_backlog_is_not_dropped_and_sender_is_preserved(self):
        import sqlite3
        reader = GroupDatabaseReader(BridgeSettings(), Path('.'))
        reader.database = Path('unused'); reader.keys = {}; reader.self_id = 'self'
        reader.members = {'person':'成员甲', 'self':'自己'}
        reader.check_identity = lambda **_: None
        def database(*_):
            db = sqlite3.connect(':memory:')
            db.execute('CREATE TABLE Name2Id(user_name TEXT)')
            db.executemany('INSERT INTO Name2Id VALUES (?)', [('person',),('self',)])
            db.execute(f'CREATE TABLE [{TABLE}](local_id,local_type,real_sender_id,message_content,WCDB_CT_message_content,source,WCDB_CT_source,create_time)')
            db.executemany(f'INSERT INTO [{TABLE}] VALUES (?,?,?,?,?,?,?,?)',
                [(i,1,1,'@师滔 内容'+str(i),0,None,0,1793000000+i) for i in range(1,251)] + [(251,1,2,'自己发的',0,None,0,1793000300)])
            return db, {}
        with patch('wechat_group_bridge.db_reader.snapshot', side_effect=database), patch('wechat_group_bridge.db_reader.file_stamp', return_value=(0,0)):
            first = reader.poll(); second = reader.poll(); third = reader.poll()
        self.assertEqual((len(first),len(second),len(third)), (200,51,0))
        self.assertEqual(first[0].sender_name, '成员甲')
        self.assertTrue(second[-1].is_self)
        self.assertTrue(first[0].is_group_mention)


if __name__ == '__main__': unittest.main(verbosity=2)
