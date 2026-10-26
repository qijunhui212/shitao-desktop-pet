from __future__ import annotations
from contextlib import closing
import hashlib
import os
import json
from pathlib import Path
import time
import unicodedata

from .models import IncomingGroupMessage
from .db_snapshot import ALLOWED, snapshot, file_stamp
from .db_crypto import decompress_content
from .mentions import match_mention

WECHAT_EXE = Path(os.getenv('WECHAT_EXE', str(Path(os.getenv('ProgramFiles', 'C:/Program Files'))/'Tencent/Weixin/Weixin.exe')))
GROUP_ID = os.getenv('WECHAT_GROUP_ID', '').strip()
TABLE = 'Msg_' + hashlib.md5(GROUP_ID.encode()).hexdigest()


def active_account():
    import psutil
    found = []
    for proc in psutil.process_iter(['name']):
        try:
            if (proc.info['name'] or '').lower() != 'weixin.exe' or Path(proc.exe()).resolve() != WECHAT_EXE.resolve():
                continue
            roots = {Path(f.path).parent.parent for f in proc.open_files()
                     if Path(f.path).name == 'contact.db' and Path(f.path).parent.name == 'contact'
                     and Path(f.path).parent.parent.name == 'db_storage'}
            for root in roots:
                found.append((proc.pid, root))
        except (OSError, psutil.Error):
            continue
    if len(found) != 1:
        raise RuntimeError('请先登录微信；无法唯一确认当前登录账号的本地数据库。')
    return found[0]


def normalize(value):
    return ''.join(unicodedata.normalize('NFKC', value or '').split())


class GroupDatabaseReader:
    def __init__(self, settings, private_dir: Path):
        self.settings = settings
        self.private_dir = private_dir
        self.cursor = 0
        self._stamp = None
        self._backlog = False
        self._last_identity_check = 0

    def start(self):
        if not GROUP_ID.endswith('@chatroom'):
            raise RuntimeError('请先在本机配置 WECHAT_GROUP_ID；仓库不包含任何账号或群的接入凭据。')
        import win32crypt
        self.pid, self.database = active_account()
        self.self_id = self.database.parent.name.rsplit('_', 1)[0]
        try:
            data = win32crypt.CryptUnprotectData((self.private_dir/'keys.dpapi').read_bytes(), None, None, None, 1)[1]
            self.keys = json.loads(data)
        except Exception as exc:
            raise RuntimeError('本机微信数据库访问配置未就绪，请重新初始化本机接入。') from exc
        if set(self.keys) != set(ALLOWED):
            raise RuntimeError('数据库访问范围不匹配。')
        self.check_identity(force=True)
        with closing(snapshot(self.database, 'message/message_0.db', self.keys)[0]) as conn:
            self.cursor = conn.execute(f'SELECT coalesce(max(local_id),0) FROM [{TABLE}]').fetchone()[0]
        # All existing rows become the baseline; none are emitted on startup.

    def check_identity(self, force=False):
        if not force and time.monotonic() - self._last_identity_check < 5:
            return
        pid, database = active_account()
        if (pid, database) != (self.pid, self.database):
            raise RuntimeError('微信已退出或切换账号，请重新开始监听。')
        with closing(snapshot(self.database, 'contact/contact.db', self.keys)[0]) as conn:
            row = conn.execute('SELECT id,nick_name,remark FROM contact WHERE username=?', (GROUP_ID,)).fetchone()
            if not row or not any(normalize(x) == normalize(self.settings.group_name) for x in row[1:]):
                raise RuntimeError('本机接入只支持已核对的示例群群，群名或群 ID 不匹配。')
            self.members = {r[0]: (r[1] or r[2] or '群成员') for r in conn.execute(
                'SELECT c.username,c.nick_name,c.remark FROM contact c JOIN chatroom_member m ON m.member_id=c.id WHERE m.room_id=?', (row[0],))}
        if self.self_id not in self.members:
            raise RuntimeError('当前账号不在目标群成员列表中。')
        self._last_identity_check = time.monotonic()

    def poll(self):
        self.check_identity()
        path = self.database/'message/message_0.db'
        stamp = (file_stamp(path), file_stamp(Path(str(path)+'-wal')))
        if stamp == self._stamp and not self._backlog:
            return []
        with closing(snapshot(self.database, 'message/message_0.db', self.keys)[0]) as conn:
            rows = conn.execute(f'SELECT local_id,local_type,real_sender_id,message_content,WCDB_CT_message_content,source,WCDB_CT_source,create_time FROM [{TABLE}] WHERE local_id>? ORDER BY local_id LIMIT 200', (self.cursor,)).fetchall()
            names = dict(conn.execute('SELECT rowid,user_name FROM Name2Id'))
        messages = []
        for lid, kind, sender, raw, compression, source, source_compression, created_at in rows:
            user = names.get(sender, '')
            text = decompress_content(raw, compression) or ''
            if user not in self.members and ':\n' in text:
                prefix = text.split(':\n', 1)[0]
                if prefix in self.members:
                    user = prefix
            if user in self.members and text.startswith(user + ':\n'):
                text = text[len(user)+2:]
            if kind & 0xffffffff != 1:
                text = ''  # Images/voice still count as activity; no media is uploaded.
            mentioned, known, clean_text = match_mention(text, source, source_compression, self.self_id,
                                                       self.members.get(self.self_id, ''))
            messages.append(IncomingGroupMessage(
                group_name=self.settings.group_name, sender_name=self.members.get(user, '群成员'),
                content=text.replace('＠', '@'), message_id=str(lid),
                is_self=user == self.self_id if user in self.members else None,
                is_group_mention=bool(text) and mentioned, mention_targets_known=known,
                reply_content=clean_text if mentioned else None, account_id=self.self_id,
                group_id=GROUP_ID, sender_id=user, sent_at=float(created_at)))
            self.cursor = lid
        self._stamp = stamp
        self._backlog = len(rows) == 200
        return messages

    def send_baseline(self):
        with closing(snapshot(self.database, 'message/message_0.db', self.keys)[0]) as conn:
            return conn.execute(f'SELECT coalesce(max(local_id),0) FROM [{TABLE}]').fetchone()[0]

    def delivered(self, after_id, text):
        with closing(snapshot(self.database, 'message/message_0.db', self.keys)[0]) as conn:
            names = dict(conn.execute('SELECT rowid,user_name FROM Name2Id'))
            rows = conn.execute(f'SELECT server_id,status,real_sender_id,message_content,WCDB_CT_message_content FROM [{TABLE}] WHERE local_id>? ORDER BY local_id', (after_id,)).fetchall()
        return any(str(sid) not in ('', '0', 'None') and status == 2 and names.get(sender) == self.self_id
                   and (decompress_content(raw, ct) or '').removeprefix(self.self_id+':\n') == text
                   for sid, status, sender, raw, ct in rows)
