"""scenes/result.py — 結算與成長（任務五）。

把「這場訓練」與「長期養成」用因果串起來：顯示本場成績、寫入該使用者 sessions、
依本場數據更新 twin_state，並視覺化分身的成長量。
"""

import digital_twin
from scenes.base import Scene, SceneName, fill_bg
from text_utils import put_text, put_text_centered


class ResultScene(Scene):
    def on_enter(self, **kwargs):
        self.res = self.app.last_result
        self.growth = None
        user = self.app.current_user

        if self.res and user:
            user.add_session(
                self.res["reps"], self.res["score"], self.res["level"],
                self.res["calories"], started_at=self.res.get("started_at"),
            )
            self.growth = digital_twin.apply_session_growth(user.id)
            print(f"💾  已存檔：{user.name} 分數 {self.res['score']}、"
                  f"卡路里 {self.res['calories']:.1f}")
            # 消費掉，避免返回再次寫入；清掉本場 game
            self.app.last_result = None
            self.app.game = None

    def handle_input(self, key):
        if key in (13, 10, ord('h'), 27):
            self.go(SceneName.HUB)

    def draw(self, frame):
        h, w = frame.shape[:2]
        fill_bg(frame)
        put_text_centered(frame, "訓練結算", w // 2, 64, size=52,
                          color=(255, 220, 100), bold=True)

        if not self.res:
            put_text_centered(frame, "（無本場資料）", w // 2, h // 2, size=30,
                              color=(210, 210, 210))
            put_text_centered(frame, "Enter / H → 返回主頁", w // 2, h - 50,
                              size=24, color=(190, 210, 240))
            return

        from exercises import get_meta
        reps = self.res["reps"]
        # 左欄：本場成績（只列本場「選擇的」動作）
        x = w // 2 - 380
        y = 150
        rows = []
        for key, count in reps.items():
            meta = get_meta(key)
            name = meta.name if meta else key
            rows.append(f"{name}：{count} 下")
        rows += [
            f"分數：{self.res['score']}",
            f"到達等級：Lv.{self.res['level']}",
            f"消耗卡路里：{self.res['calories']:.1f} kcal",
        ]
        put_text(frame, "本場成績", (x, y - 44), size=30, color=(150, 235, 180), bold=True)
        for i, r in enumerate(rows):
            put_text(frame, r, (x, y + i * 46), size=26, color=(230, 235, 245))

        # 右欄：分身成長
        gx = w // 2 + 40
        put_text(frame, "數位分身成長", (gx, y - 44), size=30,
                 color=(120, 230, 255), bold=True)
        if self.growth:
            new = self.growth["new"]
            d = self.growth["delta"]
            digital_twin.draw_avatar(frame, gx + 90, y + 150, new["level"], new["physique"])

            def fmt(label, delta, total):
                sign = f"+{delta:.0f}" if delta > 0 else f"{delta:.0f}"
                return f"{label} {sign}　(現 {total:.0f})"

            grows = [
                fmt("力量", d["strength"], new["strength"]),
                fmt("耐力", d["stamina"], new["stamina"]),
                fmt("體態", d["physique"], new["physique"]),
            ]
            gy = y + 250
            for i, g in enumerate(grows):
                put_text(frame, g, (gx, gy + i * 40), size=24, color=(200, 230, 210))
            if d["level"] > 0:
                put_text_centered(frame, f"升到 Lv.{new['level']}！", w // 2, h - 110,
                                  size=34, color=(255, 220, 100), bold=True)

        put_text_centered(frame, "Enter / H → 返回主頁", w // 2, h - 50,
                          size=24, color=(190, 210, 240))
