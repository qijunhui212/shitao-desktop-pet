"""Same-request emotional interpretation, with an offline compatibility fallback."""
import re
import logging

STATES = frozenset(('calm', 'hurt', 'annoyed', 'angry', 'cooldown'))
NEGATIVE = frozenset(('hurt', 'annoyed', 'angry'))
PREFIX = '[[mood:'
PROMPT = ('\n回复最前面先写一个隐藏情绪标记 [[mood:STATE]]，换行后再写表情标记（若要求）和正文。'
          '结合上下文判断本轮话语对师滔的影响：calm=普通聊天/夸奖；hurt=被嫌弃、冷落、拒绝或让人失落；'
          'annoyed=被挖苦、贬低、敷衍或不耐烦对待；angry=明显侮辱或持续挑衅；cooldown=安慰、道歉或和解。'
          '不用出现脏话才算负面；比如“懒得理你”“这点事都做不好”“没你也一样”可让角色受伤。'
          '只判断当前用户对师滔的态度；用户自己难过、诉苦、引用别人说的话、否定辱骂不是攻击师滔。'
          '师滔平时嘴欠、攻击性较强，calm也能主动串人。反差重点：被翻出自己的糗事、已确认的错事或被戳痛处时优先hurt，先嘴硬一句再委屈；普通侮辱才annoyed/angry。只是平静询问往事不算戳痛处。'
          '被戳中时别继续逞强骂到底，也别否认已知事实；自然用俺、咋、也等枣庄口吻。不要自行输出“可恨我了”，这句由程序按概率添加。'
          'STATE只能用上面五个英文值，标记不是正文。')
APOLOGY = re.compile(r'对不起|抱歉|不逗你|不闹了|别生气|我错了|开个玩笑|不是你的错|没有怪你|没怪你|不是在骂你|没骂你|不讨厌你|没有讨厌你')
DISTRESS = re.compile(r'去世|葬礼|重病|住院|自杀|不想活|救命|我.{0,5}(难过|伤心|痛苦|抑郁|被欺负|被骗|失恋)')
INSULT = re.compile(r'(你|师滔|桌宠|小人).{0,10}(傻逼|傻[比bB]|废物|垃圾|蠢|急了|又急|真菜|不行|弱鸡|装逼|可贱|真胖|好胖|太胖|真丑|好丑|太丑|真烦|好烦|烦死|笨|没用|没意思|一无是处|话真多)|^(傻逼|废物|垃圾|急急急)[！!。\s]*$')
HURT = re.compile(r'(不想|不愿|懒得|不爱|不喜欢).{0,5}(理你|跟你|和你|陪你|看见你|看到你)|(?:讨厌|嫌弃|恨|烦|不需要|不稀罕|拉黑|删掉|删除)你|你.{0,8}(让.{0,3}失望|一点用都没有|什么都不会|没人喜欢|一边去)|没人.{0,3}(喜欢|在乎|理)你|没你.{0,4}(也一样|更好)|(?:别|不要).{0,3}(烦我|跟我说话|来找我)|^(闭嘴|滚开|滚吧|走开|一边去|就这|这都不会)[？?！!。\s]*$')
QUOTED = re.compile(r'[“"「『].*?[”"」』]')
REASSURANCE = re.compile(r'你.{0,3}(不是|并不|一点也不|不算|不).{0,2}(废物|垃圾|蠢|傻|胖|丑|笨|烦|没用)')
SORE_TOPIC = re.compile(r'大清洗|删.{0,4}(我们|同学|好友)|放.{0,5}鸽子|鸽了|阿萨姆|死士|600.{0,3}皮肤|六百.{0,3}皮肤|小周.{0,8}吵架')
SORE_CUE = re.compile(r'还好意思|还敢|还嘴硬|少装|装什么|装啥|不是你|认怂|理亏|心虚|别狡辩|自己.{0,4}(做过|干过)|明明|笑死|就你还|还笑话|翻旧账')
SORE_DIRECT = re.compile(r'(你|师滔).{0,12}(把我们.{0,5}删|把同学.{0,5}删|当年.{0,6}删|大清洗.{0,8}删|放.{0,5}鸽子|鸽了|自己做错|明明做错|理亏|心虚|被戳中痛处|说到痛处|戳到痛处)')
SORE_DENIAL = re.compile(r'(你|师滔).{0,6}(没有|没|并没|并未|从未).{0,6}(放.{0,5}鸽子|删|做错|理亏)|不是你.{0,8}(放.{0,5}鸽子|删).{0,4}(吗|么)?[。！!]?$', re.I)
EVENT_QUERY = re.compile(r'什么时候|哪一年|哪天|几月|怎么回事|什么原因|为什么|经过|讲讲|说说|给谁|谁买|买了什么')

def sore_spot(text):
    plain = QUOTED.sub('', str(text))
    # A rhetorical accusation "不是你...吗" is not reassurance.
    denied = SORE_DENIAL.search(plain) and not re.search(r'不是你.*[吗么？?]', plain)
    if EVENT_QUERY.search(plain) and not SORE_CUE.search(plain): return False
    return not denied and bool(SORE_DIRECT.search(plain) or (SORE_TOPIC.search(plain) and SORE_CUE.search(plain)))

def fallback(text):
    text = QUOTED.sub('', str(text))
    if APOLOGY.search(text) or REASSURANCE.search(text): return 'cooldown'
    if DISTRESS.search(text): return 'calm'
    if sore_spot(text):
        logging.getLogger(__name__).debug('Reaction fallback chose hurt for a sore-point reminder')
        return 'hurt'
    if INSULT.search(text):
        return 'angry' if re.search(r'傻逼|废物|垃圾', text) else 'annoyed'
    if HURT.search(text): return 'hurt'
    return 'calm'

def extract(raw):
    text = str(raw or '')
    match = re.search(r'\[\[mood:([a-z_]+)\]\]', text, re.I)
    proposed = match.group(1).lower() if match else None
    text = re.sub(r'\[\[mood:[^\]\r\n]*\]\]', '', text, flags=re.I)
    text = re.split(r'\[\[mood:', text, maxsplit=1, flags=re.I)[0]
    for length in range(len(PREFIX), 0, -1):
        if text.lower().endswith(PREFIX[:length]):
            text = text[:-length]
            break
    return text.strip(), proposed if proposed in STATES else None

def resolve(text, proposed, local_state='calm'):
    unquoted = QUOTED.sub('', str(text))
    if APOLOGY.search(unquoted) or REASSURANCE.search(unquoted): return 'cooldown'
    if DISTRESS.search(unquoted): return 'calm'
    if sore_spot(unquoted): return 'hurt'
    return proposed if proposed in STATES else local_state
