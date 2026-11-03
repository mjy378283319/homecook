"""营养估算引擎。

设计要点：
- 指标顺序固定（11 项），与 Mealie 一致，前端与导出共用同一份定义；
- 食材库按「每 100g 可食部」存 11 项营养，菜谱按用量 × 每 100g 累加；
- 计数单位（个/根/瓣/块）靠食材的 gram_per_unit 折算；无法折算的（适量/少许）计入未覆盖清单；
- 体积按 1ml ≈ 1g 近似（油、酱油严格说密度不同，误差约 5%~10%）。

数据为《中国食物成分表（第 6 版）》的常见值近似，用于日常参考，不作为医学依据。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.units import WEIGHT_TO_G, VOLUME_TO_ML, dimension

# 固定顺序：卡路里 → 碳水 → 胆固醇 → 脂肪 → 纤维 → 蛋白质
#           → 饱和脂肪 → 钠 → 糖 → 反式脂肪 → 不饱和脂肪
METRICS: List[dict] = [
    {"key": "calories", "label": "卡路里", "unit": "kcal", "dec": 0},
    {"key": "carbohydrate", "label": "碳水化合物", "unit": "g", "dec": 1},
    {"key": "cholesterol", "label": "胆固醇", "unit": "mg", "dec": 0},
    {"key": "fat", "label": "脂肪", "unit": "g", "dec": 1},
    {"key": "fiber", "label": "纤维", "unit": "g", "dec": 1},
    {"key": "protein", "label": "蛋白质", "unit": "g", "dec": 1},
    {"key": "saturated_fat", "label": "饱和脂肪", "unit": "g", "dec": 1},
    {"key": "sodium", "label": "钠", "unit": "mg", "dec": 0},
    {"key": "sugar", "label": "糖", "unit": "g", "dec": 1},
    {"key": "trans_fat", "label": "反式脂肪", "unit": "g", "dec": 1},
    {"key": "unsaturated_fat", "label": "不饱和脂肪", "unit": "g", "dec": 1},
]

METRIC_KEYS = [m["key"] for m in METRICS]

# 食材每 100g 可食部营养（约值）+ 每 1 个/根/瓣/块的克重
# calories(kcal) carbohydrate(g) cholesterol(mg) fat(g) fiber(g) protein(g)
# saturated_fat(g) sodium(mg) sugar(g) trans_fat(g) unsaturated_fat(g)
FOODS: Dict[str, dict] = {
    # 蛋类
    "鸡蛋": dict(calories=144, carbohydrate=2.8, cholesterol=585, fat=8.8, fiber=0, protein=13.3,
               saturated_fat=2.6, sodium=131, sugar=0, trans_fat=0, unsaturated_fat=5.6, gram_per_unit=50),
    "鸭蛋": dict(calories=180, carbohydrate=3.1, cholesterol=565, fat=13, fiber=0, protein=12.6,
               saturated_fat=3.8, sodium=106, sugar=0, trans_fat=0, unsaturated_fat=8.5, gram_per_unit=70),
    # 畜肉
    "猪五花": dict(calories=395, carbohydrate=2.4, cholesterol=80, fat=37, fiber=0, protein=13.6,
                saturated_fat=13.9, sodium=59, sugar=0, trans_fat=0, unsaturated_fat=19.4, gram_per_unit=0),
    "猪肉": dict(calories=395, carbohydrate=2.4, cholesterol=80, fat=37, fiber=0, protein=13.6,
               saturated_fat=13.9, sodium=59, sugar=0, trans_fat=0, unsaturated_fat=19.4, gram_per_unit=0),
    "猪里脊": dict(calories=155, carbohydrate=0.7, cholesterol=55, fat=7.9, fiber=0, protein=20.2,
                saturated_fat=3.1, sodium=43, sugar=0, trans_fat=0, unsaturated_fat=4.2, gram_per_unit=0),
    "排骨": dict(calories=278, carbohydrate=0.7, cholesterol=146, fat=20.4, fiber=0, protein=16.7,
               saturated_fat=7.8, sodium=62, sugar=0, trans_fat=0, unsaturated_fat=11.0, gram_per_unit=0),
    "牛肉": dict(calories=125, carbohydrate=2.0, cholesterol=84, fat=4.2, fiber=0, protein=19.9,
               saturated_fat=2.0, sodium=84, sugar=0, trans_fat=0, unsaturated_fat=1.6, gram_per_unit=0),
    "羊肉": dict(calories=203, carbohydrate=0, cholesterol=111, fat=14.1, fiber=0, protein=19,
               saturated_fat=6.6, sodium=81, sugar=0, trans_fat=0, unsaturated_fat=6.1, gram_per_unit=0),
    # 禽肉
    "鸡腿": dict(calories=181, carbohydrate=0, cholesterol=162, fat=13, fiber=0, protein=16,
               saturated_fat=4.3, sodium=64, sugar=0, trans_fat=0, unsaturated_fat=7.6, gram_per_unit=200),
    "鸡胸肉": dict(calories=133, carbohydrate=2.5, cholesterol=82, fat=5, fiber=0, protein=19.4,
                saturated_fat=1.5, sodium=63, sugar=0, trans_fat=0, unsaturated_fat=2.6, gram_per_unit=0),
    "整鸡": dict(calories=167, carbohydrate=1.3, cholesterol=106, fat=9.4, fiber=0, protein=19.3,
               saturated_fat=3.3, sodium=63, sugar=0, trans_fat=0, unsaturated_fat=5.0, gram_per_unit=1200),
    "鸭肉": dict(calories=240, carbohydrate=0.2, cholesterol=94, fat=19.7, fiber=0, protein=15.5,
               saturated_fat=5.1, sodium=69, sugar=0, trans_fat=0, unsaturated_fat=12.6, gram_per_unit=0),
    # 水产
    "草鱼": dict(calories=113, carbohydrate=0, cholesterol=86, fat=5.2, fiber=0, protein=16.6,
               saturated_fat=1.2, sodium=46, sugar=0, trans_fat=0, unsaturated_fat=2.9, gram_per_unit=0),
    "鲈鱼": dict(calories=105, carbohydrate=0, cholesterol=86, fat=3.4, fiber=0, protein=18.6,
               saturated_fat=1.1, sodium=144, sugar=0, trans_fat=0, unsaturated_fat=1.8, gram_per_unit=500),
    "带鱼": dict(calories=127, carbohydrate=3.1, cholesterol=76, fat=4.9, fiber=0, protein=17.7,
               saturated_fat=1.7, sodium=150, sugar=0, trans_fat=0, unsaturated_fat=2.5, gram_per_unit=0),
    "鲫鱼": dict(calories=108, carbohydrate=3.8, cholesterol=130, fat=2.7, fiber=0, protein=17.1,
               saturated_fat=0.9, sodium=41, sugar=0, trans_fat=0, unsaturated_fat=1.3, gram_per_unit=200),
    "虾": dict(calories=93, carbohydrate=2.8, cholesterol=193, fat=0.8, fiber=0, protein=18.6,
              saturated_fat=0.2, sodium=165, sugar=0, trans_fat=0, unsaturated_fat=0.4, gram_per_unit=12),
    "虾仁": dict(calories=93, carbohydrate=2.8, cholesterol=193, fat=0.8, fiber=0, protein=18.6,
               saturated_fat=0.2, sodium=165, sugar=0, trans_fat=0, unsaturated_fat=0.4, gram_per_unit=0),
    "鱿鱼": dict(calories=84, carbohydrate=0, cholesterol=268, fat=1.1, fiber=0, protein=17.4,
               saturated_fat=0.3, sodium=134, sugar=0, trans_fat=0, unsaturated_fat=0.5, gram_per_unit=0),
    "蛤蜊": dict(calories=62, carbohydrate=2.8, cholesterol=149, fat=1.1, fiber=0, protein=10.1,
               saturated_fat=0.2, sodium=425, sugar=0, trans_fat=0, unsaturated_fat=0.3, gram_per_unit=0),
    # 蔬菜
    "西红柿": dict(calories=20, carbohydrate=4.0, cholesterol=0, fat=0.2, fiber=0.5, protein=0.9,
                saturated_fat=0, sodium=5, sugar=2.6, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=150),
    "番茄": dict(calories=20, carbohydrate=4.0, cholesterol=0, fat=0.2, fiber=0.5, protein=0.9,
               saturated_fat=0, sodium=5, sugar=2.6, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=150),
    "土豆": dict(calories=81, carbohydrate=17.8, cholesterol=0, fat=0.2, fiber=1.1, protein=2.6,
               saturated_fat=0.1, sodium=5, sugar=1.2, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=200),
    "马铃薯": dict(calories=81, carbohydrate=17.8, cholesterol=0, fat=0.2, fiber=1.1, protein=2.6,
                saturated_fat=0.1, sodium=5, sugar=1.2, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=200),
    "大白菜": dict(calories=20, carbohydrate=3.4, cholesterol=0, fat=0.1, fiber=0.8, protein=1.5,
                saturated_fat=0, sodium=57, sugar=1.1, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=1500),
    "小白菜": dict(calories=17, carbohydrate=2.4, cholesterol=0, fat=0.2, fiber=0.7, protein=1.5,
                saturated_fat=0, sodium=73, sugar=0.6, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=300),
    "菠菜": dict(calories=28, carbohydrate=4.5, cholesterol=0, fat=0.3, fiber=1.7, protein=2.6,
               saturated_fat=0.1, sodium=85, sugar=0.4, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=300),
    "西兰花": dict(calories=36, carbohydrate=4.3, cholesterol=0, fat=0.6, fiber=1.6, protein=4.1,
                saturated_fat=0.1, sodium=19, sugar=1.5, trans_fat=0, unsaturated_fat=0.4, gram_per_unit=400),
    "黄瓜": dict(calories=16, carbohydrate=2.9, cholesterol=0, fat=0.2, fiber=0.5, protein=0.8,
               saturated_fat=0, sodium=5, sugar=1.5, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=200),
    "茄子": dict(calories=23, carbohydrate=4.9, cholesterol=0, fat=0.1, fiber=1.3, protein=1.1,
               saturated_fat=0, sodium=5, sugar=3.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=300),
    "青椒": dict(calories=22, carbohydrate=5.4, cholesterol=0, fat=0.2, fiber=1.4, protein=1.0,
               saturated_fat=0, sodium=3, sugar=2.4, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=100),
    "尖椒": dict(calories=22, carbohydrate=5.4, cholesterol=0, fat=0.2, fiber=1.4, protein=1.0,
               saturated_fat=0, sodium=3, sugar=2.4, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=40),
    "小米辣": dict(calories=32, carbohydrate=5.6, cholesterol=0, fat=0.4, fiber=1.4, protein=1.3,
                saturated_fat=0.1, sodium=9, sugar=2.8, trans_fat=0, unsaturated_fat=0.2, gram_per_unit=5),
    "胡萝卜": dict(calories=39, carbohydrate=8.8, cholesterol=0, fat=0.2, fiber=1.1, protein=1.0,
                saturated_fat=0, sodium=71, sugar=4.5, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=150),
    "洋葱": dict(calories=40, carbohydrate=9.0, cholesterol=0, fat=0.2, fiber=0.9, protein=1.1,
               saturated_fat=0, sodium=4, sugar=4.2, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=200),
    "冬瓜": dict(calories=12, carbohydrate=2.6, cholesterol=0, fat=0.2, fiber=0.7, protein=0.4,
               saturated_fat=0, sodium=1.8, sugar=1.2, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=1000),
    "南瓜": dict(calories=23, carbohydrate=5.3, cholesterol=0, fat=0.1, fiber=0.8, protein=0.7,
               saturated_fat=0, sodium=0.8, sugar=2.8, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=800),
    "豆芽": dict(calories=18, carbohydrate=2.6, cholesterol=0, fat=0.1, fiber=0.8, protein=2.1,
               saturated_fat=0, sodium=4.2, sugar=0.1, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "绿豆芽": dict(calories=18, carbohydrate=2.6, cholesterol=0, fat=0.1, fiber=0.8, protein=2.1,
                saturated_fat=0, sodium=4.2, sugar=0.1, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "芹菜": dict(calories=22, carbohydrate=4.5, cholesterol=0, fat=0.2, fiber=1.2, protein=0.8,
               saturated_fat=0, sodium=159, sugar=1.5, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=40),
    "韭菜": dict(calories=26, carbohydrate=4.6, cholesterol=0, fat=0.4, fiber=1.4, protein=2.4,
               saturated_fat=0.1, sodium=8.1, sugar=1.5, trans_fat=0, unsaturated_fat=0.2, gram_per_unit=20),
    "大葱": dict(calories=30, carbohydrate=6.5, cholesterol=0, fat=0.3, fiber=1.3, protein=1.7,
               saturated_fat=0.1, sodium=4.9, sugar=2.4, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=50),
    "小葱": dict(calories=27, carbohydrate=4.9, cholesterol=0, fat=0.4, fiber=1.4, protein=1.6,
               saturated_fat=0.1, sodium=10.4, sugar=1.8, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=10),
    "姜": dict(calories=46, carbohydrate=10.3, cholesterol=0, fat=0.6, fiber=2.7, protein=1.3,
              saturated_fat=0.2, sodium=14.9, sugar=2.0, trans_fat=0, unsaturated_fat=0.2, gram_per_unit=15),
    "蒜": dict(calories=128, carbohydrate=27.6, cholesterol=0, fat=0.2, fiber=1.1, protein=4.5,
              saturated_fat=0, sodium=19.6, sugar=1.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=5),
    "大蒜": dict(calories=128, carbohydrate=27.6, cholesterol=0, fat=0.2, fiber=1.1, protein=4.5,
               saturated_fat=0, sodium=19.6, sugar=1.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=5),
    # 菌菇
    "香菇": dict(calories=26, carbohydrate=5.2, cholesterol=0, fat=0.3, fiber=3.3, protein=2.2,
               saturated_fat=0.1, sodium=1.4, sugar=1.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=20),
    "金针菇": dict(calories=32, carbohydrate=6.0, cholesterol=0, fat=0.4, fiber=2.7, protein=2.4,
                saturated_fat=0.1, sodium=4.3, sugar=1.2, trans_fat=0, unsaturated_fat=0.2, gram_per_unit=0),
    "干木耳": dict(calories=265, carbohydrate=65.6, cholesterol=0, fat=1.5, fiber=29.9, protein=12.1,
                saturated_fat=0.4, sodium=48.5, sugar=0, trans_fat=0, unsaturated_fat=0.8, gram_per_unit=0),
    "木耳": dict(calories=27, carbohydrate=6.0, cholesterol=0, fat=0.2, fiber=2.6, protein=1.5,
               saturated_fat=0.1, sodium=8.5, sugar=0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    # 豆制品
    "豆腐": dict(calories=116, carbohydrate=3.0, cholesterol=0, fat=4.8, fiber=0.5, protein=12.2,
               saturated_fat=0.7, sodium=7.3, sugar=0.5, trans_fat=0, unsaturated_fat=3.8, gram_per_unit=400),
    "嫩豆腐": dict(calories=57, carbohydrate=2.4, cholesterol=0, fat=2.5, fiber=0.3, protein=6.2,
                saturated_fat=0.4, sodium=5.0, sugar=0.4, trans_fat=0, unsaturated_fat=1.9, gram_per_unit=400),
    "豆干": dict(calories=140, carbohydrate=6.2, cholesterol=0, fat=6.5, fiber=1.0, protein=16.2,
               saturated_fat=1.0, sodium=76, sugar=0.6, trans_fat=0, unsaturated_fat=5.0, gram_per_unit=50),
    # 主食
    "大米": dict(calories=346, carbohydrate=77.9, cholesterol=0, fat=0.8, fiber=0.7, protein=7.4,
               saturated_fat=0.2, sodium=3.8, sugar=0.1, trans_fat=0, unsaturated_fat=0.3, gram_per_unit=0),
    "米饭": dict(calories=116, carbohydrate=25.9, cholesterol=0, fat=0.3, fiber=0.3, protein=2.6,
               saturated_fat=0.1, sodium=2.5, sugar=0.1, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=150),
    "面粉": dict(calories=348, carbohydrate=73.6, cholesterol=0, fat=1.5, fiber=2.7, protein=12.4,
               saturated_fat=0.3, sodium=3.1, sugar=0.3, trans_fat=0, unsaturated_fat=0.6, gram_per_unit=0),
    "面条": dict(calories=284, carbohydrate=58.0, cholesterol=0, fat=1.6, fiber=1.5, protein=8.3,
               saturated_fat=0.3, sodium=28, sugar=0.4, trans_fat=0, unsaturated_fat=0.6, gram_per_unit=0),
    "玉米": dict(calories=112, carbohydrate=22.8, cholesterol=0, fat=1.2, fiber=2.9, protein=4.0,
               saturated_fat=0.3, sodium=1.1, sugar=3.2, trans_fat=0, unsaturated_fat=0.5, gram_per_unit=200),
    "红薯": dict(calories=106, carbohydrate=24.7, cholesterol=0, fat=0.2, fiber=1.6, protein=1.1,
               saturated_fat=0.1, sodium=28.5, sugar=5.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=250),
    # 调料
    "花生油": dict(calories=899, carbohydrate=0, cholesterol=0, fat=99.9, fiber=0, protein=0,
                saturated_fat=19.0, sodium=0, sugar=0, trans_fat=0.1, unsaturated_fat=80.0, gram_per_unit=0),
    "食用油": dict(calories=899, carbohydrate=0, cholesterol=0, fat=99.9, fiber=0, protein=0,
               saturated_fat=19.0, sodium=0, sugar=0, trans_fat=0.1, unsaturated_fat=80.0, gram_per_unit=0),
    "菜籽油": dict(calories=899, carbohydrate=0, cholesterol=0, fat=99.9, fiber=0, protein=0,
                saturated_fat=13.0, sodium=0, sugar=0, trans_fat=0.1, unsaturated_fat=86.0, gram_per_unit=0),
    "生抽": dict(calories=60, carbohydrate=9.0, cholesterol=0, fat=0.1, fiber=0, protein=6.0,
               saturated_fat=0, sodium=6000, sugar=4.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "老抽": dict(calories=70, carbohydrate=12.0, cholesterol=0, fat=0.1, fiber=0, protein=6.5,
               saturated_fat=0, sodium=6500, sugar=8.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "酱油": dict(calories=63, carbohydrate=10.1, cholesterol=0, fat=0.1, fiber=0, protein=5.6,
               saturated_fat=0, sodium=5757, sugar=5.8, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "盐": dict(calories=0, carbohydrate=0, cholesterol=0, fat=0, fiber=0, protein=0,
              saturated_fat=0, sodium=39311, sugar=0, trans_fat=0, unsaturated_fat=0, gram_per_unit=0),
    "白糖": dict(calories=400, carbohydrate=99.9, cholesterol=0, fat=0, fiber=0, protein=0,
               saturated_fat=0, sodium=0.4, sugar=99.9, trans_fat=0, unsaturated_fat=0, gram_per_unit=0),
    "冰糖": dict(calories=397, carbohydrate=99.3, cholesterol=0, fat=0, fiber=0, protein=0,
               saturated_fat=0, sodium=0.4, sugar=99.3, trans_fat=0, unsaturated_fat=0, gram_per_unit=0),
    "料酒": dict(calories=63, carbohydrate=1.0, cholesterol=0, fat=0, fiber=0, protein=0.2,
               saturated_fat=0, sodium=1500, sugar=0.5, trans_fat=0, unsaturated_fat=0, gram_per_unit=0),
    "醋": dict(calories=31, carbohydrate=4.9, cholesterol=0, fat=0.3, fiber=0, protein=2.1,
              saturated_fat=0, sodium=262, sugar=0.9, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "蚝油": dict(calories=114, carbohydrate=22.0, cholesterol=0, fat=0.2, fiber=0, protein=5.1,
               saturated_fat=0, sodium=4500, sugar=15.0, trans_fat=0, unsaturated_fat=0.1, gram_per_unit=0),
    "淀粉": dict(calories=346, carbohydrate=85.0, cholesterol=0, fat=0.1, fiber=0, protein=1.5,
               saturated_fat=0, sodium=6, sugar=0, trans_fat=0, unsaturated_fat=0, gram_per_unit=0),
    "豆瓣酱": dict(calories=178, carbohydrate=15.0, cholesterol=0, fat=5.0, fiber=4.0, protein=12.0,
                saturated_fat=0.8, sodium=6000, sugar=2.0, trans_fat=0, unsaturated_fat=3.5, gram_per_unit=0),
    "花椒": dict(calories=258, carbohydrate=37.8, cholesterol=0, fat=8.9, fiber=28.7, protein=6.7,
               saturated_fat=1.1, sodium=47, sugar=0, trans_fat=0, unsaturated_fat=6.2, gram_per_unit=0),
    "干辣椒": dict(calories=298, carbohydrate=57.4, cholesterol=0, fat=8.4, fiber=41.7, protein=15.4,
                saturated_fat=1.5, sodium=14, sugar=0, trans_fat=0, unsaturated_fat=5.5, gram_per_unit=0),
}


def zero_metrics() -> Dict[str, float]:
    return {k: 0.0 for k in METRIC_KEYS}


def _grams(quantity: float, unit: str, gram_per_unit: float) -> Optional[float]:
    """把 (数量, 单位) 折算成克。无法折算返回 None。"""
    u = (unit or "").strip()
    d = dimension(u)
    if d == "weight":
        return quantity * WEIGHT_TO_G[u]
    if d == "volume":
        return quantity * VOLUME_TO_ML[u]  # 1ml ≈ 1g 近似
    if d == "count":
        return quantity * gram_per_unit if gram_per_unit > 0 else None
    return None


def _per100_of(ri) -> Optional[dict]:
    """取菜谱用料的「每 100g」营养与单件克重。优先关联食材，其次按名字兜底。"""
    ing = getattr(ri, "ingredient", None)
    gram = getattr(ing, "gram_per_unit", 0) or 0
    row = None
    if ing is not None and (ing.calories_per100 or 0) > 0:
        row = {k: getattr(ing, k + "_per100", 0) or 0 for k in METRIC_KEYS}
    else:
        food = FOODS.get((ri.name or "").strip())
        if food:
            row = {k: food[k] for k in METRIC_KEYS}
            if not gram:
                gram = food.get("gram_per_unit", 0) or 0
    return (row, gram) if row else (None, gram)


def summarize(recipe) -> dict:
    """返回菜谱营养：全锅总量、每份、每 100g，以及覆盖率与未计入项。"""
    manual = (recipe.nutrition_mode or "auto") == "manual"
    servings = recipe.servings or 1

    if manual:
        total = {k: float(getattr(recipe, "manual_" + k, 0) or 0) for k in METRIC_KEYS}
        return _pack(total, servings, mode="manual", covered_g=0.0,
                     matched=0, total_items=len(recipe.ingredients), unmatched=[])

    total = zero_metrics()
    covered_g = 0.0
    matched = 0
    unmatched: List[str] = []

    for ri in recipe.ingredients:
        per100, gram = _per100_of(ri)
        if per100 is None:
            unmatched.append(ri.name)
            continue
        g = _grams(float(ri.quantity or 0), ri.unit or "", gram)
        if g is None or g <= 0:
            unmatched.append(f"{ri.name}（{ri.unit or '适量'}无法折算克重）")
            continue
        matched += 1
        covered_g += g
        for k in METRIC_KEYS:
            total[k] += per100[k] * g / 100.0

    return _pack(total, servings, mode="auto", covered_g=covered_g, matched=matched,
                 total_items=len(recipe.ingredients), unmatched=unmatched)


def _round(value: float, dec: int) -> float:
    return round(float(value), dec)


def _pack(total: Dict[str, float], servings: int, mode: str, covered_g: float,
          matched: int, total_items: int, unmatched: List[str]) -> dict:
    per_serving = {k: total[k] / servings for k in METRIC_KEYS}
    per_100g = {k: (total[k] / covered_g * 100.0 if covered_g >= 10 else 0.0) for k in METRIC_KEYS}
    dec = {m["key"]: m["dec"] for m in METRICS}
    return {
        "mode": mode,
        "servings": servings,
        "has_data": any(total[k] > 0 for k in METRIC_KEYS) or matched > 0,
        "total": {k: _round(total[k], dec[k]) for k in METRIC_KEYS},
        "per_serving": {k: _round(per_serving[k], dec[k]) for k in METRIC_KEYS},
        "per_100g": {k: _round(per_100g[k], dec[k]) for k in METRIC_KEYS},
        "covered_g": round(covered_g, 1),
        "matched": matched,
        "total_items": total_items,
        "unmatched": unmatched[:12],
        "metrics": METRICS,
    }
