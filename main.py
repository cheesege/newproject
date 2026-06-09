#!/usr/bin/env python3
"""
體感硬核健身房 — Fitness Battle Game
=====================================
用深蹲 / 伏地挺身發射雷射砲，擊退螢幕上不斷逼近的怪物！

使用方式
--------
  pip install opencv-python mediapipe numpy
  python main.py

遊戲操作
--------
  深蹲（完整一下）   → 雷射瞄準最近怪物
  伏地挺身（完整一下）→ 雷射齊射最近 3 隻怪物
  R               → 重新開始
  P               → 暫停 / 繼續
  S               → 截圖
  F               → 手動測試發射（除錯用）
  Q / ESC         → 離開

姿態偵測
--------
  深蹲：膝蓋角度 (髖-膝-踝) 從 >160° 降至 <110° 再回到 >160°
  伏地挺身：偵測到水平體位後，肘部角度 (肩-肘-腕) 從 >155° 降至 <90° 再回升
"""

import sys
import time
from datetime import datetime
from typing import Optional, Tuple

import cv2
import numpy as np

from exercise_counter import ExerciseCounter, ExerciseType
from game_objects import GameState, MonsterMode
from pose_detector import PoseDetector
from text_utils import put_text, put_text_centered, text_size


# ══════════════════════════════════════════════════════════════════════════════
# UI 輔助函式
# ══════════════════════════════════════════════════════════════════════════════

def make_start_screen(w: int, h: int, monster_mode: MonsterMode) -> np.ndarray:
    """建立開始畫面背景。"""
    bg = np.full((h, w, 3), (14, 18, 32), dtype=np.uint8)
    for y in range(h):
        glow = int(20 * (1 - abs((y / h) - 0.5) * 2))
        bg[y] = np.clip(bg[y] + (glow, glow, glow), 0, 255)

    card_x0, card_y0 = 72, 72
    card_x1, card_y1 = w - 72, h - 92
    cv2.rectangle(bg, (card_x0, card_y0), (card_x1, card_y1), (22, 31, 54), -1)
    cv2.rectangle(bg, (card_x0, card_y0), (card_x1, card_y1), (130, 160, 220), 2)

    mode_name = {
        MonsterMode.ZOMBIE: "殭屍挑戰",
        MonsterMode.SKELETON: "骷髏挑戰",
        MonsterMode.BAT: "蝙蝠挑戰",
        MonsterMode.MIXED: "混合挑戰",
    }[monster_mode]

    put_text_centered(bg, "體感硬核健身房", w // 2, card_y0 + 52,
                      size=52, color=(255, 220, 100), bold=True)
    put_text_centered(bg, "FITNESS BATTLE GAME", w // 2, card_y0 + 108,
                      size=28, color=(175, 235, 240), bold=False)
    put_text_centered(bg, "選擇挑戰模式並用動作打敗怪物", w // 2, card_y0 + 150,
                      size=22, color=(200, 200, 230))

    put_text_centered(bg, f"當前關卡：{mode_name}", w // 2, card_y0 + 190,
                      size=24, color=(220, 220, 255), bold=True)

    button_y = card_y0 + 240
    btn_w, btn_h = 180, 70
    btn_gap = 28
    btn_x = w // 2 - (btn_w * 4 + btn_gap * 3) // 2
    active_index = {
        MonsterMode.ZOMBIE: 0,
        MonsterMode.SKELETON: 1,
        MonsterMode.BAT: 2,
        MonsterMode.MIXED: 3,
    }[monster_mode]

    for i, label in enumerate(["1 殭屍", "2 骷髏", "3 蝙蝠", "4 混合"]):
        x = btn_x + i * (btn_w + btn_gap)
        if i == active_index:
            color = (95, 170, 255)
            border = (245, 245, 255)
        else:
            color = (55, 85, 140)
            border = (140, 170, 220)
        draw_button(bg, x, button_y, btn_w, btn_h, label, color, border=border)

    draw_button(bg, w // 2 - 200, card_y1 - 100, 180, 64,
                "ENTER 開始", (80, 210, 180), border=(255, 255, 255))
    draw_button(bg, w // 2 + 20, card_y1 - 100, 180, 64,
                "Q 退出", (220, 120, 120), border=(255, 255, 255))

    put_text_centered(bg, "按 1-4 選擇模式，ENTER 開始  |  Q/ESC 離開", w // 2, card_y1 - 28,
                      size=20, color=(190, 210, 240))
    put_text_centered(bg, "遊戲中可按 M 開啟怪物圖鑑", w // 2, card_y1 - 54,
                      size=18, color=(180, 210, 220))

    return bg


