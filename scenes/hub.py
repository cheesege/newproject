"""scenes/hub.py — 使用者主頁（任務六）。

把所有資訊匯流到主頁：數位分身與等級、BMI 現值與本月變化、累計訓練摘要，
並提供入口：開始訓練 / 趨勢 / 數位分身 / 更新身體數據 / 切換使用者。
"""

import digital_twin
from scenes.base import Scene, SceneName, fill_bg
from text_utils import put_text, put_text_centered


class HubScene(Scene):
    def on_enter(self, **kwargs):
        # 若沒有選定使用者（理論上不會發生），退回選擇畫面
        if self.app.current_user is None:
            self.go(SceneName.USER_SELECT)

    def handle_input(self, key):
        if key == ord('g'):
            self.go(SceneName.PRE_GAME)
        elif key == ord('t'):
            self.go(SceneName.TRENDS)
        elif key == ord('d'):
            self.go(SceneName.TWIN)
        elif key == ord('b'):
            self._update_body()
        elif key == ord('u'):
            self.go(SceneName.USER_SELECT)
        elif key == ord('c'):
            self.go(SceneName.CAMERA, back=SceneName.HUB)
        elif key in (ord('q'), 27):
            self.quit()

    def _update_body(self):
        vr = self.app.value_reader
        user = self.app.current_user
        height = vr.read("更新身高", unit="cm", min_v=80, max_v=250)
        if height is None:
            return
        weight = vr.read("更新體重", unit="kg", min_v=20, max_v=300)
        if weight is None:
            return
        bmi = user.update_body(height, weight)
        print(f"💾  {user.name} 身體數據更新：BMI {bmi:.1f}")

    def draw(self, frame):
        h, w = frame.shape[:2]
        fill_bg(frame)
        user = self.app.current_user
        if user is None:
            return

        stats = digital_twin.compute_stats(user.id)
        bmi = user.latest_bmi()
        change = user.bmi_change_last_month()

        put_text_centered(frame, f"{user.name} 的主頁", w // 2, 60, size=48,
                          color=(255, 220, 100), bold=True)

        # 中央分身 + 等級
        digital_twin.draw_avatar(frame, w // 2, h // 2 - 10, stats["level"], stats["physique"])
        put_text_centered(frame, f"LV. {stats['level']}", w // 2, h // 2 + 110,
                          size=40, color=(120, 230, 255), bold=True)

        # 左欄：身體數據
        lx = 90
        ly = 150
        put_text(frame, "身體數據", (lx, ly - 40), size=28, color=(150, 235, 180), bold=True)
        if bmi:
            put_text(frame, f"BMI：{bmi:.1f}", (lx, ly), size=26, color=(230, 235, 245))
            if change is not None:
                arrow = "▲" if change > 0 else ("▼" if change < 0 else "—")
                put_text(frame, f"本月變化：{arrow} {abs(change):.1f}", (lx, ly + 40),
                         size=24, color=(200, 220, 235))
            else:
                put_text(frame, "本月變化：資料累積中", (lx, ly + 40), size=22,
                         color=(180, 190, 210))
        else:
            put_text(frame, "尚未輸入（按 B 更新）", (lx, ly), size=24, color=(190, 190, 210))

        # 右欄：累計摘要
        rx = w - 360
        put_text(frame, "累計訓練", (rx, ly - 40), size=28, color=(120, 230, 255), bold=True)
        summary = [
            f"場次：{stats['games']}",
            f"深蹲：{stats['total_squat']}　伏地挺身：{stats['total_pushup']}",
            f"消耗：{stats['total_cal']:.0f} kcal",
            f"力量 {stats['strength']:.0f} ｜ 耐力 {stats['stamina']:.0f} ｜ 體態 {stats['physique']:.0f}",
        ]
        for i, s in enumerate(summary):
            put_text(frame, s, (rx, ly + i * 40), size=22, color=(210, 220, 240))

        # 選單
        put_text_centered(frame, "G 開始訓練 ｜ T 趨勢 ｜ D 數位分身 ｜ B 更新身體數據",
                          w // 2, h - 64, size=24, color=(190, 210, 240))
        put_text_centered(frame, "U 切換使用者 ｜ C 攝影機設定 ｜ Q 離開",
                          w // 2, h - 30, size=22, color=(180, 200, 230))
