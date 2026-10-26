"""User-confirmed event cards, stored separately from imported knowledge."""
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config.paths import app_root

log = logging.getLogger(__name__)
LOCK = threading.RLock()
STATUSES = ('用户补充', '待核实', '计划/日程', '玩笑/创作')


def event_path():
    return app_root() / 'data/persona/chat-memories.json'


def read_events(path=None):
    p = Path(path) if path else event_path()
    if not p.exists():
        return {'schema_version': 1, 'profile': '', 'cards': []}
    try:
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        if data.get('schema_version') != 1 or not isinstance(data.get('cards'), list):
            raise ValueError()
        for card in data['cards']:
            if not isinstance(card, dict) or not all(isinstance(card.get(k), str) for k in ('id', 'title', 'summary')):
                raise ValueError()
        return data
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('新增记忆文件损坏，请先恢复备份；原文件未改动。') from exc


def _atomic_write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=p.name + '.', suffix='.tmp', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _clean(payload):
    def field(key, maximum, required=False):
        value = payload.get(key, '')
        if not isinstance(value, str):
            raise ValueError('记忆字段格式不正确')
        value = value.strip()
        if (required and not value) or len(value) > maximum:
            raise ValueError(f'{key} 需要{1 if required else 0}到{maximum}字')
        return value
    title = field('title', 80, True)
    summary = field('summary', 800, True)
    date = field('event_date', 80)
    status = payload.get('status', '用户补充')
    if status not in STATUSES:
        raise ValueError('请选择记忆性质')
    tags = payload.get('tags', [])
    if isinstance(tags, str):
        tags = re.split(r'[,，、;；\n]+', tags)
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValueError('关键词格式不正确')
    tags = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
    if len(tags) > 12 or any(len(t) > 30 for t in tags):
        raise ValueError('关键词最多12个，每个不超过30字')
    if not tags:
        raise ValueError('请至少填写一个以后会提到的关键词')
    return dict(title=title, summary=summary, event_date=date or None,
                status=status, tags=tags, aliases=[], date_note='发生时间由用户填写；未填写则未知。', uncertainties=[])


def save_event(payload, *, card_id=None, expected_updated_at=None, source=None, path=None):
    p = Path(path) if path else event_path()
    clean = _clean(payload)
    with LOCK:
        data = read_events(p)
        old = next((c for c in data['cards'] if c['id'] == card_id), None)
        if card_id and (not old or old.get('updated_at') != expected_updated_at):
            raise ValueError('这条记忆已变化，请重新打开后编辑。')
        fingerprint = hashlib.sha256(re.sub(r'\s+', '', clean['summary']).encode()).hexdigest()
        duplicate = next((c for c in data['cards'] if c['id'] != card_id and c.get('fingerprint') == fingerprint), None)
        if duplicate:
            return duplicate, False
        now = datetime.now(timezone.utc).isoformat()
        card = {**clean, 'id': card_id or 'chat-' + uuid.uuid4().hex,
                'created_at': old.get('created_at', now) if old else now, 'updated_at': now,
                'fingerprint': fingerprint, 'source_type': 'chat_user_confirmed',
                'source_excerpt': old.get('source_excerpt', '') if old else str(source or '')[:12000]}
        if old:
            data['cards'][data['cards'].index(old)] = card
        else:
            data['cards'].append(card)
        _atomic_write(p, data)
        log.info('Event memory saved id=%s count=%s updated=%s', card['id'], len(data['cards']), bool(old))
        return card, True


def delete_event(card_id, expected_updated_at, path=None):
    p = Path(path) if path else event_path()
    with LOCK:
        data = read_events(p)
        old = next((c for c in data['cards'] if c['id'] == card_id), None)
        if not old or old.get('updated_at') != expected_updated_at:
            raise ValueError('这条记忆已变化，请刷新列表。')
        data['cards'].remove(old)
        _atomic_write(p, data)
        log.info('Event memory deleted id=%s count=%s', card_id, len(data['cards']))
