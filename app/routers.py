from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth import create_session, get_current_user, verify_password
from app.covers import delete_cover, save_cover, save_cover_from_url
from app.db import get_db
from app.import_xcf import import_from_url
from app.nutrition import METRICS, METRIC_KEYS, summarize
from app.models import (
    Category,
    Ingredient,
    MealPlan,
    Recipe,
    RecipeIngredient,
    RecipeStep,
    ShoppingItem,
    ShoppingList,
    User,
)
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    IngredientCreate,
    IngredientOut,
    LoginIn,
    MealPlanIn,
    NutritionIn,
    RecipeCreate,
    RecipeOut,
    ShoppingItemIn,
    ShoppingListCreate,
)
from app.units import dimension, pretty, to_base

router = APIRouter()


# ---------- 鉴权 ----------
@router.post("/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_session(user.id)
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )
    return {"user": user.username, "display_name": user.display_name}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


def _try_user(request: Request, db: Session) -> Optional[User]:
    from app.auth import _unsign
    raw = request.cookies.get("session")
    if not raw:
        return None
    val = _unsign(raw)
    if not val:
        return None
    return db.get(User, int(val))


def _get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    return _try_user(request, db)


@router.get("/me")
def me(request_user: Optional[User] = Depends(_get_optional_user)):
    if request_user is None:
        return {"user": None}
    return {"user": request_user.username, "display_name": request_user.display_name}


# ---------- 元数据选项 ----------
@router.get("/meta/options")
def meta_options():
    return {
        "cuisines": ["家常", "川菜", "粤菜", "鲁菜", "苏菜", "浙菜", "闽菜", "湘菜", "徽菜", "东北菜", "西北菜"],
        "difficulties": ["简单", "普通", "困难"],
        "methods": ["炒", "炖", "蒸", "煮", "炸", "烤", "凉拌", "煎", "焖", "煲"],
        "meal_types": ["早餐", "午餐", "晚餐", "加餐"],
        "taste_tags": ["咸鲜", "麻辣", "酸辣", "酸甜", "清淡", "鲜香", "酱香", "甜口", "咸甜"],
        "channels": ["菜市场", "超市", "电商", "社区团购", "生鲜App"],
        "nutrition": METRICS,
    }


# ---------- 分类 ----------
@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order, Category.id).all()


