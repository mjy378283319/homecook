import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db import Base


def _now():
    return datetime.datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(64), default="")
    created_at = Column(DateTime, default=_now)


class Category(Base):
    """中式食材分类树（大类 -> 小类）。"""

    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    icon = Column(String(16), default="")  # emoji 图标
    sort_order = Column(Integer, default=0)


class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    alias = Column(String(256), default="")  # 别名，逗号分隔：马铃薯,洋芋
    default_unit = Column(String(16), default="克")
    purchase_spec = Column(String(128), default="")  # 采购规格：500g/袋
    channel = Column(String(64), default="")  # 常去渠道：菜市场/超市/电商/社区团购
    note = Column(String(256), default="")
    created_at = Column(DateTime, default=_now)


class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    title = Column(String(256), nullable=False, index=True)
    cuisine = Column(String(32), default="家常")  # 川/粤/鲁/苏/浙/闽/湘/徽/家常
    difficulty = Column(String(16), default="普通")  # 简单/普通/困难
    prep_time = Column(Integer, default=0)  # 准备分钟
    cook_time = Column(Integer, default=0)  # 烹饪分钟
    servings = Column(Integer, default=2)  # 份数
    taste_tags = Column(String(256), default="")  # 咸鲜;麻辣;酸甜
    method = Column(String(32), default="炒")  # 炒/炖/蒸/煮/炸/烤/凉拌
    tips = Column(Text, default="")  # 小贴士
    source_url = Column(String(512), default="")
    source_name = Column(String(64), default="")  # 下厨房/手工录入
    cover = Column(String(512), default="")
    created_at = Column(DateTime, default=_now)
    ingredients = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    steps = relationship(
        "RecipeStep", back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=True)
    name = Column(String(128), nullable=False)  # 显示名（未关联食材时为自由文本）
    quantity = Column(Float, default=0)
    unit = Column(String(16), default="克")
    note = Column(String(256), default="")
    order_idx = Column(Integer, default=0)
    recipe = relationship("Recipe", back_populates="ingredients")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    step_no = Column(Integer, default=1)
    title = Column(String(128), default="")
    text = Column(Text, nullable=False)
    tip = Column(Text, default="")
    image = Column(String(512), default="")
    recipe = relationship("Recipe", back_populates="steps")


class MealPlan(Base):
    __tablename__ = "meal_plans"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    plan_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    meal_type = Column(String(8), default="晚餐")  # 早餐/午餐/晚餐
    recipe_id = Column(Integer, ForeignKey("recipes.id"))


class ShoppingList(Base):
    __tablename__ = "shopping_lists"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(128), default="采购清单")
    created_at = Column(DateTime, default=_now)
    items = relationship(
        "ShoppingItem", back_populates="shopping_list", cascade="all, delete-orphan"
    )


class ShoppingItem(Base):
    __tablename__ = "shopping_items"
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey("shopping_lists.id"))
    name = Column(String(128), nullable=False)
    quantity = Column(Float, default=0)
    unit = Column(String(16), default="克")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    channel = Column(String(64), default="")
    checked = Column(Boolean, default=False)
    source_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    shopping_list = relationship("ShoppingList", back_populates="items")
