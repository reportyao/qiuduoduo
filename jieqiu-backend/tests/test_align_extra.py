"""生产 collector 未解析队名回归：seed_aliases 后必须全部可对齐。"""
from app.modules.align import Aligner, seed_aliases

UNRESOLVED = """
上海海港 不伦瑞克 亚美尼亚 伯顿 克罗地亚 兹沃勒 冈山绿雉 北京国安 博尔顿 卡萨皮亚
吉马良斯 哈马比 国际图尔 土耳其 埃夫斯堡 埃沃斯堡 塞浦路斯 墨胜利 大田市民 大阪樱花
大阪钢巴 奥德汉姆 奥斯 奥林匹亚 威尼斯 威廉二世 安养FC 富山胜利 川崎前锋 巴恩斯利
巴黎圣曼 布罗姆利 布里兰 帕德博恩 弗洛西诺 弗鲁米嫩 德比郡 拉脱维亚 捷克 斯特拉斯
曼谷港务 柏太阳神 格罗宁根 桑坦德 横滨水手 比利时 法马利康 浦和红钻 浦项制铁 特尔斯达
特温特 珀斯 瓦尔韦克 神户胜利 福图纳 科特布斯 米尔顿 纽喷气机 维多利亚 考文垂
芬兰 英格兰 蒙彼利埃 蔚山现代 西班牙 诺茨郡 谢周三 赫尔城 赫尔火花 迈国际
金泉尚武 阿克宁顿 阿尔巴尼 阿尔维卡 阿德莱德 阿罗卡 阿贾克斯 首尔FC 马拉加 鸟栖沙岩
鹿岛鹿角 黑山
""".split()


def test_seed_aliases_covers_production_unresolved(db):
    seed_aliases(db)
    aligner = Aligner(db)
    missing = [name for name in UNRESOLVED if not aligner.has(name)]
    assert missing == []
