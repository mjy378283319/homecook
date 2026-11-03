"""下厨房菜谱导入（尽力解析，导入后请在界面复核）。

网络策略：优先抓取 m.xiachufang.com 移动版（无需 cookie，成功率较高）；
若失败再回退桌面版带 cookie 的方式。解析为尽力而为，结果供用户编辑确认。
"""

import re
from urllib.parse import urljoin

import requests

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

UNIT_TOKENS = [
    "公斤", "千克", "毫升", "升", "克", "两", "斤", "汤匙", "茶匙", "大勺", "小勺", "勺",
    "个", "只", "根", "条", "瓣", "片", "块", "把", "棵", "株", "粒", "枚", "碗", "杯",
    "盘", "份", "张", "尾", "串",
    "适量", "少许", "按口味", "若干",
]


def extract_id(url: str):
    m = re.search(r"recipe/(\d+)", url or "")
    return m.group(1) if m else None


def _fetch(url: str) -> str:
    mid = extract_id(url)
    target = f"https://m.xiachufang.com/recipe/{mid}/" if mid else url
    try:
        r = requests.get(
            target,
            headers={"User-Agent": MOBILE_UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=20,
        )
        r.raise_for_status()
        return r.text
    except Exception:
        pass
    # 回退：桌面版带首页 cookie
    s = requests.Session()
    s.get("https://www.xiachufang.com/", headers={"User-Agent": DESKTOP_UA}, timeout=20)
    r = s.get(
        url,
        headers={"User-Agent": DESKTOP_UA, "Accept-Language": "zh-CN,zh;q=0.9",
                 "Referer": "https://www.xiachufang.com/"},
        timeout=20,
    )
    r.raise_for_status()
    return r.text


def strip_tags(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def parse_ingredient(line: str):
    line = line.strip()
    # 数量 + 单位 + 名称
    for u in UNIT_TOKENS:
        if u in ("适量", "少许", "按口味", "若干"):
            if line.startswith(u):
                return {"name": line[len(u):].strip(), "quantity": 0, "unit": u}
            continue
        m = re.search(r"(\d+\.?\d*)\s*" + re.escape(u) + r"\s*[:：]?\s*(.+)", line)
        if m:
            return {"name": m.group(2).strip(), "quantity": float(m.group(1)), "unit": u}
    # 名称 + 数量（如 "面粉 200克"）
    m = re.match(r"(.+?)\s+(\d+\.?\d*|适量|少许|按口味|若干)\s*(克|两|斤|公斤|个|根|瓣|勺|毫升|升)?", line)
    if m:
        name = m.group(1).strip()
        q = m.group(2)
        if q in ("适量", "少许", "按口味", "若干"):
            return {"name": name, "quantity": 0, "unit": q}
        return {"name": name, "quantity": float(q), "unit": m.group(3) or "克"}
    if 0 < len(line) <= 12:
        return {"name": line, "quantity": 0, "unit": "适量"}
    return None


def parse(html: str) -> dict:
    text = strip_tags(html)
    title = ""
    m = re.search(r"<title>(.*?)</title>", html)
    if m:
        title = m.group(1).split("的做法")[0].split("【")[0].strip()

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    ingredients, steps = [], []
    mode = "head"
    for line in lines:
        if any(k in line for k in ("用料", "原料")):
            mode = "ing"
            continue
        if any(k in line for k in ("做法", "步骤", "制法")):
            mode = "step"
            continue
        if mode == "ing":
            ing = parse_ingredient(line)
            if ing and ing["name"]:
                ingredients.append(ing)
        elif mode == "step":
            # 跳过纯序号
            if re.match(r"^第?\d+[步、.]$", line):
                continue
            steps.append({"text": line})
    return {"title": title, "ingredients": ingredients, "steps": steps}


def extract_cover(html: str, page_url: str = "") -> str:
    """从页面提取成品图（og:image 优先，其次 JSON-LD / 站内图片域名）。"""
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'"image"\s*:\s*"([^"]+?\.(?:jpg|jpeg|png|webp))"',
        r'(https?://i\d*\.xiachufang\.com/[^"\'\s<>]+\.(?:jpg|jpeg|png|webp))',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.I)
        if m:
            url = m.group(1).strip()
            if url.startswith("//"):
                url = "https:" + url
            return urljoin(page_url or "https://www.xiachufang.com/", url)
    return ""


def import_from_url(url: str) -> dict:
    html = _fetch(url)
    data = parse(html)
    data["source_url"] = url
    data["source_name"] = "下厨房"
    data["cover_url"] = extract_cover(html, url)
    return data
