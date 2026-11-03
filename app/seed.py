import os

from sqlalchemy.orm import Session

from app.models import Category, Ingredient, User
from app.auth import hash_password
from app.nutrition import FOODS, METRIC_KEYS


# (大类, 图标, [(小类, 图标), ...])
CATEGORY_TREE = [
    ("蔬菜", "🥬", [("叶菜类", "🥬"), ("根茎类", "🥕"), ("瓜果类", "🍆"),
                 ("葱蒜类", "🧅"), ("菌菇类", "🍄")]),
    ("肉禽蛋", "🥩", [("猪肉", "🐖"), ("牛羊肉", "🐂"), ("禽肉", "🐔"), ("禽蛋", "🥚")]),
    ("水产", "🐟", [("鱼类", "🐟"), ("虾蟹类", "🦐"), ("贝类", "🦪")]),
    ("主食杂粮", "🌾", [("米面", "🍚"), ("杂粮", "🌽")]),
    ("豆制品", "🫘", []),
    ("水果", "🍎", []),
    ("调料干货", "🧂", [("油盐酱醋", "🧴"), ("香辛料", "🌶️"), ("干杂", "🍄")]),
    ("其他", "📦", []),
]

SAMPLE_INGREDIENTS = [
    # name, 分类, 默认单位, 采购规格, 常用渠道
    ("鸡蛋", "禽蛋", "个", "30枚/盒", "超市"),
    ("猪五花", "猪肉", "克", "500g/盒", "菜市场"),
    ("鸡腿", "禽肉", "个", "按斤买", "菜市场"),
    ("西红柿", "瓜果类", "个", "按斤买", "菜市场"),
    ("土豆", "根茎类", "个", "按斤买", "菜市场"),
    ("大白菜", "叶菜类", "棵", "按斤买", "菜市场"),
    ("生抽", "油盐酱醋", "毫升", "500ml/瓶", "超市"),
    ("老抽", "油盐酱醋", "毫升", "500ml/瓶", "超市"),
    ("盐", "油盐酱醋", "克", "400g/袋", "超市"),
    ("大葱", "葱蒜类", "根", "按斤买", "菜市场"),
    ("姜", "葱蒜类", "块", "按两买", "菜市场"),
    ("蒜", "葱蒜类", "瓣", "按斤买", "菜市场"),
    ("豆腐", "豆制品", "块", "400g/盒", "超市"),
    ("干木耳", "干杂", "克", "100g/袋", "超市"),
    ("小米辣", "香辛料", "个", "按两买", "菜市场"),
    # 做营养估算的常用底料
    ("花生油", "油盐酱醋", "毫升", "5L/桶", "超市"),
    ("白糖", "油盐酱醋", "克", "400g/袋", "超市"),
    ("料酒", "油盐酱醋", "毫升", "500ml/瓶", "超市"),
    ("淀粉", "干杂", "克", "400g/袋", "超市"),
    ("大米", "米面", "克", "10kg/袋", "超市"),
]


def apply_food_data(ing: Ingredient) -> bool:
    """按名字把内置食物成分表写进食材，返回是否发生写入。"""
    food = FOODS.get((ing.name or "").strip())
    if not food:
        return False
    for k in METRIC_KEYS:
        setattr(ing, k + "_per100", float(food.get(k, 0) or 0))
    if not (ing.gram_per_unit or 0):
        ing.gram_per_unit = float(food.get("gram_per_unit", 0) or 0)
    return True


def backfill_nutrition(db: Session) -> int:
    """给已有食材补营养数据（只补空的，不覆盖用户改过的值）。"""
    changed = 0
    for ing in db.query(Ingredient).all():
        if (ing.calories_per100 or 0) > 0:
            continue
        if apply_food_data(ing):
            changed += 1
    if changed:
        db.commit()
    return changed


def seed_initial(db: Session) -> None:
    if db.query(Category).count() > 0:
        return
    order = 0
    for name, icon, subs in CATEGORY_TREE:
        top = Category(name=name, icon=icon, parent_id=None, sort_order=order)
        db.add(top)
        db.flush()
        for sname, sicon in subs:
            db.add(Category(name=sname, icon=sicon, parent_id=top.id, sort_order=0))
        order += 1

    cat_by_name = {c.name: c.id for c in db.query(Category).all()}
    for name, cat, unit, spec, ch in SAMPLE_INGREDIENTS:
        ing = Ingredient(
            name=name,
            category_id=cat_by_name.get(cat),
            default_unit=unit,
            purchase_spec=spec,
            channel=ch,
        )
        apply_food_data(ing)
        db.add(ing)
    db.commit()


def ensure_default_user(db: Session) -> None:
    username = os.environ.get("WEB_USER", "admin")
    if db.query(User).filter_by(username=username).first():
        return
    pw = os.environ.get("WEB_PASSWORD", "homecook")
    db.add(
        User(
            username=username,
            password_hash=hash_password(pw),
            display_name=username,
        )
    )
    db.commit()