@router.post("/categories", response_model=CategoryOut)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db),
                    _: User = Depends(get_current_user)):
    c = Category(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/categories/{cid}")
def delete_category(cid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    c = db.get(Category, cid)
    if not c:
        raise HTTPException(status_code=404, detail="分类不存在")
    if db.query(Ingredient).filter_by(category_id=cid).first():
        raise HTTPException(status_code=400, detail="该分类下还有食材，无法删除")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---------- 食材库 ----------
@router.get("/ingredients", response_model=List[IngredientOut])
def list_ingredients(q: str = "", db: Session = Depends(get_db)):
    query = db.query(Ingredient)
    if q:
        query = query.filter(Ingredient.name.contains(q))
    return query.order_by(Ingredient.name).all()


@router.post("/ingredients", response_model=IngredientOut)
def create_ingredient(payload: IngredientCreate, db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    if db.query(Ingredient).filter_by(name=payload.name).first():
        raise HTTPException(status_code=400, detail="食材已存在")
    ing = Ingredient(**payload.model_dump())
    db.add(ing)
    db.commit()
    db.refresh(ing)
    return ing


@router.put("/ingredients/{iid}", response_model=IngredientOut)
def update_ingredient(iid: int, payload: IngredientCreate, db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    """更新食材信息，含每 100g 营养与单件克重（营养估算的数据源）。"""
    ing = db.get(Ingredient, iid)
    if not ing:
        raise HTTPException(status_code=404, detail="食材不存在")
    for k, v in payload.model_dump().items():
        if k == "name" and v != ing.name:
            if db.query(Ingredient).filter_by(name=v).first():
                raise HTTPException(status_code=400, detail="同名食材已存在")
        setattr(ing, k, v)
    db.commit()
    db.refresh(ing)
    return ing


@router.patch("/ingredients/{iid}/nutrition", response_model=IngredientOut)
def patch_ingredient_nutrition(iid: int, payload: dict, db: Session = Depends(get_db),
                               _: User = Depends(get_current_user)):
    """只改营养字段，方便前端小表单提交。"""
    ing = db.get(Ingredient, iid)
    if not ing:
        raise HTTPException(status_code=404, detail="食材不存在")
    allowed = {k + "_per100" for k in METRIC_KEYS} | {"gram_per_unit"}
    for k, v in (payload or {}).items():
        if k not in allowed:
            continue
        try:
            setattr(ing, k, max(0.0, float(v or 0)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{k} 必须是数字")
    db.commit()
    db.refresh(ing)
    return ing


@router.delete("/ingredients/{iid}")
def delete_ingredient(iid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ing = db.get(Ingredient, iid)
    if not ing:
        raise HTTPException(status_code=404, detail="食材不存在")
    db.delete(ing)
    db.commit()
    return {"ok": True}


# ---------- 菜谱 ----------
def _recipe_out(r: Recipe) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "cuisine": r.cuisine,
        "difficulty": r.difficulty,
        "prep_time": r.prep_time,
        "cook_time": r.cook_time,
        "servings": r.servings,
        "taste_tags": r.taste_tags,
        "method": r.method,
        "tips": r.tips,
        "source_url": r.source_url,
        "source_name": r.source_name,
        "cover": r.cover,
        "ingredients": [
            {"id": i.id, "ingredient_id": i.ingredient_id, "name": i.name,
             "quantity": i.quantity, "unit": i.unit, "note": i.note, "order_idx": i.order_idx}
            for i in sorted(r.ingredients, key=lambda x: x.order_idx)
        ],
        "steps": [
            {"id": s.id, "step_no": s.step_no, "title": s.title, "text": s.text, "tip": s.tip}
            for s in sorted(r.steps, key=lambda x: x.step_no)
        ],
        "nutrition": summarize(r),
    }


@router.get("/recipes", response_model=List[RecipeOut])
def list_recipes(
    q: str = "", cuisine: str = "", method: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Recipe)
    if q:
        query = query.filter(Recipe.title.contains(q))
    if cuisine:
        query = query.filter(Recipe.cuisine == cuisine)
    if method:
        query = query.filter(Recipe.method == method)
    recipes = query.order_by(Recipe.id.desc()).limit(200).all()
    return [_recipe_out(r) for r in recipes]


@router.get("/recipes/{rid}", response_model=RecipeOut)
def get_recipe(rid: int, db: Session = Depends(get_db)):
    r = db.get(Recipe, rid)
    if not r:
        raise HTTPException(status_code=404, detail="菜谱不存在")
    return _recipe_out(r)


def _base_fields():
    from app.schemas import RecipeBase
    return list(RecipeBase.model_fields.keys())


def _link_ingredients(db: Session, r: Recipe) -> None:
    """用料名自动关联食材库，营养估算才能取到每 100g 数据。"""
    names = {i.name: i.id for i in db.query(Ingredient).all()}
    for ri in r.ingredients:
        if not ri.ingredient_id:
            ri.ingredient_id = names.get((ri.name or "").strip())


@router.post("/recipes", response_model=RecipeOut)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    r = Recipe(**{k: getattr(payload, k) for k in _base_fields()})
    for ing in payload.ingredients:
        r.ingredients.append(RecipeIngredient(**ing.model_dump()))
    for st in payload.steps:
        r.steps.append(RecipeStep(**st.model_dump()))
    _link_ingredients(db, r)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@router.put("/recipes/{rid}/nutrition", response_model=RecipeOut)
def set_recipe_nutrition(rid: int, payload: NutritionIn, db: Session = Depends(get_db),
                         _: User = Depends(get_current_user)):
    """切换营养口径：auto 按食材估算，manual 用手填的全锅总量。"""
    r = db.get(Recipe, rid)
    if not r:
        raise HTTPException(status_code=404, detail="菜谱不存在")
    mode = (payload.mode or "auto").strip().lower()
    if mode not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="mode 只能是 auto 或 manual")
    r.nutrition_mode = mode
    if mode == "manual":
        for k, v in (payload.values or {}).items():
            if k not in METRIC_KEYS:
                continue
            try:
                setattr(r, "manual_" + k, max(0.0, float(v or 0)))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{k} 必须是数字")
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@router.put("/recipes/{rid}", response_model=RecipeOut)
def update_recipe(rid: int, payload: RecipeCreate, db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    r = db.get(Recipe, rid)
    if not r:
        raise HTTPException(status_code=404, detail="菜谱不存在")
    for f in _base_fields():
        setattr(r, f, getattr(payload, f))
    for i in list(r.ingredients):
        db.delete(i)
    for s in list(r.steps):
        db.delete(s)
    db.flush()
    for ing in payload.ingredients:
        r.ingredients.append(RecipeIngredient(**ing.model_dump()))
    for st in payload.steps:
        r.steps.append(RecipeStep(**st.model_dump()))
    _link_ingredients(db, r)
    db.commit()
    db.refresh(r)
    return _recipe_out(r)


@router.delete("/recipes/{rid}")
def delete_recipe(rid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    r = db.get(Recipe, rid)
    if not r:
        raise HTTPException(status_code=404, detail="菜谱不存在")
    cover = r.cover
    db.delete(r)
    db.commit()
    delete_cover(cover)
    return {"ok": True}


@router.post("/recipes/{rid}/cover")
async def upload_recipe_cover(rid: int, file: UploadFile = File(...),
                              db: Session = Depends(get_db),
                              _: User = Depends(get_current_user)):
    r = db.get(Recipe, rid)
    if not r:
        raise HTTPException(status_code=404, detail="菜谱不存在")
    raw = await file.read()
    try:
        cover = save_cover(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    old = r.cover
    r.cover = cover
    db.commit()
    delete_cover(old)
    return {"cover": cover}


@router.delete("/recipes/{rid}/cover")
def remove_recipe_cover(rid: int, db: Session = Depends(get_db),
                        _: User = Depends(get_current_user)):
    r = db.get(Recipe, rid)
    if not r:
        raise HTTPException(status_code=404, detail="菜谱不存在")
    old = r.cover
    r.cover = ""
    db.commit()
    delete_cover(old)
    return {"ok": True}


# ---------- 周菜单 ----------
@router.get("/meal-plan")
def list_meal_plan(date_from: str = Query(None), date_to: str = Query(None),
                   db: Session = Depends(get_db)):
    q = db.query(MealPlan)
    if date_from:
        q = q.filter(MealPlan.plan_date >= date_from)
    if date_to:
        q = q.filter(MealPlan.plan_date <= date_to)
    return q.order_by(MealPlan.plan_date).all()


@router.post("/meal-plan")
def create_meal_plan(payload: MealPlanIn, db: Session = Depends(get_db),
                     _: User = Depends(get_current_user)):
    mp = MealPlan(**payload.model_dump())
    db.add(mp)
    db.commit()
    db.refresh(mp)
    return {"id": mp.id}


@router.delete("/meal-plan/{mid}")
def delete_meal_plan(mid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    mp = db.get(MealPlan, mid)
    if not mp:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(mp)
    db.commit()
    return {"ok": True}


# ---------- 采购清单 ----------
def _aggregate(recipe_ids, db):
    agg = {}
    for rid in set(recipe_ids):
        r = db.get(Recipe, rid)
        if not r:
            continue
        for ing in r.ingredients:
            base, dim = to_base(ing.quantity, ing.unit)
            key = ing.name.strip().lower()
            if key not in agg:
                agg[key] = {"name": ing.name, "grams": 0.0, "ml": 0.0,
                            "count": 0.0, "count_unit": ing.unit, "dim": dim,
                            "sources": []}
            a = agg[key]
            if dim == "weight":
                a["grams"] += base
            elif dim == "volume":
                a["ml"] += base
            elif dim == "count":
                a["count"] += base
                a["count_unit"] = ing.unit
            a["sources"].append(r.title)
    items = []
    for a in agg.values():
        if a["dim"] == "weight":
            qty, unit, display = a["grams"], "克", pretty(a["grams"], "克")
        elif a["dim"] == "volume":
            qty, unit, display = a["ml"], "毫升", pretty(a["ml"], "毫升")
        elif a["dim"] == "count":
            qty, unit, display = a["count"], a["count_unit"], pretty(a["count"], a["count_unit"])
        else:
            qty, unit, display = 0, "适量", "适量"
        items.append({
            "name": a["name"], "quantity": qty, "unit": unit,
            "display": display, "channel": "", "checked": False,
            "source_recipes": ";".join(a["sources"]),
        })
    # 按名称排序
    items.sort(key=lambda x: x["name"])
    return items


@router.post("/shopping-lists/from-recipes")
def shopping_from_recipes(payload: dict, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    recipe_ids = payload.get("recipe_ids", [])
    items = _aggregate(recipe_ids, db)
    sl = ShoppingList(name=payload.get("name", "采购清单"), user_id=user.id)
    for it in items:
        sl.items.append(ShoppingItem(
            name=it["name"], quantity=it["quantity"], unit=it["unit"],
            channel=it["channel"], source_recipe_id=None,
        ))
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return {"id": sl.id, "items": items}


@router.post("/shopping-lists/from-mealplan")
def shopping_from_mealplan(payload: dict, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    date_from = payload.get("from")
    date_to = payload.get("to")
    q = db.query(MealPlan)
    if date_from:
        q = q.filter(MealPlan.plan_date >= date_from)
    if date_to:
        q = q.filter(MealPlan.plan_date <= date_to)
    recipe_ids = [p.recipe_id for p in q.all() if p.recipe_id]
    items = _aggregate(recipe_ids, db)
    sl = ShoppingList(name=payload.get("name", "周采购清单"), user_id=user.id)
    for it in items:
        sl.items.append(ShoppingItem(
            name=it["name"], quantity=it["quantity"], unit=it["unit"],
            channel=it["channel"],
        ))
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return {"id": sl.id, "items": items}


@router.get("/shopping-lists")
def list_shopping(db: Session = Depends(get_db)):
    out = []
    for sl in db.query(ShoppingList).order_by(ShoppingList.created_at.desc()).all():
        out.append({
            "id": sl.id, "name": sl.name, "created_at": str(sl.created_at),
            "item_count": len(sl.items),
            "checked_count": sum(1 for i in sl.items if i.checked),
        })
    return out


@router.get("/shopping-lists/{lid}")
def get_shopping(lid: int, db: Session = Depends(get_db)):
    sl = db.get(ShoppingList, lid)
    if not sl:
        raise HTTPException(status_code=404, detail="清单不存在")
    return {
        "id": sl.id, "name": sl.name,
        "items": [
            {"id": i.id, "name": i.name, "quantity": i.quantity, "unit": i.unit,
             "display": pretty(i.quantity, i.unit), "channel": i.channel,
             "checked": i.checked, "source_recipe_id": i.source_recipe_id}
            for i in sl.items
        ],
    }


@router.put("/shopping-lists/{lid}/items/{iid}")
def toggle_item(lid: int, iid: int, payload: dict, db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    item = db.get(ShoppingItem, iid)
    if not item or item.list_id != lid:
        raise HTTPException(status_code=404, detail="条目不存在")
    if "checked" in payload:
        item.checked = bool(payload["checked"])
    if "channel" in payload:
        item.channel = payload["channel"]
    db.commit()
    return {"ok": True}


@router.delete("/shopping-lists/{lid}")
def delete_shopping(lid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    sl = db.get(ShoppingList, lid)
    if not sl:
        raise HTTPException(status_code=404, detail="清单不存在")
    db.delete(sl)
    db.commit()
    return {"ok": True}


# ---------- 单位换算 ----------
@router.get("/units/info")
def units_info(qty: float, unit: str):
    return {"pretty": pretty(qty, unit), "dimension": dimension(unit)}


# ---------- 导入 ----------
@router.post("/import/xiachufang")
def import_xcf(payload: dict, db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    url = payload.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="缺少 url")
    try:
        data = import_from_url(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"抓取失败：{e}")
    if not data["title"] and not data["ingredients"] and not data["steps"]:
        raise HTTPException(status_code=422, detail="未能解析出内容，请手动录入或粘贴文本")
    # 封面图尽力抓取，失败不影响导入
    cover_url = data.pop("cover_url", "")
    data["cover"] = ""
    if cover_url:
        try:
            data["cover"] = save_cover_from_url(cover_url, referer="https://www.xiachufang.com/")
        except Exception:  # noqa: BLE001
            data["cover"] = ""
    return data
