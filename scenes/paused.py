"""scenes/paused.py — 暫停（任務四）：可續玩或放棄返回主頁。"""

import cv2

from scenes.base import Scene, SceneName
from text_utils import put_text_centered


class PausedScene(Scene):
    def handle_input(self, key):
        if key == ord('c'):                 # 續玩（保留同一場 game）
            self.go(SceneName.PLAYING)
        elif key in (ord('h'), 27):         # 放棄並返回主頁（丟棄本場）
            self.app.game = None
            self.go(SceneName.HUB)

    def draw(self, frame):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        put_text_centered(frame, "已暫停", w // 2, h // 2 - 110, size=64,
                          color=(255, 220, 100), bold=True)
        game = self.app.game
        if game is not None:
            put_text_centered(frame, f"目前分數 {game.score}　等級 Lv.{game.level}",
                              w // 2, h // 2 - 30, size=30, color=(220, 230, 250))
        put_text_centered(frame, "C → 繼續訓練", w // 2, h // 2 + 40, size=30,
                          color=(150, 235, 180), bold=True)
        put_text_centered(frame, "H / ESC → 放棄並返回主頁（本場不計入）",
                          w // 2, h // 2 + 90, size=26, color=(255, 190, 170))
