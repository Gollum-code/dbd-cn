"""Chinese term dictionary for DBD localisation.

The pipeline translates English source terms into Chinese.  This module
holds the curated dictionary (terms that need exact, hand-tuned Chinese) and
a light, rule-based translator for structural values (realms, rarities, tag
names, role descriptors, units) that come from the wiki datatables.

Strategy (per the project plan):
  * curated dictionary first  -> deterministic, reviewable output
  * rule/translation-map fallback for structural tokens
  * anything unknown is left as English and flagged for manual review
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_DICT_DIR = Path(__file__).parent / "dictionaries"

# ---------------------------------------------------------------------------
# Curated dictionary: exact English -> Chinese.  Extend over time.
# ---------------------------------------------------------------------------
TERMS: dict[str, str] = {
    # Killers (the canonical "The ..." names)
    "Trapper": "设陷者",
    "Wraith": "幽灵",
    "Hillbilly": "电锯莽夫",
    "Nurse": "女护士",
    "Shape": "变形者",
    "Hag": "女巫",
    "Doctor": "医生",
    "Huntress": "女猎手",
    "Cannibal": "食人魔王",
    "Nightmare": "梦魇",
    "Pig": "猪女",
    "Clown": "小丑",
    "Spirit": "怨灵",
    "Legion": "军团",
    "Plague": "瘟疫",
    "Ghost Face": "鬼脸",
    "Demogorgon": "俄摩拉虫",
    "Oni": "鬼武者",
    "Deathslinger": "死神之枪",
    "Executioner": "刽子手",
    "Blight": "枯萎者",
    "Twins": "双胞胎",
    "Trickster": "小丑女",
    "Nemesis": "复仇女神",
    "Cenobite": "地牢修女",
    "Artist": "艺术家",
    "Sadako": "贞子",
    "Dredge": "深潜者",
    "Wesker": "威斯克",
    "Knight": "骑士",
    "Skull Merchant": "骷髅商人",
    "Singularity": "奇点",
    "Xenomorph": "异形",
    "Good Guy": "好人",
    "Chucky": "既视凶魔",
    "Unknown": "未知者",
    "Lich": "巫妖",
    "Vecna": "维克纳",
    "Dark Lord": "黑暗领主",
    "Dracula": "德古拉",
    "Houndmaster": "猎犬主人",
    "Doomed Courser": "厄运骑士",
    "Sojourn": "旅人",
    "The Blighter": "枯萎者",
    "Tormentor": "折磨者",
    "Inferno": "狱火",
    "Onryō": "般若",
    "The Mastermind": "幕后黑手",
    "Mastermind": "幕后黑手",
    "Slasher": "杀戮者",
    "Judgment": "审判",
    "First": "先驱者",
    # Survivors (full names)
    "William \"Bill\" Overbeck": "威廉·“比尔”·奥弗贝克",
    "Detective David Tapp": "侦探戴维·塔普",
    "Jeffrey \"Jeff\" Johansen": "杰弗里·“杰夫”·约翰森",
    "Ashley J. Williams": "阿什莉·J·威廉姆斯",
    "Lee Yun-jin": "李允真",
    "Leon Scott Kennedy": "里昂·S·肯尼迪",
    "Aestri Yazar & Baermar Uraz": "艾斯特里·雅扎尔 & 贝尔玛·乌拉斯",
    "Trevor Belmont": "特雷弗·贝尔蒙特",
    "Orela Rose": "奥蕾拉·罗斯",
    "Rick Grimes": "瑞克·格莱姆斯",
    "Michonne Grimes": "米琼·格莱姆斯",
    "Vee Boonyasak": "薇·蓬亚萨",
    "Dustin Henderson": "达斯汀·亨德森",
    "Eleven": "伊莱文",
    "Kwon Tae-young": "权泰英",
    "Shane Wiigwaas": "沙恩·威格瓦斯",
    "Aurora Stardotter": "奥罗拉·星尘",
    # Gnomes
    "Ghoul": "食尸鬼",
    "Animatronic": "机械人偶",
    "Krasue": "浮屠鬼",
    # Survivors
    "Dwight Fairfield": "德怀特·费尔菲尔德",
    "Meg Thomas": "梅格·托马斯",
    "Claudette Morel": "克劳黛特·莫雷尔",
    "Jake Park": "杰克·帕克",
    "Nea Karlsson": "内亚·卡尔森",
    "Laurie Strode": "劳丽·斯特罗德",
    "Ace Visconti": "艾斯·维斯康蒂",
    "Bill Overbeck": "比尔·奥弗贝克",
    "Feng Min": "风敏",
    "David King": "大卫·金",
    "Quentin Smith": "昆汀·史密斯",
    "Detective Tapp": "侦探塔普",
    "Kate Denson": "凯特·丹森",
    "Adam Francis": "亚当·弗朗西斯",
    "Jeff Johansen": "杰夫·约翰森",
    "Jane Romero": "简·罗梅罗",
    "Ash Williams": "阿什·威廉姆斯",
    "Nancy Wheeler": "南希·惠勒",
    "Steve Harrington": "史蒂夫·哈林顿",
    "Yui Kimura": "木村唯",
    "Zarina Kassir": "扎丽娜·卡西尔",
    "Cheryl Mason": "谢丽尔·梅森",
    "Felix Richter": "菲利克斯·里希特",
    "Élodie Rakoto": "艾洛迪·拉科托",
    "Yun-Jin Lee": "李允真",
    "Jill Valentine": "吉尔·瓦伦丁",
    "Leon S. Kennedy": "里昂·S·肯尼迪",
    "Mikaela Reid": "米凯拉·里德",
    "Jonah Vasquez": "乔纳·瓦斯奎兹",
    "Yoichi Asakawa": "浅川阳一",
    "Haddie Kaur": "哈迪·考尔",
    "Ada Wong": "艾达·王",
    "Rebecca Chambers": "丽贝卡·钱伯斯",
    "Vittorio Toscano": "维多利奥·托斯卡诺",
    "Thalita Lyra": "塔莉塔·莱拉",
    "Renato Lyra": "雷纳托·莱拉",
    "Gabriel Soma": "加布里埃尔·索马",
    "Nicolas Cage": "尼古拉斯·凯奇",
    "Ellen Ripley": "艾伦·里普利",
    "Alan Wake": "艾伦·韦克",
    "Sable Ward": "赛布尔·沃德",
    "Trickster's": "小丑女",
    "Clairée": "克莱尔",
    "Bard": "诗人",
    "Aestri Yazar": "艾斯特里·雅扎尔",
    "Baermar Uraz": "贝尔玛·乌拉斯",
    "Tatum": "塔图姆",
    "Minnie": "米妮",
    "Treat": "崔特",
    "Sam": "萨姆",
    "Toma": "托玛",
    "Junior": "ジュニア",
    "Ivy": "常春藤",
    "Lara Croft": "劳拉·克罗夫特",
    "Taurie Cain": "陶莉·凯恩",
    "Yoshida": "吉田",
    "Hux-A7-13": "哈克斯A7-13",
    "Frank": "弗兰克",
    "Julie": "朱莉",
    "Susie": "苏西",
    "Joey": "乔伊",
    # Realms
    "The MacMillan Estate": "麦克米伦庄园",
    "Autohaven Wreckers": "废车场",
    "Coldwind Farm": "冷风农场",
    "Crotus Prenn Asylum": "克劳图斯·普伦疯人院",
    "Red Forest": "红林",
    "Raccoon City Police Department": "浣熊市警察局",
    "Léry's Memorial Institute": "莱里纪念研究所",
    "RPD": "警局",
    "Fissure": "裂隙",
    "Yamaoka": "山冈",
    "Gulch": "峡谷",
    "Eyrie": "鹰巢",
    "Toba Landing": "鸟羽镇",
    "The Shattered Square": "破碎广场",
    "Temple of Perdition": "毁灭神庙",
    "The Astro Museum": "天文博物馆",
    "Bally's": "巴利赌场",
    "Midway": "中途城",
    "Evershade": "永影",
    "Infinite": "无尽",
    "Ormond": "奥蒙德",
    "Haddonfield": "哈登菲尔德",
    "Springwood": "斯普林伍德",
    "Greenvale Square": "绿谷广场",
    "The Gemination": "双生",
    "Necropolis": "幽冥城",
    "Port Paleborn": "苍白港",
    "Backwater Swamp": "死水沼泽",
    "Gideon Meat Plant": "基甸肉联厂",
    "Yamaoka Estate": "山冈家宅",
    "Hawkins National Laboratory": "霍金斯国家实验室",
    "Grave of Glenvale": "格伦威尔之墓",
    "Silent Hill": "寂静岭",
    "Raccoon City": "浣熊市",
    "Forsaken Boneyard": "荒芜坟场",
    "Withered Isle": "枯萎之岛",
    "The Decimated Borgo": "残破博尔戈",
    "Dvarka Deepwood": "德瓦尔卡密林",
    "Sleepless District": "无眠街区",
    # Perk / addon tags (kept in English in the DB; translated at display time)
    # Rarities
    "Common": "常见",
    "Uncommon": "稀有",
    "Rare": "罕见",
    "Very Rare": "精贵",
    "Ultra Rare": "传说",
    "Event": "活动",
    # Generic
    "Killer": "杀手",
    "Survivor": "逃生者",
    "Male": "男性",
    "Woman": "女性",
    "Men": "男性",
    "Women": "女性",
    "American": "美国人",
    "Canadian": "加拿大人",
    "Nigerian": "尼日利亚人",
    "Japanese": "日本人",
    "Korean": "韩国人",
    "British": "英国人",
    "French": "法国人",
    "German": "德国人",
    "Spanish": "西班牙人",
    "Italian": "意大利人",
    "Chinese": "中国人",
    "Brazilian": "巴西人",
    "Not specified": "未知",
    "different": "不同",
    "Chaos": "混沌",
    "The Trickster": "捣蛋者",
}

def _load_dict_file(name: str) -> dict[str, str]:
    """Load an extra dictionary JSON file from crawler/dictionaries."""
    path = _DICT_DIR / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        return {}


# Extra dictionaries loaded at import time (perks / maps / addons / realms).
EXTRA_DICTS: dict[str, dict[str, str]] = {
    filename.stem: _load_dict_file(filename.name)
    for filename in _DICT_DIR.glob("*_zh.json")
}

# ---------------------------------------------------------------------------
# Structural translation maps (fallback when not in curated dictionary)
# ---------------------------------------------------------------------------
ROLE_ZH: dict[str, str] = {
    "Nervous Leader": "紧张型领袖",
    "Energetic Athlete": "活力运动健将",
    "Studious Botanist": "好学植物学家",
    "Academic": "学者",
    "Solitary Survivalist": "孤僻求生者",
    "Tactician": "战术家",
    "Country Carpenter": "乡村木匠",
    "Mall Rat": "商场混混",
    "Celebrity": "名人",
    "Cyberpunk P.E. Teacher": "赛博朋克体育老师",
    "K-Pop Idol": "韩流偶像",
    "Paramedic": "护理员",
    "Vigilante": "义警",
    "Occult Teacher": "神秘学教师",
    "Reporter": "记者",
    "Film Student": "电影学院学生",
    "Writer": "作家",
    "The Hunk": "型男",
    "Rock Icon": "摇滚偶像",
    "Bookshop Owner": "书店店主",
    "Landscaper": "园丁",
    "Paleontologist": "古生物学家",
    "Aspiring Singer": "准歌手",
    "Bus Scheduler": "公交调度员",
    "Commercial Fisheries Captain": "商业渔业船长",
    "Engineer": "工程师",
    "Forensic Scientist": "法医科学家",
    "Paranormal Investigator": "灵异调查员",
    "Occultist": "神秘学家",
    "Photographer": "摄影师",
    "Contractor": "承包商",
    "Game Designer": "游戏设计师",
    "Comedian": "喜剧演员",
    "Captain": "船长",
    "Pilot": "飞行员",
    "Frontier Survivalist": "边境生存专家",
    "Museum Curator": "博物馆馆长",
    "Detective": "侦探",
    "Visual Anthropologist": "视觉人类学家",
    "Professional Gamer": "职业玩家",
    "Graphic Artist": "平面设计师",
    "Musician": "音乐家",
    "Barista": "咖啡师",
    "Astrophysicist": "天体物理学家",
    "Security Guard": "保安",
}

# tag / descriptor color-map left as English; translated via TERMS where possible.


RARITY_BY_LEVEL: dict[int, str] = {
    0: "Common",
    1: "Uncommon",
    2: "Rare",
    3: "Very Rare",
    4: "Ultra Rare",
    5: "Event",
}


def translate_term(term: Any, dictionary: dict[str, str] | None = None) -> str:
    """Translate one scalar.  Unknown / non-string values pass through."""
    if not isinstance(term, str):
        return "" if term is None else str(term)
    key = term.strip()
    if not key:
        return key
    d = dictionary or TERMS
    if key in d:
        return d[key]
    lower = key.lower()
    for k, v in d.items():
        if k.lower() == lower:
            return v
    if key in ROLE_ZH:
        return ROLE_ZH[key]
    # fall back through loaded extra dictionaries
    for extra in EXTRA_DICTS.values():
        if key in extra:
            return extra[key]
        for k, v in extra.items():
            if k.lower() == lower:
                return v
    return key


def translate_all(term: Any) -> str:
    """Translate using every loaded dictionary (TERMS + extras)."""
    return translate_term(term)


def looks_untranslated(text: str) -> bool:
    """Heuristic: text that is mostly Latin letters and lacks CJK."""
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_latin = bool(re.search(r"[A-Za-z]{2,}", text))
    return has_latin and not has_cjk
