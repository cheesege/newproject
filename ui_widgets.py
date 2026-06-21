"""
ui_widgets.py
共用 UI 繪製元件（從舊 main.py 抽出，供各 Scene 重用）。

純繪製函式，不處理輸入與狀態切換。中文一律走 text_utils。
"""

from typing import Optional, Tuple

import cv2
import numpy as np

from exercise_counter import ExerciseCounter, ExerciseType
from game_objects import GameState, MonsterType
from text_utils import put_text, put_text_centered, text_size

# 怪物圖鑑資料：類型 → (顯示名, 代表色 BGR, 說明)
_MONSTER_INFO = {
    MonsterType.ZOMBIE: ("殭屍", (90, 200, 90), "標準怪物，耐打且不會飛。"),
    MonsterType.SKELETON: ("骷髏", (210, 210, 220), "中速怪物，血量適中。"),
    MonsterType.BAT: ("蝙蝠", (200, 110, 230), "飛行怪物，移動較快。"),
}


def draw_button(frame: np.ndarray, x: int, y: int, w: int, h: int, text: str,
                fill: Tuple[int, int, int],
                border: Tuple[int, int, int] = (255, 255, 255),
                text_color: Tuple[int, int, int] = (255, 255, 255)):
    """繪製簡單按鈕樣式。"""
    cv2.rectangle(frame, (x, y), (x + w, y + h), fill, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), border, 2)
    put_text_centered(frame, text, x + w // 2, y + h // 2 - 6,
                      size=20, color=text_color, bold=True)


# 各動作專屬配色（BGR）
EX_COLORS = {
    "squat": (80, 255, 130),
    "pushup": (80, 180, 255),
    "raise_hand": (80, 210, 255),
}


