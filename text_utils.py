"""
text_utils.py
使用 Pillow 在 OpenCV BGR frame 上繪製 CJK（中文）文字。

cv2.putText 只支援 ASCII；這個模組是它的替代品。

主要 API
--------
put_text(frame, text, xy, size, color, bold)
    在 (x, y) 左上角繪製文字。

put_text_centered(frame, text, cx, y, size, color, bold)
    以 cx 為水平中心繪製文字。

text_size(text, size, bold) -> (w, h)
    取得文字的像素尺寸（用來自行排版）。
"""

import os
from typing import Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── 字型搜尋路徑（依優先順序） ────────────────────────────────────────────────

_FONT_CANDIDATES = [
    "/usr/share/fonts/wqy-microhei-fonts/wqy-microhei.ttc",
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",            # macOS
    "C:/Windows/Fonts/msjh.ttc",                     # Windows 微軟正黑
    "C:/Windows/Fonts/msyh.ttc",                     # Windows 微軟雅黑
]

_DEFAULT_FONT_PATH: str | None = None
for _p in _FONT_CANDIDATES:
    if os.path.exists(_p):
        _DEFAULT_FONT_PATH = _p
        break

if _DEFAULT_FONT_PATH is None:
    print(
        "⚠ 找不到 CJK 字型，將改用 PIL 預設字型。"
        " 中文顯示可能不完整。"
    )

# ── 字型快取（同路徑＋大小只載入一次） ───────────────────────────────────────

_font_cache: dict = {}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _font_cache:
        if _DEFAULT_FONT_PATH is not None:
            path = _DEFAULT_FONT_PATH
            # 嘗試取 bold index（.ttc 多字型檔）
            try:
                _font_cache[key] = ImageFont.truetype(path, size, index=1 if bold else 0)
            except Exception:
                _font_cache[key] = ImageFont.truetype(path, size)
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


# ══════════════════════════════════════════════════════════════════════════════
# 公開函式
# ══════════════════════════════════════════════════════════════════════════════

def text_size(text: str, size: int = 28, bold: bool = False) -> Tuple[int, int]:
    """回傳文字的（寬, 高）像素尺寸。"""
    font = _get_font(size, bold)
    bbox = font.getbbox(text)          # (left, top, right, bottom)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])


def put_text(
    frame: np.ndarray,
    text: str,
    xy: Tuple[int, int],
    size: int = 28,
    color: Tuple[int, int, int] = (255, 255, 255),
    bold: bool = False,
    shadow: bool = False,
) -> np.ndarray:
    """
    在 frame 上的 (x, y) 左上角繪製文字（支援中文 / emoji）。

    Parameters
    ----------
    frame  : BGR numpy array（直接修改並回傳）
    text   : 要顯示的文字
    xy     : (x, y) 左上角座標
    size   : 字體大小（像素）
    color  : BGR 顏色
    bold   : 是否加粗
    shadow : True → 繪製黑色陰影（提升可讀性）
    """
    if not text:
        return frame

    font    = _get_font(size, bold)
    rgb_col = (color[2], color[1], color[0])   # BGR → RGB

    # 取得文字尺寸，建立略大的透明貼圖
    bbox    = font.getbbox(text)
    tw, th  = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad     = 4
    tile_w  = tw + pad * 2
    tile_h  = th + pad * 2

    tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)

    tx = pad - bbox[0]
    ty = pad - bbox[1]

    if shadow:
        draw.text((tx + 2, ty + 2), text, font=font, fill=(0, 0, 0, 200))

    draw.text((tx, ty), text, font=font, fill=(*rgb_col, 255))

    # 貼到 frame
    x, y = int(xy[0]) - pad, int(xy[1]) - pad

    # 自適應：若文字會超出畫面邊界，平移回框內（避免被切掉）
    fh, fw = frame.shape[:2]
    if tile_w <= fw:
        x = max(0, min(x, fw - tile_w))
    if tile_h <= fh:
        y = max(0, min(y, fh - tile_h))

    _paste_rgba(frame, tile, x, y)

    return frame


def put_text_centered(
    frame: np.ndarray,
    text: str,
    cx: int,
    y: int,
    size: int = 28,
    color: Tuple[int, int, int] = (255, 255, 255),
    bold: bool = False,
    shadow: bool = True,
) -> np.ndarray:
    """以 cx 為水平中心，在 y 繪製文字。"""
    tw, _ = text_size(text, size, bold)
    return put_text(frame, text, (cx - tw // 2, y), size, color, bold, shadow)


# ── 內部：Alpha 合成 ──────────────────────────────────────────────────────────

def _paste_rgba(frame: np.ndarray, tile: Image.Image, x: int, y: int):
    """將 RGBA PIL tile 以 alpha 混合方式貼到 BGR numpy frame。"""
    h_f, w_f = frame.shape[:2]
    t_arr    = np.array(tile, dtype=np.uint8)   # (H, W, 4)
    th, tw   = t_arr.shape[:2]

    # 計算有效的重疊區域
    x0  = max(x, 0);        y0  = max(y, 0)
    x1  = min(x + tw, w_f); y1  = min(y + th, h_f)
    if x0 >= x1 or y0 >= y1:
        return

    tx0 = x0 - x;  ty0 = y0 - y
    tx1 = tx0 + (x1 - x0);  ty1 = ty0 + (y1 - y0)

    tile_crop  = t_arr[ty0:ty1, tx0:tx1]
    frame_crop = frame[y0:y1, x0:x1]

    alpha = tile_crop[:, :, 3:4].astype(np.float32) / 255.0
    rgb   = tile_crop[:, :, :3][:, :, ::-1]    # RGB → BGR

    frame[y0:y1, x0:x1] = (
        frame_crop * (1 - alpha) + rgb * alpha
    ).astype(np.uint8)
