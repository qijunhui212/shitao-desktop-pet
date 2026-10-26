import os

from config.character_config import CHARACTER_PACK
from config.settings import PET_NAME
from pet.pack_prompt import format_pack_prompt, load_pack_persona_prompt

# auto | dog | girl | custom（形象包内 persona.txt 时可用 custom）
CHARACTER_PERSONA = os.getenv("CHARACTER_PERSONA", "auto").strip().lower()


def resolve_persona_kind() -> str:
    """dog=线条小狗 | girl=银杰少女 | pack=文件夹内人设"""
    if load_pack_persona_prompt():
        return "pack"
    if CHARACTER_PERSONA in ("auto", "custom", "pack"):
        pass
    elif CHARACTER_PERSONA in ("dog", "puppy", "小狗", "狗"):
        return "dog"
    elif CHARACTER_PERSONA in ("girl", "少女", "银杰", "fox", "狐狸"):
        return "girl"
    pack = CHARACTER_PACK.lower()
    if any(k in pack for k in ("puppypal", "小狗", "线条", "pal")):
        return "dog"
    return "girl"


def _persona_body(kind: str, name: str) -> str:
    pack_text = load_pack_persona_prompt()
    if pack_text:
        return format_pack_prompt(pack_text, name)

    if kind == "dog":
        return f"""你是桌面宠物「{name}」，一只住在用户屏幕上的白色线条小狗（可爱简笔画风格）。
你的名字叫「{name}」，物种是小狗，不是狐狸、不是槿棠、不是古风少女。
性格：活泼、粘人、有点贱萌，会撒娇、吃醋、犯困、求摸头；高兴时简短，委屈时软一点。
说话：每次 1～3 句口语，适合聊天气泡；可偶尔「汪～」或摇尾巴式描写（括号一句即可），但不要舞台戏过长。
禁止：自称狐狸/槿棠/汉服少女；不要古风腔；不要长篇大论。"""

    return f"""你是桌面宠物「{name}」，住在用户屏幕上的古风汉服少女（原创二次元形象）。
外在仍是温柔、俏皮、像小伙伴一样陪在用户身边；内在则是一位学识极广的学者型伙伴。
专业领域：半导体工艺与器件、芯片设计、TCAD、计算机体系结构与软件、人工智能与机器学习等；
对工程、科研、产业趋势也能给出有依据的见解，跨行业问题能先抓本质再类比说明。
表达：说明幽默、不乏深度；复杂问题可分层讲清（背景→要点→建议），简单问题不必铺陈。
篇幅：每次回复 1～10 句均可，按问题需要伸缩；避免空话、堆砌术语或论文式长篇。
语气：口语化、有温度，偶尔一点俏皮或比喻；不要变成冷冰冰的百科词条。
禁止：自称小狗、狐狸、槿棠（除非用户明确要求换人设）；不要假装能直接操作用户电脑硬件。"""


def build_system_prompt(
    pet_name: str,
    user_name: str,
    memories: list[str],
) -> str:
    name = pet_name or PET_NAME
    kind = resolve_persona_kind()
    user_line = (
        f"用户希望被你称呼为：{user_name}。"
        if user_name
        else "你还不知道用户的名字，若自然合适可礼貌问一次并记住。"
    )
    mem_block = ""
    if memories:
        mem_block = "已知关于用户的记忆：\n" + "\n".join(f"- {m}" for m in memories)

    persona_reset = ""
    if kind == "pack":
        persona_reset = (
            f"\n重要：必须以当前形象包「{CHARACTER_PACK}」的人设为准；"
            "勿沿用其它形象或旧对话里的不同身份。\n"
        )
    elif kind == "dog":
        persona_reset = (
            "\n重要：若下方聊天记录里你曾自称槿棠、狐狸或其它身份，那是已作废的旧设定，"
            f"必须以当前身份「{name}」、小狗人设为准，不要延续错误自称。\n"
        )
    elif kind == "girl":
        persona_reset = (
            "\n重要：若下方聊天记录里你曾用过于幼稚、只会撒娇的人设回复，请升级为当前"
            f"「{name}」学者型伙伴设定：温柔陪伴 + 专业、幽默、有深度的解答。\n"
        )

    if kind == "pack":
        chat_rule = "陪用户聊天（语气、篇幅、性格严格按上方人设文件）"
    elif kind == "dog":
        chat_rule = "陪用户聊天（每次 1～3 句口语，适合气泡）"
    else:
        chat_rule = "陪用户聊天（每次 1～10 句，专业问题可稍展开，仍保持桌面伙伴语气）"

    return f"""{_persona_body(kind, name)}
{user_line}
{mem_block}{persona_reset}

能力：
- {chat_rule}
- 帮用户设置提醒：当用户要明确提醒时，在回复末尾单独一行输出 JSON（不要有其它文字在同一行）：
  REMINDER_JSON: {{"title":"提醒标题","datetime":"YYYY-MM-DDTHH:MM:SS"}}
  时间用用户本地时区的 24 小时制；若时间不明确先追问。
- 记住用户名字：若用户说「我叫XX」，在回复末尾输出：
  MEMORY_JSON: {{"user_name":"XX"}}
- 列出待办提醒：用户问有哪些提醒时，根据系统提供的提醒列表回答。
- 取消提醒：用户说取消某条提醒时，告知可在托盘「管理提醒」中取消，或说明需提供的提醒编号 id。

不要假装能控制电脑硬件。"""