def draw_exercise_panel(frame: np.ndarray, counter: ExerciseCounter):
    """在畫面下方繪製動作計數面板。"""
    h, w = frame.shape[:2]
    ph   = 105

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - ph), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.60, frame, 0.40, 0, frame)

    # 深蹲計數（左）
    put_text(frame, "深蹲 SQUATS",
             (18, h - ph + 6), size=22, color=(80, 255, 130))
    squat_str = str(counter.squat_count)
    sw, sh = text_size(squat_str, 56)
    put_text(frame, squat_str,
             (18, h - sh - 10), size=56, color=(80, 255, 130))

    # 伏地挺身計數（右）
    pushup_label = "伏地挺身 PUSH-UPS"
    plw, _ = text_size(pushup_label, 22)
    put_text(frame, pushup_label,
             (w - plw - 18, h - ph + 6), size=22, color=(80, 180, 255))
    pushup_str = str(counter.pushup_count)
    pw, ph2 = text_size(pushup_str, 56)
    put_text(frame, pushup_str,
             (w - pw - 18, h - ph2 - 10), size=56, color=(80, 180, 255))

    # 目前模式（中央）
    if counter.body_orientation == "horizontal":
        mode_text  = ">> 伏地挺身模式 <<"
        mode_color = (80, 180, 255)
    else:
        mode_text  = ">> 深蹲模式 <<"
        mode_color = (80, 255, 130)
    put_text_centered(frame, mode_text, w // 2, h - ph + 38, size=24, color=mode_color)

    # 姿勢回饋（中央偏下）
    if counter.form_feedback:
        put_text_centered(frame, counter.form_feedback,
                          w // 2, h - 34, size=20, color=(255, 220, 50))

    # 關節角度量表
    angle = counter.current_angle()
    if angle is not None:
        _draw_angle_gauge(frame, angle, counter.current_exercise,
                          center=(w // 2, h - ph + 82))


def _draw_angle_gauge(frame: np.ndarray,
                      angle: float,
                      ex_type: ExerciseType,
                      center: Tuple[int, int]):
    """以半圓弧顯示目前關節角度。"""
    cx, cy = center
    r      = 22

    # 底色弧
    cv2.ellipse(frame, (cx, cy), (r, r), 0, 0, 180, (50, 50, 50), 3)

    # 填色弧（正規化至 70°~180°）
    norm = min(max((angle - 70) / 110.0, 0), 1)
    arc  = int(180 * norm)

    if ex_type == ExerciseType.SQUAT:
        good = angle < 100
        fill_c = (80, 255, 130) if good else (50, 150, 80)
    else:
        good = angle < 90
        fill_c = (80, 180, 255) if good else (50, 100, 150)

    if arc > 0:
        cv2.ellipse(frame, (cx, cy), (r, r), 0, 0, arc, fill_c, 3)

    cv2.putText(frame, f"{angle:.0f}°",
                (cx - 17, cy - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1)


def draw_player_marker(frame: np.ndarray,
                       pos: Optional[Tuple[int, int]],
                       laser_ready: bool):
    """在玩家身體中心繪製瞄準標記。"""
    if pos is None:
        return
    px, py = pos
    color  = (0, 255, 255) if laser_ready else (100, 100, 100)
    cv2.drawMarker(frame, (px, py), color, cv2.MARKER_CROSS, 22, 2, cv2.LINE_AA)
    cv2.circle(frame, (px, py), 16, color, 1, cv2.LINE_AA)


def draw_no_pose_warning(frame: np.ndarray):
    """若未偵測到人物，顯示警告。"""
    h, w = frame.shape[:2]
    msg  = "!! 未偵測到人物 — 請站入攝影機視野"
    put_text_centered(frame, msg, w // 2, 72, size=24, color=(0, 80, 255), shadow=True)


def draw_button(frame: np.ndarray,
                x: int,
                y: int,
                w: int,
                h: int,
                text: str,
                fill: Tuple[int, int, int],
                border: Tuple[int, int, int] = (255, 255, 255),
                text_color: Tuple[int, int, int] = (255, 255, 255)):
    """繪製簡單按鈕樣式。"""
    cv2.rectangle(frame, (x, y), (x + w, y + h), fill, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), border, 2)
    put_text_centered(frame, text, x + w // 2, y + h // 2 - 6,
                      size=20, color=text_color, bold=True)


def draw_monster_page(frame: np.ndarray, game: GameState):
    """繪製怪物圖鑑頁面。"""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (12, 18, 30), -1)
    cv2.addWeighted(overlay, 0.92, frame, 0.08, 0, frame)

    put_text_centered(frame, "怪物圖鑑", w // 2, 40, size=48, color=(255, 220, 100), bold=True)
    put_text_centered(
        frame,
        f"當前等級 LV.{game.level}  |  怪物數 {len(game.monsters)}",
        w // 2,
        90,
        size=24,
        color=(200, 220, 255),
    )

    if game.monsters:
        card_w, card_h = 230, 124
        for index, mon in enumerate(game.monsters[:6]):
            col = index % 3
            row = index // 3
            x = 60 + col * 260
            y = 130 + row * 150

            cv2.rectangle(frame, (x, y), (x + card_w, y + card_h), (32, 40, 52), -1)
            cv2.rectangle(frame, (x, y), (x + card_w, y + card_h), (95, 110, 170), 2)

            put_text(frame, f"{index + 1}. {mon.mtype.name}", (x + 14, y + 18), size=22, color=(245, 240, 210), bold=True)
            put_text(frame, f"HP: {mon.hp}/{mon.max_hp}", (x + 14, y + 48), size=20, color=(180, 255, 190))
            put_text(frame, f"速度: {mon.speed:.1f}", (x + 14, y + 74), size=20, color=(170, 210, 255))

            desc = {
                "ZOMBIE": "標準怪物，耐打且不會飛。",
                "SKELETON": "中速怪物，血量適中。",
                "BAT": "飛行怪物，移動較快。",
            }.get(mon.mtype.name, "未知怪物")
            put_text(frame, desc, (x + 14, y + 100), size=17, color=(210, 210, 210))
    else:
        put_text_centered(frame, "目前畫面上沒有怪物。回到遊戲開始戰鬥！", w // 2, h // 2, size=26, color=(220, 220, 220))

    put_text_centered(frame, "按 M 返回遊戲 | R 重新開始 | P 暫停 | S 截圖 | Q 退出", w // 2, h - 42, size=20, color=(180, 180, 220))
    put_text_centered(frame, "最多顯示前 6 隻怪物資訊", w // 2, h - 20, size=16, color=(140, 140, 170))


def draw_key_hints(frame: np.ndarray):
    """在遊戲畫面頂部繪製按鍵使用提示。"""
    h, w = frame.shape[:2]
    hint = "R 重新開始  |  P 暫停/繼續  |  M 怪物圖鑑  |  S 截圖  |  Q 退出"
    put_text_centered(frame, hint, w // 2, 36, size=20, color=(200, 200, 220), shadow=True)


# ══════════════════════════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── 攝影機初始化 ──────────────────────────────────────────────────────────
    print("🎥  初始化攝影機中...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌  無法開啟攝影機！請確認裝置已連接。")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"✅  攝影機解析度：{W} x {H}")

    # ── 模組初始化 ────────────────────────────────────────────────────────────
    print("🦾  載入姿態偵測模型...")
    detector = PoseDetector(min_detection_confidence=0.6, min_tracking_confidence=0.5)
    counter  = ExerciseCounter()

    def make_game(monster_mode: MonsterMode) -> GameState:
        return GameState((W, H), monster_mode=monster_mode)

    selected_mode = MonsterMode.MIXED
    game = make_game(selected_mode)

    # ── 視窗 ──────────────────────────────────────────────────────────────────
    WIN = "體感健身房 — Fitness Battle"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, W, H)

    start_bg         = make_start_screen(W, H, selected_mode)
    game_started     = False
    show_monster_page = False

    prev_t   = time.time()
    fps_disp = 30.0

    print("\n🎮  遊戲就緒！按 SPACE 或 ENTER 開始。")
    print("    Q / ESC  退出  |  R  重新開始  |  P  暫停  |  M 怪物圖鑑")

    # ── 主迴圈 ────────────────────────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌  無法讀取攝影機畫面")
            break

        frame = cv2.flip(frame, 1)   # 鏡像翻轉

        # FPS 計算
        now   = time.time()
        dt    = max(now - prev_t, 1e-4)
        fps_disp = fps_disp * 0.9 + (1.0 / dt) * 0.1
        prev_t = now

        # ── 開始畫面（乾淨，不執行姿態偵測） ───────────────────────────────────────
        if not game_started:
            blend = start_bg.copy()

            cv2.imshow(WIN, blend)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord(' '), 13):    # SPACE 或 ENTER
                # 玩家按下開始，才啟動姿態偵測
                game_started = True
            elif key == ord('1'):
                selected_mode = MonsterMode.ZOMBIE
                game = make_game(selected_mode)
                start_bg = make_start_screen(W, H, selected_mode)
            elif key == ord('2'):
                selected_mode = MonsterMode.SKELETON
                game = make_game(selected_mode)
                start_bg = make_start_screen(W, H, selected_mode)
            elif key == ord('3'):
                selected_mode = MonsterMode.BAT
                game = make_game(selected_mode)
                start_bg = make_start_screen(W, H, selected_mode)
            elif key == ord('4'):
                selected_mode = MonsterMode.MIXED
                game = make_game(selected_mode)
                start_bg = make_start_screen(W, H, selected_mode)
            elif key in (ord('q'), 27):
                break
            continue

        # ── 遊戲執行中 ────────────────────────────────────────────────────────

        if show_monster_page:
            draw_monster_page(frame, game)
            cv2.imshow(WIN, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):           # 離開
                break
            elif key == ord('m'):
                show_monster_page = False
            elif key == ord('r'):
                game = make_game(selected_mode)
                counter.reset()
                print("🔄  遊戲重新開始！")
            elif key == ord('p'):
                if game.paused:
                    game.paused = False
                    game.message = ""
                    print("▶  繼續遊戲")
                else:
                    game.paused = True
                    game.show_message("|| 遊戲暫停  — 按 H 返回首頁", 999_999)
                    print("⏸  遊戲暫停（按 H 返回首頁）")
            elif key == ord('s'):
                ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"fitness_battle_{ts}.png"
                cv2.imwrite(fname, frame)
                print(f"📷  截圖已儲存：{fname}")
                game.show_message("截圖 OK", 60)
            continue

        # 姿態偵測
        detector.process(frame)

        # 半透明骨架疊加
        pose_layer = frame.copy()
        detector.draw_landmarks(pose_layer)
        cv2.addWeighted(pose_layer, 0.65, frame, 0.35, 0, frame)

        # 玩家位置
        player_pos = detector.body_center_pixel(frame.shape)

        # 動作判斷 → 發射雷射
        if not game.game_over and not game.paused:
            rep = counter.update(detector)
            if rep is not None:
                px = player_pos[0] if player_pos else W // 2
                py = player_pos[1] if player_pos else H // 2
                pushup_mode = (rep == ExerciseType.PUSHUP)
                game.fire_laser(px, py, pushup_mode=pushup_mode)

        # 更新遊戲狀態
        if player_pos:
            game.update(player_pos[0], player_pos[1])
        else:
            game.update()

        # ── 繪製遊戲物件（後→前） ─────────────────────────────────────────────
        for exp  in game.explosions: exp.draw(frame)
        for mon  in game.monsters:   mon.draw(frame)
        for las  in game.lasers:     las.draw(frame)

        draw_player_marker(frame, player_pos, game.laser_ready)

        # ── UI ────────────────────────────────────────────────────────────────
        game.draw_hud(frame)
        draw_exercise_panel(frame, counter)
        draw_key_hints(frame)

        if not detector.is_visible():
            draw_no_pose_warning(frame)

        # FPS 小字
        cv2.putText(frame, f"FPS {fps_disp:.0f}",
                    (W - 90, H - 112),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 120, 120), 1)

        cv2.imshow(WIN, frame)

        # ── 按鍵處理 ──────────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):           # 離開
            break

        elif key == ord('r'):               # 重新開始
            game = make_game(selected_mode)
            counter.reset()
            print("🔄  遊戲重新開始！")

        elif key == ord('m'):               # 怪物圖鑑
            show_monster_page = True

        elif key == ord('p'):               # 暫停 / 繼續
            if game.paused:
                game.paused = False
                game.message = ""
                print("▶  繼續遊戲")
            else:
                game.paused = True
                game.show_message("|| 遊戲暫停  — 按 H 返回首頁", 999_999)
                print("⏸  遊戲暫停（按 H 返回首頁）")

        elif key == ord('s'):               # 截圖
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"fitness_battle_{ts}.png"
            cv2.imwrite(fname, frame)
            print(f"📷  截圖已儲存：{fname}")
            game.show_message("截圖 OK", 60)

        elif key == ord('f'):               # 測試發射（除錯）
            if not game.game_over and player_pos:
                game.laser_ready = True
                game.fire_laser(player_pos[0], player_pos[1], pushup_mode=False)

        elif key == ord('h') and (game.game_over or game.paused):   # 遊戲結束或暫停時返回首頁
            game = make_game(selected_mode)
            counter.reset()
            game_started = False

        elif key == ord(' ') and game.game_over:   # 遊戲結束後按空白重啟
            game = make_game(selected_mode)
            counter.reset()

    # ── 結束 ──────────────────────────────────────────────────────────────────
    cap.release()
    cv2.destroyAllWindows()

    print("\n🎮  遊戲結束！")
    print(f"    最終分數    ：{game.score}")
    print(f"    深蹲次數    ：{counter.squat_count}")
    print(f"    伏地挺身次數：{counter.pushup_count}")
    print(f"    到達等級    ：{game.level}")


if __name__ == "__main__":
    main()
