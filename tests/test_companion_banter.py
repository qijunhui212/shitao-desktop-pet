"""Verify everyday chat requests use the revised persona before any insult."""
from types import SimpleNamespace

from brain import chat
from brain.companion_persona import EmotionState, STYLE, context_for
from brain import reaction
import pytest


def test_calm_request_carries_banter_and_dialect_without_memory_match(monkeypatch):
    service = object.__new__(chat.ChatService)
    service.emotion = EmotionState()
    service.memory = SimpleNamespace(
        get_pet_name=lambda: '师滔', get_user_name=lambda: '测试同学',
        recent_memories=lambda: [], recent_chats=lambda _: [],
    )
    monkeypatch.setattr(chat, 'build_system_prompt', lambda *args: '基础聊天能力')
    monkeypatch.setattr(chat, 'get_character_display_name', lambda: '师滔')
    monkeypatch.setattr(chat, 'context_for', lambda text, state: context_for(text, state, {'profile': '', 'cards': []}))
    monkeypatch.setattr(chat.stickers, 'settings', lambda: {'chat': False})
    messages = service._build_messages('吃啥', [])
    assert service.last_emotion == 'calm'
    assert messages[-1] == {'role': 'user', 'content': '吃啥'}
    assert STYLE in messages[0]['content']
    for phrase in ('wcnm','你冯呢','找YE揍呢','如果没有……，你冯直接……'):
        assert phrase in messages[0]['content']
    assert '平静但嘴欠' in messages[0]['content']
    assert '自称优先用“俺”' in messages[0]['content']
    assert '不用等对方先攻击' in messages[0]['content']
    assert '明确说别闹' in messages[0]['content']
    assert '偶尔说“俺”' not in messages[0]['content']


@pytest.mark.parametrize('text', [
    '你放我鸽子还好意思笑我？', '大清洗删我们那会儿，怎么不见你这么能说？你还嘴硬？',
    '给小周买阿萨姆才和好，就你还笑话别人认怂？', '你自己做错了还狡辩',
])
def test_sore_point_overrides_anger(text):
    assert reaction.fallback(text) == 'hurt'
    assert reaction.resolve(text, 'angry', 'angry') == 'hurt'
    emotion = EmotionState()
    emotion.update('你真菜', now=100)
    emotion.update('你又急了', now=101)
    assert emotion.state == 'angry'
    assert emotion.update(text, now=102) == 'hurt'
    assert emotion.level == 0


@pytest.mark.parametrize('text', [
    '你和小周怎么和好的？', '你放鸽子那次是什么时候？', '阿萨姆买给谁的？',
    '我今天很难过', '他说“你放我鸽子还好意思笑我”', '你没有放我鸽子',
])
def test_neutral_event_or_other_person_is_not_a_sore_point(text):
    assert reaction.fallback(text) == 'calm'


def test_reassurance_ends_hurt():
    assert reaction.fallback('不是你的错，没怪你') == 'cooldown'
    assert reaction.resolve('没怪你，别生气', 'hurt') == 'cooldown'
