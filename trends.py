"""
trends.py
長期體能趨勢圖 — 直接用 OpenCV 畫在遊戲風格的深色背景上（不再用 Matplotlib 出 PNG），
與遊戲整體視覺一致、好看且零額外依賴。

三個折線面板（隨場次／時間）：
  1. 每場「深蹲＋伏地挺身」總次數
  2. 每場消耗卡路里
  3. BMI 變化（疊上未來一個月的線性外推預測，虛線）
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np

import storage
from text_utils import put_text, put_text_centered


# ── 配色 ──
_BG_TOP = (40, 28, 18)
_BG_BOTTOM = (18, 14, 26)
_PANEL = (34, 30, 48)
_PANEL_BORDER = (95, 110, 170)
_AXIS = (90, 95, 120)
_GRID = (52, 56, 76)


def _gradient_bg(w: int, h: int) -> np.ndarray:
    """深色直向漸層背景。"""
    top = np.array(_BG_TOP, dtype=np.float32)
    bot = np.array(_BG_BOTTOM, dtype=np.float32)
    col = (top[None, :] * (1 - np.linspace(0, 1, h))[:, None]
           + bot[None, :] * np.linspace(0, 1, h)[:, None])
    return np.repeat(col[:, None, :], w, axis=1).astype(np.uint8)


def _dashed_line(frame, p1, p2, color, thickness=2, dash=10):
    """畫虛線（給預測用）。"""
    x1, y1 = p1
    x2, y2 = p2
    dist = int(np.hypot(x2 - x1, y2 - y1))
    if dist == 0:
        return
    for i in range(0, dist, dash * 2):
        a = i / dist
        b = min((i + dash) / dist, 1.0)
        xa, ya = int(x1 + (x2 - x1) * a), int(y1 + (y2 - y1) * a)
        xb, yb = int(x1 + (x2 - x1) * b), int(y1 + (y2 - y1) * b)
        cv2.line(frame, (xa, ya), (xb, yb), color, thickness, cv2.LINE_AA)


def _draw_panel(frame, rect: Tuple[int, int, int, int], title: str,
                values: List[float], color, unit: str = "",
                forecast: Optional[List[float]] = None):
    """在 rect=(x0,y0,x1,y1) 內畫一個折線面板。"""
    x0, y0, x1, y1 = rect
    cv2.rectangle(frame, (x0, y0), (x1, y1), _PANEL, -1)
    cv2.rectangle(frame, (x0, y0), (x1, y1), _PANEL_BORDER, 1)
    put_text(frame, title, (x0 + 14, y0 + 8), size=22, color=(235, 235, 245), bold=True)

    # 繪圖區（留邊給標籤）
    pad_l, pad_r, pad_t, pad_b = 64, 20, 44, 26
    gx0, gy0 = x0 + pad_l, y0 + pad_t
    gx1, gy1 = x1 - pad_r, y1 - pad_b

    if not values:
        put_text_centered(frame, "尚無資料", (x0 + x1) // 2, (y0 + y1) // 2 - 12,
                          size=22, color=(150, 150, 170))
        return

    all_vals = list(values) + (forecast or [])
    vmin, vmax = min(all_vals), max(all_vals)
    if vmax - vmin < 1e-6:
        vmax = vmin + 1.0
    pad_v = (vmax - vmin) * 0.15
    vmin -= pad_v
    vmax += pad_v

    def vy(v):
        return int(gy1 - (v - vmin) / (vmax - vmin) * (gy1 - gy0))

    # 水平格線 + y 軸標籤（3 條）
    for i in range(3):
        v = vmin + (vmax - vmin) * i / 2
        yy = vy(v)
        cv2.line(frame, (gx0, yy), (gx1, yy), _GRID, 1, cv2.LINE_AA)
        put_text(frame, f"{v:.0f}", (x0 + 12, yy - 10), size=16, color=(160, 165, 185))

    # 軸線
    cv2.line(frame, (gx0, gy0), (gx0, gy1), _AXIS, 1, cv2.LINE_AA)
    cv2.line(frame, (gx0, gy1), (gx1, gy1), _AXIS, 1, cv2.LINE_AA)

    n_total = len(values) + (len(forecast) if forecast else 0)
    if n_total == 1 and not forecast:
        # 單點：畫一個點
        cx = (gx0 + gx1) // 2
        cv2.circle(frame, (cx, vy(values[0])), 5, color, -1, cv2.LINE_AA)
        return

    span = max(n_total - 1, 1)
    xs = [int(gx0 + (gx1 - gx0) * i / span) for i in range(n_total)]

    # 實績折線
    pts = [(xs[i], vy(values[i])) for i in range(len(values))]
    for i in range(1, len(pts)):
        cv2.line(frame, pts[i - 1], pts[i], color, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(frame, p, 4, color, -1, cv2.LINE_AA)

    # 預測虛線（接在實績之後）
    if forecast:
        fcolor = (90, 90, 235)
        prev = pts[-1] if pts else None
        for j, fv in enumerate(forecast):
            idx = len(values) + j
            fp = (xs[idx], vy(fv))
            if prev is not None:
                _dashed_line(frame, prev, fp, fcolor, 2, dash=9)
            prev = fp
        # 「現在」分隔線
        if pts:
            cv2.line(frame, (pts[-1][0], gy0), (pts[-1][0], gy1), (70, 80, 110), 1, cv2.LINE_AA)
        put_text(frame, "預測", (gx1 - 60, gy0 - 2), size=16, color=fcolor, bold=True)

    if unit:
        put_text(frame, unit, (gx1 - 44, gy1 + 4), size=15, color=(150, 155, 175))


def render_trends(user_id: int, size: Tuple[int, int]) -> Optional[np.ndarray]:
    """產生某使用者的趨勢圖（OpenCV BGR 影像）；完全無資料時回傳 None。"""
    w, h = size
    sessions = storage.get_sessions(user_id)
    bmi_hist = storage.get_bmi_history(user_id)
    if not sessions and not bmi_hist:
        return None

    frame = _gradient_bg(w, h)
    put_text_centered(frame, "體能長期趨勢", w // 2, 24, size=40,
                      color=(255, 220, 100), bold=True)

    reps_total = [int(s["reps"].get("squat", 0)) + int(s["reps"].get("pushup", 0))
                  for s in sessions]
    cals = [float(s["calories"]) for s in sessions]
    bmis = [float(b["bmi"]) for b in bmi_hist]

    # BMI 預測（延後匯入避免循環相依）
    forecast = None
    try:
        import digital_twin
        fc = digital_twin.forecast_bmi(user_id)
        if fc:
            forecast = fc["y"]
    except Exception:
        forecast = None

    margin = 50
    top = 84
    gap = 16
    panel_h = (h - top - 40 - gap * 2) // 3
    x0, x1 = margin, w - margin
    panels = [
        ("每場 深蹲＋伏地挺身 總次數", reps_total, (130, 220, 110), ""),
        ("每場消耗卡路里", cals, (90, 170, 250), "kcal"),
        ("BMI 變化（虛線為未來一個月預測）", bmis, (120, 230, 120), "BMI"),
    ]
    for i, (title, vals, color, unit) in enumerate(panels):
        py0 = top + i * (panel_h + gap)
        fc = forecast if i == 2 else None
        _draw_panel(frame, (x0, py0, x1, py0 + panel_h), title, vals, color,
                    unit=unit, forecast=fc)

    put_text_centered(frame, "按任意鍵返回主頁", w // 2, h - 24,
                      size=22, color=(190, 210, 240))
    return frame
