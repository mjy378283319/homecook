"""生成 HomeCook 应用图标（纯标准库，无 Pillow 依赖）。

用法：python assets/make_icon.py
输出：static/icon.png (512x512)、static/favicon.png (256x256)
"""

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SS = 1024  # 超采样画布


def lerp(a, b, t):
    return a + (b - a) * t


def inside_rrect(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    if x < x0 + r and y < y0 + r:
        return (x - (x0 + r)) ** 2 + (y - (y0 + r)) ** 2 <= r * r
    if x > x1 - r and y < y0 + r:
        return (x - (x1 - r)) ** 2 + (y - (y0 + r)) ** 2 <= r * r
    if x < x0 + r and y > y1 - r:
        return (x - (x0 + r)) ** 2 + (y - (y1 - r)) ** 2 <= r * r
    if x > x1 - r and y > y1 - r:
        return (x - (x1 - r)) ** 2 + (y - (y1 - r)) ** 2 <= r * r
    return True


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / l2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def render():
    W = SS
    rows = []
    cx, cy = 0.5 * W, 0.58 * W
    rx, ry = 0.30 * W, 0.20 * W
    rim_top, rim_bot = cy - 0.04 * W, cy + 0.04 * W
    rim_l, rim_r = cx - rx - 0.02 * W, cx + rx + 0.02 * W
    rim_rad = (rim_bot - rim_top) / 2
    chop = [
        (0.58 * W, 0.16 * W, 0.44 * W, 0.50 * W),
        (0.70 * W, 0.15 * W, 0.56 * W, 0.49 * W),
    ]
    thick = 0.018 * W

    for y in range(W):
        row = []
        t = y / (W - 1)
        br, bg, bb = int(lerp(255, 216, t)), int(lerp(145, 70, t)), int(lerp(55, 40, t))
        for x in range(W):
            px, py = x + 0.5, y + 0.5
            # 圆角矩形外透明
            if not inside_rrect(px, py, 0, 0, W - 1, W - 1, 0.22 * W):
                row.append((0, 0, 0, 0))
                continue
            color = (br, bg, bb, 255)
            white = (255, 255, 255, 255)
            # 筷子（先画，位于碗后方）
            for x1, y1, x2, y2 in chop:
                if seg_dist(px, py, x1, y1, x2, y2) <= thick:
                    color = white
                    break
            # 碗身：下半椭圆
            if py >= cy and ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0:
                color = white
            # 碗沿
            if inside_rrect(px, py, rim_l, rim_top, rim_r, rim_bot, rim_rad):
                color = white
            row.append(color)
        rows.append(row)
    return rows


def downsample(rows, factor):
    h = len(rows)
    w = len(rows[0])
    nh, nw = h // factor, w // factor
    out = []
    for by in range(nh):
        row = []
        for bx in range(nw):
            sa = sr = sg = sb = 0
            for dy in range(factor):
                for dx in range(factor):
                    r, g, b, a = rows[by * factor + dy][bx * factor + dx]
                    sa += a
                    sr += r * a
                    sg += g * a
                    sb += b * a
            if sa == 0:
                row.append((0, 0, 0, 0))
            else:
                row.append((sr // sa, sg // sa, sb // sa, sa // (factor * factor)))
        out.append(row)
    return out


def save_png(path, rows):
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in rows)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    base = render()
    icon = downsample(base, 2)       # 512
    fav = downsample(icon, 2)        # 256
    save_png(ROOT / "static" / "icon.png", icon)
    save_png(ROOT / "static" / "favicon.png", fav)
    print("wrote static/icon.png (512) and static/favicon.png (256)")
