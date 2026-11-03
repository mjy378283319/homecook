from typing import List, Optional

from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    icon: str = ""
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int


class IngredientBase(BaseModel):
    name: str
    category_id: Optional[int] = None
    alias: str = ""
    default_unit: str = "克"
    purchase_spec: str = ""
    channel: str = ""
    note: str = ""


class IngredientCreate(IngredientBase):
    pass


class IngredientOut(IngredientBase):
    id: int


class RecipeIngredientIn(BaseModel):
    ingredient_id: Optional[int] = None
    name: str
    quantity: float = 0
    unit: str = "克"
    note: str = ""
    order_idx: int = 0


class RecipeStepIn(BaseModel):
    step_no: int = 1
    title: str = ""
    text: str
    tip: str = ""


class RecipeBase(BaseModel):
    title: str
    cuisine: str = "家常"
    difficulty: str = "普通"
    prep_time: int = 0
    cook_time: int = 0
    servings: int = 2
    taste_tags: str = ""
    method: str = "炒"
    tips: str = ""
    source_url: str = ""
    source_name: str = ""
    cover: str = ""


class RecipeCreate(RecipeBase):
    ingredients: List[RecipeIngredientIn] = []
    steps: List[RecipeStepIn] = []


class RecipeOut(RecipeBase):
    id: int
    ingredients: List[dict] = []
    steps: List[dict] = []


class MealPlanIn(BaseModel):
    plan_date: str
    meal_type: str = "晚餐"
    recipe_id: int


class ShoppingItemIn(BaseModel):
    name: str
    quantity: float = 0
    unit: str = "克"
    category_id: Optional[int] = None
    channel: str = ""
    checked: bool = False
    source_recipe_id: Optional[int] = None


class ShoppingListCreate(BaseModel):
    name: str = "采购清单"
    items: List[ShoppingItemIn] = []


class LoginIn(BaseModel):
    username: str
    password: str
