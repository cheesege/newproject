"""scenes/trends.py — 趨勢與預測（OpenCV 繪製版）。

用 OpenCV 在遊戲風格背景上畫該使用者的次數/卡路里/BMI 折線，並疊上預測虛線。
"""

import trends as trends_module
from scenes.base import Scene, SceneName, fill_bg
from text_utils import put_text_centered


class TrendsScene(Scene):
    def on_enter(self, **kwargs):
        self._img = None
        self._msg = ""
        user = self.app.current_user
        if user is None:
            self._msg = "請先選擇使用者"
            return
        self._img = trends_module.render_trends(user.id, (self.app.W, self.app.H))
        if self._img is None:
            self._msg = "尚無足夠資料可繪製趨勢圖，先訓練幾場吧！"

    def handle_input(self, key):
        if key != 255:
            self.go(SceneName.HUB)

    def draw(self, frame):
        if self._img is not None:
            frame[:] = self._img
        else:
            h, w = frame.shape[:2]
            fill_bg(frame)
            put_text_centered(frame, "體能趨勢", w // 2, h // 2 - 40, size=44,
                              color=(255, 220, 100), bold=True)
            put_text_centered(frame, self._msg, w // 2, h // 2 + 20, size=26,
                              color=(220, 220, 220))
            put_text_centered(frame, "按任意鍵返回主頁", w // 2, h - 50, size=24,
                              color=(190, 210, 240))
