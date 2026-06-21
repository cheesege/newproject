"""scenes/playing.py — 訓練打怪核心。

讀幀→偵測→動作判定→發射雷射→更新遊戲→繪製骨架/怪物/雷射/HUD。
保留怪物三型、四模式、雷射齊射、爆炸、生命、計分、升級、冷卻、半透明骨架、
角度量表、瞄準準星、無人物警告、FPS、怪物圖鑑。
"""

import time
from datetime import datetime

import cv2

from calories import session_calories
from game_objects import GameState
from scenes.base import Scene, SceneName
from text_utils import put_text_centered
from ui_widgets import (draw_exercise_panel, draw_monster_page,
                        draw_no_pose_warning, draw_player_marker)


class PlayingScene(Scene):
    DETECT_EVERY = 2        # 每隔幾幀才跑一次姿態偵測（其餘幀沿用上次骨架），提升 FPS
    GAMEOVER_DWELL = 3.0    # Game Over 後在結算前停留秒數（可按鍵提前）

    def on_enter(self, new=False, **kwargs):
        app = self.app
        if new or app.game is None:
            app.game = GameState((app.W, app.H), monster_mode=app.selected_mode)
            app.counter.set_enabled(app.selected_exercises)   # 本場選定的動作
            app.counter.reset()
            app.game_start_iso = datetime.now().isoformat(timespec="seconds")
            self._ended = False
            self._gameover_t = None
            self._fps = 30.0
            print(f"🎮  開始訓練（模式 {app.selected_mode.name}）")
        self.show_monster = False
        self._player_pos = None
        self._want_screenshot = None
        self._tick = 0

    def _weight(self) -> float:
        u = self.app.current_user
        return u.weight if u else 65.0

    # ── 每幀邏輯 ──
    def update(self, dt, frame):
        if frame is None:
            return
        self._fps = self._fps * 0.9 + (1.0 / max(dt, 1e-4)) * 0.1
        app, game = self.app, self.app.game
        if self.show_monster:
            return

        # 偵測節流：每 DETECT_EVERY 幀才做一次姿態偵測與動作判定
        self._tick += 1
        if self._tick % self.DETECT_EVERY == 0 and not game.game_over:
            app.detector.process(frame)
            self._player_pos = app.detector.body_center_pixel(frame.shape)

            completed = app.counter.update(app.detector)
            if completed is not None:
                px = self._player_pos[0] if self._player_pos else app.W // 2
                py = self._player_pos[1] if self._player_pos else app.H // 2
                game.fire_laser(px, py, pushup_mode=(completed.game_action == "triple"))
            else:
                err = app.counter.form_error()
                if err:
                    key = {"squat": "squat_depth", "pushup": "pushup_depth"}.get(
                        app.counter.display_exercise.key, "form_alert")
                    app.sound_mgr.play(key)

        if self._player_pos:
            game.update(self._player_pos[0], self._player_pos[1])
        else:
            game.update()

        # Game Over：先準備結算資料，停留數秒（或按鍵）再切到 RESULT，避免一閃而過
        if game.game_over and not self._ended:
            self._ended = True
            self._gameover_t = time.time()
            reps = app.counter.reps()
            app.last_result = {
                "reps": reps,
                "score": game.score,
                "level": game.level,
                "calories": session_calories(reps, self._weight()),
                "started_at": app.game_start_iso,
            }
        if self._ended and (time.time() - self._gameover_t) >= self.GAMEOVER_DWELL:
            self.go(SceneName.RESULT)

    # ── 繪製 ──
    def draw(self, frame):
        app, game = self.app, self.app.game
        if self.show_monster:
            draw_monster_page(frame, game)
            return

        pose_layer = frame.copy()
        app.detector.draw_landmarks(pose_layer)
        cv2.addWeighted(pose_layer, 0.65, frame, 0.35, 0, frame)

        for exp in game.explosions:
            exp.draw(frame)
        for mon in game.monsters:
            mon.draw(frame)
        for las in game.lasers:
            las.draw(frame)

        draw_player_marker(frame, self._player_pos, game.laser_ready)

        game.draw_hud(frame)
        cur_cal = session_calories(app.counter.reps(), self._weight())
        draw_exercise_panel(frame, app.counter, calories=cur_cal)

        if self._ended:
            # Game Over 停留畫面提示（game.draw_hud 已畫 GAME OVER 大字）
            remain = max(0, int(self.GAMEOVER_DWELL - (time.time() - self._gameover_t)) + 1)
            put_text_centered(frame, f"按任意鍵查看本場結算（{remain} 秒後自動）",
                              app.W // 2, app.H // 2 + 40, size=26,
                              color=(255, 235, 160), shadow=True)
        else:
            put_text_centered(frame, "P 暫停 ｜ M 圖鑑 ｜ S 截圖 ｜ F 測試發射(免動作)",
                              app.W // 2, 66, size=18, color=(190, 200, 220), shadow=True)

        if not app.detector.is_visible() and not self._ended:
            draw_no_pose_warning(frame)

        cv2.putText(frame, f"FPS {self._fps:.0f}", (app.W - 90, app.H - 108),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 120, 120), 1)

        if self._want_screenshot:
            cv2.imwrite(self._want_screenshot, frame)
            self._want_screenshot = None

    # ── 輸入 ──
    def handle_input(self, key):
        app, game = self.app, self.app.game

        # Game Over 停留中：任意鍵立即進結算
        if self._ended:
            self.go(SceneName.RESULT)
            return

        if self.show_monster:
            if key in (ord('m'), 27):
                self.show_monster = False
            return

        if key in (ord('p'), 27):
            self.go(SceneName.PAUSED)
        elif key == ord('m'):
            self.show_monster = True
        elif key == ord('s'):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"fitness_battle_{ts}.png"
            print(f"📷  截圖已儲存：{fname}")
            game.show_message("截圖 OK", 60)
            self._want_screenshot = fname
        elif key == ord('f'):
            # 測試發射：不用做動作，直接發射一發雷射（除錯／展示用）。
            # 沒有玩家座標就用畫面中心；場上沒怪就先生一隻，確保看得到效果。
            if not game.game_over:
                px = self._player_pos[0] if self._player_pos else app.W // 2
                py = self._player_pos[1] if self._player_pos else app.H // 2
                if not any(m.alive for m in game.monsters):
                    game._spawn_monster()
                game.laser_ready = True
                fired = game.fire_laser(px, py, pushup_mode=False)
                game.show_message("測試發射！" if fired else "測試發射（無目標）", 45)
