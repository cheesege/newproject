"""scenes/twin.py — 數位分身（任務七），與當前使用者綁定。

完整屬性面板（力量/耐力/體態 + 等級 + 會長大的角色）+ 數據來源說明 + 預測。
"""

import digital_twin
from scenes.base import Scene, SceneName, fill_bg
from text_utils import put_text_centered


class TwinScene(Scene):
    def on_enter(self, **kwargs):
        self._panel = None
        user = self.app.current_user
        if user is not None:
            self._panel = digital_twin.render_panel(user, (self.app.W, self.app.H))

    def handle_input(self, key):
        if key == ord('t'):                 # 看含預測的趨勢圖
            self.go(SceneName.TRENDS)
        elif key != 255:
            self.go(SceneName.HUB)

    def draw(self, frame):
        if self._panel is not None:
            frame[:] = self._panel
        else:
            h, w = frame.shape[:2]
            fill_bg(frame)
            put_text_centered(frame, "請先選擇使用者", w // 2, h // 2, size=30,
                              color=(220, 220, 220))
