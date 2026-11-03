import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

SECRET = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")


def hash_password(pw: str, salt: str = None) -> str:
    salt = salt or os.urandom(8).hex()
    h = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    return f"{salt}:{h}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
    except ValueError:
        return False
    return hmac.compare_digest(
        hashlib.sha256((salt + pw).encode("utf-8")).hexdigest(), h
    )


def _sign(value: str) -> str:
    sig = hmac.new(SECRET.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{value}.{sig}"


def _unsign(signed: str):
    if not signed or "." not in signed:
        return None
    value, sig = signed.rsplit(".", 1)
    expected = hmac.new(SECRET.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if hmac.compare_digest(expected, sig):
        return value
    return None


def create_session(user_id: int) -> str:
    return _sign(str(user_id))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get("session")
    if not raw:
        raise HTTPException(status_code=401, detail="未登录")
    val = _unsign(raw)
    if not val:
        raise HTTPException(status_code=401, detail="会话无效，请重新登录")
    user = db.get(User, int(val))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
