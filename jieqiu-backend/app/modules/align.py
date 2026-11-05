"""对齐模块：多源队名 → 规范中文名。

原则：入库前先对齐；对齐不了的保留归一化原名并允许后续补别名，
绝不因别名缺失丢数据（ingest 只记 warning）。
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import TeamAlias

# 归一化时要剥掉的组织后缀（跨语言通用）
_STRIP_TOKENS = ("fc", "cf", "sc", "afc", "club", "de", "cd", "calcio")

# 种子别名：canonical → 常见变体（中/英/简称）。ingest 时若表为空则自动播种。
SEED_ALIASES: dict[str, list[str]] = {
    # ---- W3：football-data / Understat / the-odds-api 英文名 → 规范中文 ----
    # 英超（canonical 与竞彩采集器叫法一致）
    "曼城": ["manchestercity", "mancity", "曼彻斯特城", "man city"],
    "曼联": ["manchesterunited", "manutd", "曼彻斯特联"],
    "阿森纳": ["arsenal", "阿仙奴"],
    "利物浦": ["liverpool", "利物浦fc"],
    "切尔西": ["chelsea", "车路士"],
    "热刺": ["tottenham", "tottenhamhotspur", "托特纳姆热刺", "spurs"],
    "埃弗顿": ["everton"],
    "纽卡斯尔": ["newcastle", "newcastleunited", "纽卡斯尔联", "纽卡素"],
    "西汉姆": ["westham", "westhamunited", "西汉姆联"],
    "狼队": ["wolves", "wolverhamptonwanderers", "狼队足球俱乐部", "伍尔弗", "伍尔弗汉普顿"],
    "布莱顿": ["brighton", "brightonhovealbion"],
    "伯恩茅斯": ["bournemouth", "afcbournemouth"],
    "布伦特福德": ["brentford"],
    "水晶宫": ["crystalpalace"],
    "富勒姆": ["fulham"],
    "伯恩利": ["burnley"],
    "利兹联": ["leeds", "leedsunited"],
    "桑德兰": ["sunderland"],
    "诺丁汉森林": ["nottinghamforest", "nottmforest", "诺丁汉"],
    "阿斯顿维拉": ["astonvilla", "维拉", "阿士东维拉"],
    # 德甲
    "拜仁": ["bayernmunich", "fcbayern", "bayern", "拜仁慕尼黑", "拜仁慕尼黑足球俱乐部"],
    "多特蒙德": ["borussiadortmund", "dortmund", "bvb", "多蒙特"],
    "勒沃库森": ["bayerleverkusen", "leverkusen", "bayer04leverkusen", "利华古逊"],
    "莱比锡红牛": ["rbleipzig", "莱比锡", "rb莱比锡", "莱红牛"],
    "法兰克福": ["eintrachtfrankfurt", "法兰克福足球俱乐部"],
    "斯图加特": ["stuttgart", "vfbstuttgart"],
    "弗赖堡": ["freiburg", "scfreiburg", "弗莱堡"],
    "霍芬海姆": ["hoffenheim", "tsghoffenheim", "1899hoffenheim", "hoffenheim1899"],
    "美因茨": ["mainz", "mainz05", "美因茨05"],
    "门兴": ["borussiamonchengladbach", "monchengladbach", "gladbach", "门兴格拉德巴赫", "慕逊加柏"],
    "柏林联合": ["unionberlin", "柏林联"],
    "奥格斯堡": ["augsburg", "fcaugsburg"],
    "沃尔夫斯堡": ["wolfsburg", "vwolfsburg"],
    "云达不来梅": ["werderbremen", "bremen", "不来梅"],
    "圣保利": ["stpauli", "fcpstpauli"],
    "海登海姆": ["heidenheim"],
    "科隆": ["koln", "fckoln", "cologne", "科隆足球俱乐部"],
    "波鸿": ["bochum", "vflbochum"],
    "汉堡": ["hamburg", "hsv"],
    # 西甲（canonical 与竞彩一致）
    "皇马": ["realmadrid", "皇家马德里"],
    "巴萨": ["fcbarcelona", "barcelona", "巴塞罗那", "巴塞"],
    "马竞": ["atleticomadrid", "atleticodemadrid", "马德里竞技", "马体会", "atleticoclub", "clubatleticodemadrid"],
    "塞维利亚": ["sevilla", "西维尔"],
    "皇家社会": ["realsociedad", "皇社"],
    "毕尔巴鄂": ["athleticbilbao", "athleticclub", "毕尔巴鄂竞技", "毕尔包", "毕尔巴鄂足球俱乐部"],
    "比利亚雷亚尔": ["villarreal", "比利亚雷"],
    "皇家贝蒂斯": ["realbetis", "betis", "贝蒂斯"],
    "赫塔费": ["getafe", "赫塔菲"],
    "赫罗纳": ["girona", "吉罗纳"],
    "塞尔塔": ["celtavigo", "celta", "塞尔塔足球俱乐部"],
    "瓦伦西亚": ["valencia", "华伦西亚"],
    "奥萨苏纳": ["osasuna"],
    "马洛卡": ["mallorca", "rcdmallorca", "马略卡"],
    "阿拉维斯": ["alaves", "阿拉维斯足球俱乐部"],
    "西班牙人": ["espanyol", "爱斯宾奴"],
    "巴列卡诺": ["rayovallecano", "rayo", "华历简奴"],
    "莱万特": ["levante"],
    "埃尔切": ["elche"],
    "皇家奥维耶多": ["realoviedo", "oviedo", "奥维耶多"],
    # 意甲
    "国际米兰": ["inter", "intermilan", "internazionale", "国际米兰足球俱乐部", "国米"],
    "ac米兰": ["acmilan", "milan", "米兰"],
    "尤文图斯": ["juventus", "尤文", "祖云达斯"],
    "那不勒斯": ["napoli", "sscnapoli", "拿坡里"],
    "罗马": ["asroma", "roma", "罗马足球俱乐部"],
    "拉齐奥": ["lazio", "sslazio", "拉素"],
    "亚特兰大": ["atalanta", "亚特兰大足球俱乐部"],
    "佛罗伦萨": ["fiorentina", "acffiorentina", "费伦天拿"],
    "博洛尼亚": ["bologna", "博洛尼亚足球俱乐部"],
    "都灵": ["torino", "都灵足球俱乐部", "拖连奴"],
    "乌迪内斯": ["udinese", "乌甸尼斯"],
    "热那亚": ["genoa", "热那亚足球俱乐部"],
    "卡利亚里": ["cagliari", "卡利亚里足球俱乐部"],
    "莱切": ["lecce", "莱切足球俱乐部"],
    "维罗纳": ["hellasverona", "verona", "维罗纳足球俱乐部"],
    "帕尔马": ["parma", "帕尔马足球俱乐部"],
    "科莫": ["como"],
    "克雷莫纳": ["cremonese"],
    "萨索洛": ["sassuolo"],
    "比萨": ["pisa"],
    # 法甲
    "巴黎圣日耳曼": ["parissaintgermain", "parissg", "psg", "paris", "巴黎", "巴黎圣日门", "巴黎圣杰门"],
    "马赛": ["olympiquemarseille", "marseille", "om", "马赛足球俱乐部", "马赛奥"],
    "里昂": ["olympiquelyon", "lyon", "里昂足球俱乐部"],
    "摩纳哥": ["monaco", "asmonaco"],
    "里尔": ["lille", "里尔足球俱乐部"],
    "朗斯": ["lens", "朗斯足球俱乐部"],
    "尼斯": ["nice", "ognice"],
    "雷恩": ["rennes", "staderennais"],
    "斯特拉斯堡": ["strasbourg", "rcstrasbourgalsace"],
    "布雷斯特": ["brest", "stadebrestois"],
    "南特": ["nantes", "fcnantes"],
    "图卢兹": ["toulouse"],
    "欧塞尔": ["auxerre", "ajauxerre"],
    "昂热": ["angers", "angerssco"],
    "勒阿弗尔": ["lehavre", "lehavreac"],
    "洛里昂": ["lorient", "fclorient"],
    "梅斯": ["metz", "fcmetz"],
    # 欧战/其他（采集器出现过的队名）
    "加拉塔萨雷": ["galatasaray", "加拉塔萨"],
    "拉科鲁尼亚": ["deportivolacoruna", "deportivo", "拉科"],
    "博德闪耀": ["bodoglimt", "bodoglimt", "glimt", "bodo"],
    "圣旺红星": ["redstarbelgrade", "贝尔格莱德红星", "红星"],
    "新英格兰革命": ["newenglandrevolution", "新英格兰"],
    "本菲卡": ["benfica", "本菲卡足球俱乐部", "宾菲加"],
    "费耶诺德": ["feyenoord"],
    "格雷米奥": ["gremio"],
    "布拉干RB": ["rbbragantino", "bragantino", "redbullbragantino"],
    "LASK林茨": ["lasklinz", "lask"],
    "盖斯": ["gais"],
    "桑托斯": ["santos"],
    "布拉迪斯": ["slovanbratislava", "bratislava", "布拉迪斯拉发"],
    "南锡": ["nancy", "asnancy"],
    "索尔纳": ["aikstockholm", "aik", "solna"],
    "米竞技": ["atleticomineiro", "cam", "米内罗竞技"],

    # ---- 欧战常见队名（The Odds API 英文名 → 竞彩中文名）----
    "布斯巴达": ["spartaprague", "spartapraha", "sparta"],
    "奈梅亨": ["necnijmegen", "nec"],
    "奥莫尼亚": ["omonoia", "omonia", "omonianicosia"],
    "费伦茨": ["ferencvrostc", "ferencvaros", "ferencvarosi", "ferencvarositc"],
    "特拉布宗": ["trabzonspor"],
    "萨迪纳摩": ["dinamozagreb"],
    "圣吉联合": ["unionsaintgilloise", "unionstgilloise", "unionsg"],
    "波兹南": ["lechpozna", "lechpoznan", "lech"],
    "阿尔克马": ["azalkmaar", "az"],
    "波尔图": ["porto", "fcporto"],
    "布鲁日": ["clubbrugge", "clubbruggekv", "bruggekv", "brugge"],
    "顿涅茨克矿工": ["shakhtardonetsk", "shakhtar"],
    "费内巴切": ["fenerbahce"],
    "维京": ["viking", "vikingfk"],
    "布拉格斯拉维亚": ["slaviapraha", "slavia", "斯拉维亚"],
    "萨巴赫": ["sabahfk", "sabah", "sabahfa"],
    "葡萄牙体育": ["sportinglisbon", "sportingcp", "sporting"],
    "埃因霍温": ["psveindhoven", "psv"],
    # 亚冠 / 巴西（竞彩口语名）
    "町田泽维": ["machidazelvia", "machida"],
    "上海申花": ["shanghaishenhua", "shenhua"],
    "帕梅拉斯": ["palmeiras"],
    "里莫": ["remo"],
    "布城": ["bristolcity"],
    "悉尼FC": ["sydney", "sydneyfc"],
    "中央海岸": ["centralcoastmariners", "centralcoast"],
}

_WS = re.compile(r"\s+")


def normalize(name: str) -> str:
    """归一化：NFKC 全半角折叠 → 小写 → 按 CJK/拉丁数字边界切词 → 剥组织后缀 → 重接。"""
    s = unicodedata.normalize("NFKC", name or "").lower()
    seg = re.findall(r"[\u4e00-\u9fff]+|[0-9a-z]+", s)
    kept = [t for t in seg if t not in _STRIP_TOKENS]
    return "".join(kept if kept else seg)


def _upsert(db: Session, alias: str, canonical: str) -> None:
    row = db.scalar(select(TeamAlias).where(TeamAlias.alias == alias))
    if row is None:
        db.add(TeamAlias(alias=alias, canonical=canonical))
        db.flush()  # 会话 autoflush=False：立刻可见，避免同批重复 alias 撞唯一键
    else:
        row.canonical = canonical


def seed_aliases(db: Session) -> int:
    """补齐内置别名（不只在空表时），返回新增条数。幂等。

    生产库早期可能只播过一部分别名；新加欧战/英文别名后必须能增量补进去，
    否则 The Odds API 的英文队名会对不上竞彩中文名。
    """
    existing = set(db.scalars(select(TeamAlias.alias)).all())
    n = 0
    for canonical, variants in SEED_ALIASES.items():
        for v in [canonical, *variants]:
            key = normalize(v)
            if not key or key in existing:
                continue
            db.add(TeamAlias(alias=key, canonical=canonical))
            existing.add(key)
            n += 1
    if n:
        db.commit()
    return n


def upsert_aliases(db: Session, canonical: str, variants: list[str]) -> int:
    for v in [canonical, *variants]:
        _upsert(db, normalize(v), canonical)
    db.commit()
    return len(variants) + 1


class Aligner:
    """带缓存的对齐器：一次查询载入全部别名，进程内复用。"""

    def __init__(self, db: Session):
        self._map: dict[str, str] = {}
        for row in db.scalars(select(TeamAlias)):
            self._map[row.alias] = row.canonical

    def has(self, name: str) -> bool:
        return normalize(name) in self._map

    def resolve(self, name: str) -> str:
        n = normalize(name)
        if not n:
            return name
        return self._map.get(n, name)  # 未命中回退原名（保留大小写，显示层友好）
