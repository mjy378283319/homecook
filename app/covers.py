"""菜谱封面图：本地存储 + 归一化压缩。

设计要点：
- 图片落在数据卷内的 `covers/`（默认 `<DATA_DIR>/covers`，容器里即 `/data/covers`），
  与 SQLite 同卷，备份/迁移一并带走。
- 有 Pillow 时统一转成最长边 1280 的 JPEG（质量 85），列表与详情共用一个文件；
  没装 Pillow 时按原始格式落盘，保证功能不因缺依赖而中断。
- 对外只暴露 `/covers/<32位hex>.<ext>`，文件名随机生成，避免路径穿越与猜解。
"""

import io
import os
import re
import uuid

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))


def _default_covers_dir() -> str:
    """封面必须与数据库同卷才能被备份带走，因此优先跟随 DB_PATH 所在目录。"""
    if os.environ.get("COVERS_DIR"):
        return os.environ["COVERS_DIR"]
    db_path = os.environ.get("DB_PATH")
    if db_path:
        return os.path.join(os.path.dirname(os.path.abspath(db_path)), "covers")
    return os.path.join(DATA_DIR, "covers")


COVERS_DIR = _default_covers_dir()

MAX_BYTES = 12 * 1024 * 1024  # 单张上限 12MB
MAX_EDGE = 1280  # 归一化后的最长边
URL_PREFIX = "/covers/"
_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|gif)$")

try:  # 可选依赖：没装也能工作
    from PIL import Image, ImageOps

    HAS_PIL = True
except Exception:  # noqa: BLE001
    HAS_PIL = False

_SIGS = [
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
]


def _sniff(raw: bytes):
    for sig, ext in _SIGS:
        if raw.startswith(sig):
            return ext
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


def ensure_dir() -> None:
    os.makedirs(COVERS_DIR, exist_ok=True)


def save_cover(raw: bytes) -> str:
    """保存并归一化图片，返回可访问路径 `/covers/xxx.jpg`。非法内容抛 ValueError。"""
    if not raw:
        raise ValueError("空文件")
    if len(raw) > MAX_BYTES:
        raise ValueError(f"图片超过 {MAX_BYTES // (1024 * 1024)}MB")

    ensure_dir()
    name = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(COVERS_DIR, name)

    if HAS_PIL:
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im = ImageOps.exif_transpose(im)
                im = im.convert("RGB")
                im.thumbnail((MAX_EDGE, MAX_EDGE))
                im.save(path, "JPEG", quality=85, optimize=True, progressive=True)
            return URL_PREFIX + name
        except Exception:  # noqa: BLE001  压缩失败则降级为原样保存
            pass

    ext = _sniff(raw)
    if not ext:
        raise ValueError("仅支持 JPG / PNG / WebP / GIF 图片")
    name = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(COVERS_DIR, name), "wb") as f:
        f.write(raw)
    return URL_PREFIX + name


def save_cover_from_url(url: str, referer: str = "") -> str:
    """下载远程图片并保存（用于下厨房导入）。失败抛异常由调用方降级。"""
    if not url or not url.lower().startswith(("http://", "https://")):
        raise ValueError("非法图片地址")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    if len(resp.content) > MAX_BYTES:
        raise ValueError("远程图片过大")
    return save_cover(resp.content)


def delete_cover(cover: str) -> None:
    """删除本应用保存的封面文件；外部 URL 或非法名忽略。"""
    if not cover or not cover.startswith(URL_PREFIX):
        return
    name = cover[len(URL_PREFIX):]
    if not _NAME_RE.match(name):
        return
    try:
        os.remove(os.path.join(COVERS_DIR, name))
    except FileNotFoundError:
        pass
