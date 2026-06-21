"""
digital_twin.py
數位分身（數據孿生 + 成長角色）— 方案 b + c 結合，**與使用者綁定**。

只吃資料層數據，不碰 3D 建模。

c. 成長角色：屬性由某位使用者累積的 sessions 推導
   - 力量(strength)：隨累計伏地挺身次數
   - 耐力(stamina) ：隨累計深蹲次數與遊戲場次
   - 體態(physique)：依目前 BMI 與健康值(22)的接近程度
   - 等級(level)   ：隨累計總卡路里
b. 數據孿生與預測：用該使用者 bmi_history 線性外推，預測一個月後 BMI。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import cv2
import numpy as np

import storage
from text_utils import put_text, put_text_centered

# ── 成長係數（集中為常數，方便調校） ──
STRENGTH_PER_PUSHUP = 2.0
STAMINA_PER_SQUAT = 1.5
STAMINA_PER_GAME = 5.0
CALORIES_PER_LEVEL = 30.0
HEALTHY_BMI = 22.0
FORECAST_DAYS = 30


def _parse(d: str) -> datetime:
    return datetime.fromisoformat(d)


# ══════════════════════════════════════════════════════════════════════════════
# 成長角色屬性（依 user_id）
# ══════════════════════════════════════════════════════════════════════════════

def compute_stats(user_id: int) -> Dict:
    """從某使用者的累積 sessions / bmi 推導分身屬性。"""
    sessions = storage.get_sessions(user_id)
    total_squat = sum(int(s["reps"].get("squat", 0)) for s in sessions)
    total_pushup = sum(int(s["reps"].get("pushup", 0)) for s in sessions)
    total_cal = sum(float(s["calories"]) for s in sessions)
    games = len(sessions)

    bmi = storage.latest_bmi(user_id)
    physique = max(0.0, 100.0 - abs(bmi - HEALTHY_BMI) * 8.0) if bmi else 50.0

    return {
        "games": games,
        "total_squat": total_squat,
        "total_pushup": total_pushup,
        "total_cal": total_cal,
        "bmi": bmi,
        "strength": min(100.0, total_pushup * STRENGTH_PER_PUSHUP),
        "stamina": min(100.0, total_squat * STAMINA_PER_SQUAT + games * STAMINA_PER_GAME),
        "physique": min(100.0, physique),
        "level": 1 + int(total_cal // CALORIES_PER_LEVEL),
    }


def apply_session_growth(user_id: int) -> Dict:
    """
    在某使用者新增一場 session 之後呼叫：
    比較舊 twin_state 與重算後的新屬性，更新 twin_state，回傳成長明細。
    """
    old = storage.get_twin_state(user_id)
    new = compute_stats(user_id)
    storage.save_twin_state(user_id, new["strength"], new["stamina"],
                            new["physique"], new["level"])
    return {
        "new": new,
        "delta": {
            "strength": new["strength"] - old.get("strength", 0),
            "stamina": new["stamina"] - old.get("stamina", 0),
            "physique": new["physique"] - old.get("physique", 0),
            "level": new["level"] - old.get("level", 1),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 數據孿生：線性外推預測
# ══════════════════════════════════════════════════════════════════════════════

def _linfit_forecast(dates: List[datetime], values: List[float],
                     days_ahead: int = FORECAST_DAYS, n_points: int = 12) -> Optional[Dict]:
    if len(dates) < 2:
        return None
    t0 = dates[0]
    xs = np.array([(d - t0).total_seconds() / 86400.0 for d in dates])
    ys = np.array(values, dtype=float)
    if np.ptp(xs) < 1e-9:
        return None
    slope, intercept = np.polyfit(xs, ys, 1)
    last = xs[-1]
    fx = np.linspace(last, last + days_ahead, n_points)
    fy = slope * fx + intercept
    return {
        "x": [t0 + timedelta(days=float(x)) for x in fx],
        "y": fy.tolist(),
        "slope": float(slope),
        "next_value": float(slope * (last + days_ahead) + intercept),
    }


def forecast_bmi(user_id: int) -> Optional[Dict]:
    hist = storage.get_bmi_history(user_id)
    if len(hist) < 2:
        return None
    return _linfit_forecast([_parse(b["date"]) for b in hist],
                            [float(b["bmi"]) for b in hist])


def forecast_all(user_id: int) -> Dict[str, Dict]:
    out = {}
    bmi = forecast_bmi(user_id)
    if bmi:
        out["bmi"] = bmi
    return out


# ══════════════════════════════════════════════════════════════════════════════
# OpenCV 面板繪製（TWIN Scene 用）
# ══════════════════════════════════════════════════════════════════════════════

def _draw_bar(frame, x, y, w, h, ratio, color):
    ratio = max(0.0, min(1.0, ratio / 100.0))
    cv2.rectangle(frame, (x, y), (x + w, y + h), (40, 46, 60), -1)
    cv2.rectangle(frame, (x, y), (x + int(w * ratio), y + h), color, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (120, 130, 160), 1)


def draw_avatar(frame, cx, cy, level, physique):
    """畫一個會隨等級長大的簡單像素小人。"""
    scale = 1.0 + min(level - 1, 12) * 0.12
    body_h = int(70 * scale)
    head_r = int(18 * scale)
    g = int(120 + physique)
    color = (90, min(255, g), 160)

    head_c = (cx, cy - body_h // 2 - head_r)
    cv2.circle(frame, head_c, head_r, color, -1)
    cv2.circle(frame, head_c, head_r, (255, 255, 255), 2)
    cv2.rectangle(frame, (cx - int(16 * scale), cy - body_h // 2),
                  (cx + int(16 * scale), cy + body_h // 2), color, -1)
    cv2.line(frame, (cx - int(16 * scale), cy - body_h // 4),
             (cx - int(40 * scale), cy - body_h // 2), color, int(6 * scale))
    cv2.line(frame, (cx + int(16 * scale), cy - body_h // 4),
             (cx + int(40 * scale), cy - body_h // 2), color, int(6 * scale))
    cv2.line(frame, (cx - int(8 * scale), cy + body_h // 2),
             (cx - int(18 * scale), cy + body_h // 2 + int(40 * scale)), color, int(7 * scale))
    cv2.line(frame, (cx + int(8 * scale), cy + body_h // 2),
             (cx + int(18 * scale), cy + body_h // 2 + int(40 * scale)), color, int(7 * scale))


def render_panel(user, frame_size) -> np.ndarray:
    """產生某使用者的數位分身面板影像（BGR）。"""
    w, h = frame_size
    frame = np.full((h, w, 3), (16, 20, 32), dtype=np.uint8)

    stats = compute_stats(user.id)
    bmi_fc = forecast_bmi(user.id)

    put_text_centered(frame, f"{user.name} 的數位分身", w // 2, 36,
                      size=44, color=(255, 220, 100), bold=True)
    put_text_centered(frame, "由真實訓練數據驅動的成長角色", w // 2, 88,
                      size=22, color=(200, 215, 240))

    draw_avatar(frame, w // 4, h // 2, stats["level"], stats["physique"])
    put_text_centered(frame, f"LV. {stats['level']}", w // 4, h // 2 + 130,
                      size=40, color=(120, 230, 255), bold=True)
    put_text_centered(frame, f"累計 {stats['games']} 場訓練", w // 4, h // 2 + 178,
                      size=22, color=(200, 210, 230))

    bx = w // 2 + 40
    bw = w // 2 - 120
    by = 170
    gap = 78
    bars = [
        ("力量", stats["strength"], (90, 140, 255)),
        ("耐力", stats["stamina"], (90, 220, 160)),
        ("體態", stats["physique"], (120, 200, 255)),
    ]
    for i, (label, val, color) in enumerate(bars):
        y = by + i * gap
        put_text(frame, label, (bx, y - 30), size=26, color=(235, 235, 245), bold=True)
        put_text(frame, f"{val:.0f}/100", (bx + bw - 90, y - 30), size=22, color=(190, 200, 220))
        _draw_bar(frame, bx, y, bw, 22, val, color)

    detail_y = by + 3 * gap + 6
    put_text(frame, f"累計深蹲 {stats['total_squat']}　累計伏地挺身 {stats['total_pushup']}",
             (bx, detail_y), size=22, color=(210, 220, 240))
    put_text(frame, f"累計消耗 {stats['total_cal']:.0f} kcal",
             (bx, detail_y + 34), size=22, color=(255, 200, 130))

    pred_y = detail_y + 84
    if bmi_fc and stats["bmi"]:
        trend = "下降" if bmi_fc["slope"] < 0 else ("上升" if bmi_fc["slope"] > 0 else "持平")
        put_text(frame, "預測（照目前趨勢）", (bx, pred_y), size=24,
                 color=(255, 230, 120), bold=True)
        put_text(frame, f"目前 BMI {stats['bmi']:.1f} → 一個月後約 {bmi_fc['next_value']:.1f}（{trend}）",
                 (bx, pred_y + 34), size=22, color=(180, 245, 200))
    else:
        put_text(frame, "預測：需至少兩筆不同日期的 BMI 紀錄",
                 (bx, pred_y), size=22, color=(190, 190, 210))

    put_text_centered(frame, "按 T 查看含預測的趨勢圖  |  按其他鍵返回",
                      w // 2, h - 36, size=22, color=(190, 210, 240))
    return frame