def draw_exercise_panel(frame: np.ndarray, counter: ExerciseCounter,
                        calories: float = None):
    """
    在畫面下方繪製動作計數面板。

    計數器**依本場啟用的動作動態產生**（不再寫死深蹲／伏地挺身），
    並自動置中排版，避免文字超出畫面。
    """
    h, w = frame.shape[:2]
    ph = 96

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - ph), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.60, frame, 0.40, 0, frame)

    # ── 動態計數列（本場啟用動作 + 卡路里），整體置中 ──
    seg_size = 30
    segments = [(f"{ex.name} {ex.count}", EX_COLORS.get(ex.key, (230, 230, 230)))
                for ex in counter.exercises]
    if calories is not None:
        segments.append((f"卡路里 {calories:.1f}", (255, 200, 130)))

    widths = [text_size(t, seg_size, bold=True)[0] for t, _ in segments]
    gap = 36
    total = sum(widths) + gap * (len(segments) - 1)
    x = max(12, w // 2 - total // 2)
    y = h - ph + 12
    for (t, c), seg_w in zip(segments, widths):
        put_text(frame, t, (x, y), size=seg_size, color=c, bold=True)
        x += seg_w + gap

    # ── 目前判定的動作（取代寫死的模式字串）──
    disp = counter.display_exercise
    put_text_centered(frame, f"目前動作：{disp.name}", w // 2, h - 48,
                      size=22, color=(200, 220, 245))

    # ── 姿勢回饋 ──
    if counter.form_feedback:
        put_text_centered(frame, counter.form_feedback, w // 2, h - 24,
                          size=20, color=(255, 220, 50))

    # ── 角度量表（右下角，不擋中央）──
    angle = counter.current_angle()
    if angle is not None:
        draw_angle_gauge(frame, angle, counter.current_exercise,
                         center=(w - 56, h - ph + 40))


def draw_angle_gauge(frame: np.ndarray, angle: float, ex_type: ExerciseType,
                     center: Tuple[int, int]):
    """以半圓弧顯示目前關節角度。"""
    cx, cy = center
    r = 22
    cv2.ellipse(frame, (cx, cy), (r, r), 0, 0, 180, (50, 50, 50), 3)

    norm = min(max((angle - 70) / 110.0, 0), 1)
    arc = int(180 * norm)

    if ex_type == ExerciseType.SQUAT:
        good = angle < 100
        fill_c = (80, 255, 130) if good else (50, 150, 80)
    else:
        good = angle < 90
        fill_c = (80, 180, 255) if good else (50, 100, 150)

    if arc > 0:
        cv2.ellipse(frame, (cx, cy), (r, r), 0, 0, arc, fill_c, 3)

    cv2.putText(frame, f"{angle:.0f}",
                (cx - 17, cy - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1)


def draw_player_marker(frame: np.ndarray, pos: Optional[Tuple[int, int]],
                       laser_ready: bool):
    """在玩家身體中心繪製瞄準標記。"""
    if pos is None:
        return
    px, py = pos
    color = (0, 255, 255) if laser_ready else (100, 100, 100)
    cv2.drawMarker(frame, (px, py), color, cv2.MARKER_CROSS, 22, 2, cv2.LINE_AA)
    cv2.circle(frame, (px, py), 16, color, 1, cv2.LINE_AA)


def draw_no_pose_warning(frame: np.ndarray):
    """若未偵測到人物，顯示警告。"""
    h, w = frame.shape[:2]
    msg = "!! 未偵測到人物 — 請站入攝影機視野"
    put_text_centered(frame, msg, w // 2, 72, size=24, color=(0, 80, 255), shadow=True)


def draw_monster_page(frame: np.ndarray, game: GameState):
    """
    繪製怪物圖鑑：記錄**本場所有出現過**的怪物（含已離開畫面者）與其擊敗次數，
    而非只列當下畫面上的怪物。
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (12, 18, 30), -1)
    cv2.addWeighted(overlay, 0.92, frame, 0.08, 0, frame)

    put_text_centered(frame, "怪物圖鑑", w // 2, 36, size=46, color=(255, 220, 100), bold=True)
    total_spawn = sum(game.spawn_counts.values())
    total_kill = sum(game.kill_counts.values())
    put_text_centered(
        frame,
        f"本場 LV.{game.level}  ｜  總出現 {total_spawn}  ｜  總擊敗 {total_kill}  ｜  場上 {len(game.monsters)}",
        w // 2, 84, size=24, color=(200, 220, 255))

    card_w, card_h = 360, 150
    gap = 40
    total_w = card_w * 3 + gap * 2
    x_start = (w - total_w) // 2
    y = 140
    for i, (mtype, (name, color, desc)) in enumerate(_MONSTER_INFO.items()):
        x = x_start + i * (card_w + gap)
        cv2.rectangle(frame, (x, y), (x + card_w, y + card_h), (30, 38, 52), -1)
        cv2.rectangle(frame, (x, y), (x + card_w, y + card_h), color, 2)

        appeared = game.spawn_counts.get(mtype, 0)
        defeated = game.kill_counts.get(mtype, 0)
        on_screen = sum(1 for m in game.monsters if m.alive and m.mtype == mtype)

        put_text(frame, name, (x + 18, y + 14), size=30, color=color, bold=True)
        put_text(frame, desc, (x + 18, y + 56), size=18, color=(210, 210, 220))
        put_text(frame, f"出現 {appeared}", (x + 18, y + 90), size=22, color=(245, 235, 180))
        put_text(frame, f"擊敗 {defeated}", (x + 18, y + 118), size=22, color=(150, 255, 170))
        put_text(frame, f"場上 {on_screen}", (x + 200, y + 90), size=22, color=(170, 210, 255))
        rate = (defeated / appeared * 100) if appeared else 0
        put_text(frame, f"擊敗率 {rate:.0f}%", (x + 200, y + 118), size=22, color=(255, 210, 150))

    if total_spawn == 0:
        put_text_centered(frame, "本場還沒有怪物出現，回到戰鬥開始累積圖鑑！",
                          w // 2, y + card_h + 60, size=26, color=(220, 220, 220))

    put_text_centered(frame, "按 M 返回戰鬥", w // 2, h - 36, size=22, color=(190, 200, 230))
