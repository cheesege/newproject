"""scenes/user_select.py — 選擇 / 創建使用者（任務二）。"""

import cv2

import storage
from scenes.base import Scene, SceneName, fill_bg
from text_utils import put_text, put_text_centered


class UserSelectScene(Scene):
    def on_enter(self, **kwargs):
        self._reload()

    def _reload(self):
        self.cards = []
        for u in storage.list_users():
            twin = storage.get_twin_state(u.id)
            games = len(storage.get_sessions(u.id))
            self.cards.append({"user": u, "level": twin.get("level", 1), "games": games})

    # ── 輸入 ──
    def handle_input(self, key):
        if key in (ord('q'), 27):
            self.quit()
            return
        if key == ord('n'):
            self._create_user()
            return
        # 數字鍵選擇使用者（1 起算）
        if ord('1') <= key <= ord('9'):
            idx = key - ord('1')
            if idx < len(self.cards):
                self.app.current_user = self.cards[idx]["user"]
                print(f"👤  選擇使用者：{self.app.current_user.name}")
                self.go(SceneName.HUB)

    def _create_user(self):
        vr = self.app.value_reader
        name = vr.read_text("輸入使用者名稱（英數）", max_len=16)
        if not name:
            return
        height = vr.read("輸入身高", unit="cm", min_v=80, max_v=250)
        if height is None:
            return
        weight = vr.read("輸入體重", unit="kg", min_v=20, max_v=300)
        if weight is None:
            return
        user = storage.create_user(name, height, weight)
        self.app.current_user = user
        print(f"✨  已建立使用者：{name}（BMI {storage.compute_bmi(height, weight):.1f}）")
        self.go(SceneName.HUB)

    # ── 繪製 ──
    def draw(self, frame):
        h, w = frame.shape[:2]
        fill_bg(frame)
        put_text_centered(frame, "選擇使用者", w // 2, 70, size=52,
                          color=(255, 220, 100), bold=True)
        put_text_centered(frame, "體感硬核健身房 — 你的訓練都記在你的角色身上",
                          w // 2, 124, size=24, color=(190, 210, 240))

        if not self.cards:
            put_text_centered(frame, "目前沒有使用者，按 N 創建一位開始！",
                              w // 2, h // 2, size=30, color=(220, 220, 220))
        else:
            y0 = 180
            for i, c in enumerate(self.cards[:9]):
                u = c["user"]
                y = y0 + i * 66
                cv2.rectangle(frame, (w // 2 - 360, y), (w // 2 + 360, y + 56), (28, 36, 58), -1)
                cv2.rectangle(frame, (w // 2 - 360, y), (w // 2 + 360, y + 56), (95, 120, 180), 2)
                put_text(frame, f"{i + 1}", (w // 2 - 344, y + 12), size=30,
                         color=(120, 230, 255), bold=True)
                put_text(frame, u.name, (w // 2 - 290, y + 14), size=28,
                         color=(245, 245, 250), bold=True)
                bmi = u.latest_bmi()
                info = f"Lv.{c['level']}   {c['games']} 場"
                if bmi:
                    info += f"   BMI {bmi:.1f}"
                put_text(frame, info, (w // 2 + 80, y + 16), size=24, color=(200, 215, 235))

        put_text_centered(frame, "數字鍵選擇使用者 ｜ N 創建新使用者 ｜ Q 離開",
                          w // 2, h - 40, size=24, color=(190, 210, 240))
