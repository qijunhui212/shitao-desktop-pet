"""Durable, source-linked group memories; separate from persona and private chat."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

HOUR = 3600
KINDS = {'event': '事件', 'plan': '约定', 'preference': '偏好', 'topic': '话题',
         'joke': '玩笑', 'rumor': '未证实说法', 'correction': '更正'}


def default_path():
    from config.paths import app_root
    return app_root()/'data'/'wechat_group_memory.sqlite3'


def local_time(value):
    return datetime.fromtimestamp(value, timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')


def tokens(text):
    result = set(re.findall(r'[a-z0-9_]{2,}', text.lower()))
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        result.update(run[i:i+2] for i in range(len(run)-1))
    return result


class GroupMemoryStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, account TEXT NOT NULL, room TEXT NOT NULL,
                    group_name TEXT NOT NULL, message_id TEXT NOT NULL, sender_id TEXT NOT NULL,
                    sender TEXT NOT NULL, sent_at REAL NOT NULL, received_at REAL NOT NULL,
                    is_self INTEGER, content TEXT NOT NULL, summarized INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(account,room,message_id));
                CREATE INDEX IF NOT EXISTS pending ON messages(account,room,summarized,id);
                CREATE TABLE IF NOT EXISTS schedule (
                    account TEXT NOT NULL, room TEXT NOT NULL, group_name TEXT NOT NULL,
                    next_due REAL NOT NULL, last_attempt REAL NOT NULL DEFAULT 0,
                    last_success REAL NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
                    active_run TEXT NOT NULL DEFAULT '', PRIMARY KEY(account,room));
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY, account TEXT NOT NULL, room TEXT NOT NULL,
                    group_name TEXT NOT NULL, created_at REAL NOT NULL, event_start REAL NOT NULL,
                    event_end REAL NOT NULL, kind TEXT NOT NULL, summary TEXT NOT NULL,
                    participants TEXT NOT NULL, keywords TEXT NOT NULL, sources TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, message, now=None):
        now = time.time() if now is None else now
        if not message.content.strip() or not message.account_id or not message.group_id or not message.message_id:
            return False
        with self.connect() as db:
            inserted = db.execute('''INSERT OR IGNORE INTO messages
                (account,room,group_name,message_id,sender_id,sender,sent_at,received_at,is_self,content)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', (message.account_id, message.group_id, message.group_name,
                message.message_id, message.sender_id, message.sender_name, message.sent_at or now, now,
                None if message.is_self is None else int(message.is_self), message.content)).rowcount
            db.execute('INSERT OR IGNORE INTO schedule(account,room,group_name,next_due) VALUES (?,?,?,?)',
                       (message.account_id, message.group_id, message.group_name, now+HOUR))
        return bool(inserted)

    def claim(self, group_name, now=None, force=False):
        """Reserve the hourly API budget atomically, including across restarts."""
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            scopes = db.execute('SELECT * FROM schedule WHERE group_name=? ORDER BY next_due', (group_name,)).fetchall()
            for scope in scopes:
                if scope['next_due'] > now and (not force or scope['last_attempt'] > 0):
                    continue
                rows = db.execute('''SELECT * FROM messages WHERE account=? AND room=? AND summarized=0
                    ORDER BY id LIMIT 200''', (scope['account'], scope['room'])).fetchall()
                if not rows:
                    db.execute('UPDATE schedule SET next_due=? WHERE account=? AND room=?',
                               (now+HOUR, scope['account'], scope['room']))
                    continue
                selected, used = [], 0
                for row in rows:
                    item = {'id':row['id'], 'speaker':row['sender'], 'time':local_time(row['sent_at']),
                            'is_bot':row['is_self'] != 0, 'text':row['content'][:1600]}
                    size = len(json.dumps(item, ensure_ascii=False))
                    if selected and used+size > 12000:
                        break
                    selected.append(item); used += size
                run = uuid4().hex
                db.execute('''UPDATE schedule SET next_due=?,last_attempt=?,last_error='',active_run=?
                    WHERE account=? AND room=?''', (now+HOUR, now, run, scope['account'], scope['room']))
                return {'run':run, 'account':scope['account'], 'room':scope['room'],
                        'group_name':group_name, 'messages':selected, 'attempted_at':now}
        return None

    def complete(self, batch, cards, now=None):
        now = time.time() if now is None else now
        sources = {item['id']:item for item in batch['messages']}
        # Validate the whole result before changing any pending-message cursor.
        validated = []
        if not isinstance(cards, list) or len(cards) > 8:
            raise ValueError('群记忆返回格式不正确，待整理消息已保留。')
        for card in cards:
            if not isinstance(card, dict):
                raise ValueError('群记忆条目格式不正确。')
            ids = card.get('source_ids', [])
            if not isinstance(ids, list) or not ids or any(type(i) is not int or i not in sources for i in ids):
                raise ValueError('群记忆缺少有效消息出处，未写入。')
            if not any(not sources[i]['is_bot'] for i in ids):
                raise ValueError('不能只用桌宠自己的回复建立事实记忆。')
            summary = card.get('summary', '')
            kind = card.get('kind', '')
            if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 350 or kind not in KINDS:
                raise ValueError('群记忆内容或类型不正确。')
            for field in ('participants','keywords'):
                if not isinstance(card.get(field, []), list) or any(not isinstance(x,str) for x in card.get(field, [])):
                    raise ValueError('群记忆人物或关键词格式不正确。')
            validated.append((card, list(dict.fromkeys(ids))))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT active_run FROM schedule WHERE account=? AND room=?',
                                 (batch['account'], batch['room'])).fetchone()
            if not current or current[0] != batch['run']:
                raise ValueError('这次整理已经结束或被新的任务替代。')
            for card, ids in validated:
                rows = db.execute('SELECT sent_at FROM messages WHERE id IN ('+','.join('?' for _ in ids)+')', ids).fetchall()
                times = [row[0] for row in rows]
                db.execute('''INSERT INTO memories(account,room,group_name,created_at,event_start,event_end,
                    kind,summary,participants,keywords,sources) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (batch['account'], batch['room'], batch['group_name'], now, min(times), max(times), card['kind'],
                     card['summary'].strip(), json.dumps(card.get('participants',[])[:12],ensure_ascii=False),
                     json.dumps(card.get('keywords',[])[:12],ensure_ascii=False), json.dumps(ids)))
            db.executemany('UPDATE messages SET summarized=1 WHERE id=?', ((i,) for i in sources))
            db.execute('UPDATE schedule SET active_run=\'\',last_success=?,last_error=\'\' WHERE account=? AND room=?',
                       (now, batch['account'], batch['room']))
        return len(validated)

    def fail(self, batch, message):
        with self.connect() as db:
            db.execute('''UPDATE schedule SET active_run='',last_error=?
                WHERE account=? AND room=? AND active_run=?''',
                (str(message)[:200],batch['account'],batch['room'],batch['run']))

    def stats(self, group_name=None):
        clause = ' WHERE group_name=?' if group_name else ''
        args = (group_name,) if group_name else ()
        with self.connect() as db:
            scopes = [dict(row) for row in db.execute('SELECT * FROM schedule'+clause,args)]
            pending = db.execute('SELECT count(*) FROM messages WHERE summarized=0'+(' AND group_name=?' if group_name else ''),args).fetchone()[0]
            count = db.execute('SELECT count(*) FROM memories'+clause,args).fetchone()[0]
        return {'pending':pending, 'memories':count, 'scopes':scopes}

    def recall(self, query, scope=None, limit=4, char_limit=1400):
        if scope is not None and not all(scope):
            return ''
        with self.connect() as db:
            clause, args = (' WHERE account=? AND room=?', tuple(scope)) if scope is not None else ('',())
            rows = db.execute('SELECT * FROM memories'+clause+' ORDER BY event_end DESC,id DESC LIMIT 1500',args).fetchall()
        wanted = tokens(query)
        recent_query = any(word in query for word in ('之前','昨天','上次','最近','还记得','群里','刚才'))
        ranked = []
        for index, row in enumerate(rows):
            overlap = wanted & tokens(row['summary']+' '+row['keywords']+' '+row['participants'])
            score = len(overlap)
            if not score and not (recent_query and index < 2):
                continue
            ranked.append((score+1/(index+2), row))
        snippets, size = [], 0
        for _, row in sorted(ranked, key=lambda pair:pair[0], reverse=True)[:limit]:
            snippet = f"[{local_time(row['event_start'])} · {row['group_name']} · {KINDS[row['kind']]}] {row['summary']}"
            if size+len(snippet) > char_limit: break
            snippets.append(snippet); size += len(snippet)
        return '\n'.join(snippets)

    def review_text(self, group_name=None):
        with self.connect() as db:
            clause, args = (' WHERE group_name=?',(group_name,)) if group_name else ('',())
            rows = db.execute('SELECT * FROM memories'+clause+' ORDER BY id DESC LIMIT 100',args).fetchall()
            sections = []
            for row in rows:
                evidence = []
                for source_id in json.loads(row['sources']):
                    source = db.execute('SELECT sender,sent_at,content FROM messages WHERE id=?',(source_id,)).fetchone()
                    if source:
                        evidence.append(f"  {local_time(source['sent_at'])} {source['sender']}：{source['content'][:300]}")
                sections.append(f"{local_time(row['event_start'])} | {KINDS[row['kind']]}\n{row['summary']}\n出处：\n"+'\n'.join(evidence))
        return '\n\n'.join(sections) or '还没有整理完成的群记忆。新的文字消息会先保存在本机，每小时整理一次。'


def recall_for_chat(query, scope=None):
    path = default_path()
    if not path.exists(): return ''
    try:
        return GroupMemoryStore(path).recall(query,scope=scope)
    except (OSError,sqlite3.Error):
        return ''  # A memory file problem must not prevent normal chat.
