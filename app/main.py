import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.db import SessionLocal, init_db
from app.routers import router
from app.seed import ensure_default_user, seed_initial

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="家常菜单 HomeCook", version="0.1.0")
app.include_router(router, prefix="/api")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def _startup():
    init_db()
    db = SessionLocal()
    try:
        seed_initial(db)
        ensure_default_user(db)
    finally:
        db.close()


@app.get("/healthz")
def healthz():
    """容器健康检查：不查鉴权、不碰业务表，只确认进程与数据库句柄可用。"""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)})
    return {"status": "ok", "version": app.version}


@app.get("/favicon.ico")
def favicon():
    return JSONResponse(status_code=204, content=None)


@app.get("/")
@app.get("/{path:path}")
def index(path: str = ""):
    # 非 API、非静态的路由一律回退到单页应用
    if path.startswith("api") or path.startswith("static"):
        return JSONResponse(status_code=404, content={"detail": "not found"})
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
