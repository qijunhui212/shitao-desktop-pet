"""Occasional local utterances from imported memory; no API calls."""
import random,re,time

CHANCE_QUESTION=0.05
CHANCE_MONOLOGUE=0.03
SHARED_COOLDOWN=600
MONOLOGUE_COOLDOWN=1200
SENSITIVE=re.compile(r'传闻|待核实|未经证实|性取向|双性|造谣|性压抑|初恋|分手|喜欢.*女生|班主任|不正常')

def choose(memory,kind,recent=(),rng=random.random):
    if not isinstance(memory,dict):return None
    field='proactive_questions' if kind=='question' else 'proactive_lines'
    pool=[]
    for card in memory.get('cards',[]):
        if not isinstance(card,dict) or card.get('proactive_allowed') is False:continue
        if SENSITIVE.search(str(card.get('status',''))+' '+str(card.get('title',''))):continue
        phrases=card.get(field,[])
        if not isinstance(phrases,list):continue
        for phrase in phrases:
            if isinstance(phrase,str) and 1<=len(phrase)<=90 and not re.search(r'[\x00-\x1f<>]',phrase):
                if phrase not in recent:pool.append({'text':phrase,'card_id':card.get('id'),'kind':kind})
    return pool[min(int(rng()*len(pool)),len(pool)-1)] if pool else None

class ProactiveState:
    def __init__(self):
        self.last_any=-float('inf');self.last_monologue=-float('inf');self.recent=[]
    def attempt(self,memory,settings,now=None,rng=random.random):
        now=time.monotonic() if now is None else now
        if now-self.last_any<SHARED_COOLDOWN:return None
        item=None
        if settings.get('proactive',True) and rng()<CHANCE_QUESTION:
            item=choose(memory,'question',self.recent,rng)
        if not item and settings.get('monologue',True) and now-self.last_monologue>=MONOLOGUE_COOLDOWN and rng()<CHANCE_MONOLOGUE:
            item=choose(memory,'monologue',self.recent,rng)
        return item
    def mark(self,item,now=None):
        now=time.monotonic() if now is None else now
        self.last_any=now
        if item['kind']=='monologue':self.last_monologue=now
        self.recent=(self.recent+[item['text']])[-6:]
