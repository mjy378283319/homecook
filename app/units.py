"""中式单位体系与换算引擎。

维度说明：
- weight 重量：克 / 两 / 斤 / 公斤 / 毫克
- volume 体积：毫升 / 升 / 茶匙 / 汤匙 / 勺
- count  计数：个 / 根 / 瓣 / 勺(此处作计数) 等不可跨单位相加
- special 定性：适量 / 少许 / 按口味（无数值）
"""

WEIGHT_TO_G = {
    "克": 1.0, "g": 1.0, "G": 1.0,
    "毫克": 0.001, "mg": 0.001,
    "两": 50.0,
    "斤": 500.0,
    "公斤": 1000.0, "kg": 1000.0, "千克": 1000.0,
}

VOLUME_TO_ML = {
    "毫升": 1.0, "ml": 1.0, "mL": 1.0,
    "升": 1000.0, "L": 1000.0,
    "茶匙": 5.0, "小勺": 5.0,
    "汤匙": 15.0, "大勺": 15.0, "勺": 15.0,
}

COUNT_UNITS = {
    "个", "只", "根", "条", "瓣", "片", "块", "把", "棵", "株",
    "粒", "枚", "碗", "杯", "盘", "份", "张", "尾", "串", "根",
}

SPECIAL_UNITS = {"适量", "少许", "按口味", "若干", "一点点", "自选"}

# 采购清单常用的标准单位候选，用于最终展示
PREFERRED_WEIGHT_UNITS = ["斤", "两", "克"]
PREFERRED_VOLUME_UNITS = ["升", "毫升"]


def dimension(unit: str) -> str:
    u = (unit or "").strip()
    if u in WEIGHT_TO_G:
        return "weight"
    if u in VOLUME_TO_ML:
        return "volume"
    if u in COUNT_UNITS:
        return "count"
    return "special"


def to_base(qty: float, unit: str):
    """转成标准基准量：(数值, 维度)。special 返回 (0, 'special')。"""
    u = (unit or "").strip()
    d = dimension(u)
    if d == "weight":
        return qty * WEIGHT_TO_G[u], "weight"
    if d == "volume":
        return qty * VOLUME_TO_ML[u], "volume"
    if d == "count":
        return qty, "count"
    return 0.0, "special"


def format_weight(grams: float) -> str:
    if grams >= 500:
        jin = int(grams // 500)
        liang = (grams - jin * 500) / 50
        if jin == 0:
            return f"{liang:g}两"
        if abs(liang) < 1e-6:
            return f"{jin}斤"
        return f"{jin}斤{liang:g}两"
    return f"{grams:g}克"


def format_volume(ml: float) -> str:
    if ml >= 1000:
        return f"{ml / 1000:g}升"
    return f"{ml:g}毫升"


def pretty(qty: float, unit: str) -> str:
    """把 (数量, 单位) 渲染成中文可读串。"""
    u = (unit or "").strip()
    d = dimension(u)
    if d == "weight":
        return f"{format_weight(qty * WEIGHT_TO_G[u])}"
    if d == "volume":
        return f"{format_volume(qty * VOLUME_TO_ML[u])}"
    if d == "special":
        return u or "适量"
    return f"{qty:g}{u}" if u else f"{qty:g}"


def is_special(unit: str) -> bool:
    return dimension(unit) == "special"
