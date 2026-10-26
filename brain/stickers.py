"""Small same-request sticker protocol; images and idle choices stay local."""
import json
import random
import re
from brain import reaction
from config.paths import resolve_resource_path, app_root

def catalog():
    try:
        return json.loads(resolve_resource_path('assets/stickers/catalog.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []

CATALOG = {card['id']: card for card in catalog()}
PREFIX = '[[sticker:'
MARKER = re.compile(r'\[\[sticker:([a-z_]+)\]\]', re.I)
SERIOUS = re.compile(r'去世|葬礼|重病|住院|抑郁|自杀|不想活|分手|失恋|难过|伤心|痛苦|被欺负|被骗|救命|杀人|真想打|打死|杀了')
BANTER = re.compile(r'斗图|表情|玩梗|开玩笑|整活|损友')
PROMPT = ('\n回复格式：情绪标记之后一行只写 [[sticker:ID]]，再换行说话。按本轮语意选一个，也可用 none。'
          '可选：shield=玩笑防御；schadenfreude=明确损友玩笑的幸灾乐祸；belly=肚子/吃饱/健身；'
          'thumbs_up=认可夸赞；rage=明确斗图时夸张急眼；football=足球/耍帅；laugh=好笑开心。'
          '真实难过、求助或严肃问题用none；别嘲笑痛苦。不要为凑表情改变回复。禁止使用其他ID。')

def extract(raw, streaming=False):
    """Strip metadata, including chunk-split prefixes, before display/history."""
    text, _mood = reaction.extract(raw)
    found = MARKER.search(text)
    proposed = found.group(1).lower() if found else None
    text = re.sub(r'\[\[sticker:[^\]\r\n]*\]\]', '', text, flags=re.I)
    text = re.split(r'\[\[sticker:',text,maxsplit=1,flags=re.I)[0]
    for length in range(len(PREFIX), 0, -1):
        if text.lower().endswith(PREFIX[:length]):
            text = text[:-length]
            break
    return text.strip(), proposed

def allowed(sticker_id, user_text, reply):
    if sticker_id not in CATALOG or SERIOUS.search(user_text + '\n' + reply):
        return False
    if sticker_id in ('rage', 'schadenfreude') and not BANTER.search(user_text):
        return False
    return True

def choose(user_text, reply, proposed=None, state='calm'):
    if proposed == 'none':
        return None
    if proposed in CATALOG:
        return proposed if allowed(proposed, user_text, reply) else None
    if SERIOUS.search(user_text + '\n' + reply):
        return None
    # Compatible with providers that ignore the optional marker.
    text = reply + '\n' + user_text
    for card in reversed(list(CATALOG.values())):
        if any(word in text for word in card['keywords']) and allowed(card['id'], user_text, reply):
            return card['id']
    if state in reaction.NEGATIVE:
        return 'shield'
    return None

def idle_choice(previous=None, allow_costume=True):
    choices = [c for c in CATALOG.values() if c.get('idle') and c['id'] != previous and (allow_costume or c['action'] != '14_costume_laugh')]
    return random.choice(choices) if choices else None

def settings():
    try:
        data = json.loads((app_root()/'data/sticker-settings.json').read_text(encoding='utf-8'))
        return {k: data.get(k) is not False for k in ('chat', 'idle','proactive','monologue')}
    except (OSError, ValueError, AttributeError):
        return {'chat': True, 'idle': True,'proactive':True,'monologue':True}

def save_settings(value):
    dest = app_root()/'data/sticker-settings.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps({k: bool(value.get(k, True)) for k in ('chat', 'idle','proactive','monologue')}), encoding='utf-8')
    temp.replace(dest)
