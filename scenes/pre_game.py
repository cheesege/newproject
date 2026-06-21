"""scenes/pre_game.py — 訓練前設定。

全部用數字鍵操作：
  動作（單選，每輪一個）：1 深蹲 / 2 伏地挺身 / 3 舉手
  挑戰模式：             4 殭屍 / 5 骷髏 / 6 蝙蝠 / 7 混合
  ENTER 開始 / ESC 返回
"""

from scenes.base import Scene, SceneName, fill_bg
from game_objects import MonsterMode
from ui_widgets import draw_button, EX_COLORS
from text_utils import put_text, put_text_centered

# 動作單選：(數字鍵, key, 名稱, 體位, 攻擊說明)
_EXERCISES = [
    (ord('1'), "squat", "深蹲", "站立", "雷射單體（最近 1 隻）"),
    (ord('2'), "pushup", "伏地挺身", "水平", "雷射齊射（最近 3 隻）"),
    (ord('3'), "raise_hand", "舉手(測試)", "坐姿", "雷射單體（驗證流程用）"),
]
# 模式選擇：(數字鍵, mode, 名稱)
_MODES = [
    (ord('4'), MonsterMode.ZOMBIE, "殭屍"),
    (ord('5'), MonsterMode.SKELETON, "骷髏"),
    (ord('6'), MonsterMode.BAT, "蝙蝠"),
    (ord('7'), MonsterMode.MIXED, "混合"),
]


class PreGameScene(Scene):
    def handle_input(self, key):
        for k, ex_key, *_ in _EXERCISES:
            if key == k:
                self.app.selected_exercises = [ex_key]   # 單選：每輪一個動作
                return
        for k, mode, _ in _MODES:
            if key == k:
                self.app.selected_mode = mode
                return
        if key in (13, 10):
            self.go(SceneName.PLAYING, new=True)
        elif key in (27, ord('h')):
            self.go(SceneName.HUB)

    def _current_ex(self):
        return self.app.selected_exercises[0] if self.app.selected_exercises else None

    def draw(self, frame):
        h, w = frame.shape[:2]
        fill_bg(frame)
        user = self.app.current_user
        who = user.name if user else "訪客"
        put_text_centered(frame, "訓練前設定", w // 2, 50, size=46,
                          color=(255, 220, 100), bold=True)
        put_text_centered(frame, f"訓練者：{who}（每輪選一個動作）", w // 2, 100,
                          size=24, color=(190, 230, 255))

        # ── 動作單選 ──
        cur = self._current_ex()
        put_text_centered(frame, "選擇本場動作（按 1 / 2 / 3）", w // 2, 150,
                          size=24, color=(210, 220, 240))
        rx = w // 2 - 360
        for i, (kk, ex_key, name, orient, atk) in enumerate(_EXERCISES):
            y = 188 + i * 56
            on = (ex_key == cur)
            mark = "●" if on else "○"
            color = EX_COLORS.get(ex_key, (220, 220, 220)) if on else (130, 140, 160)
            put_text(frame, f"{mark} {i + 1}. {name}（{orient}）", (rx, y), size=28,
                     color=color, bold=on)
            put_text(frame, atk, (rx + 380, y + 4), size=22,
                     color=(200, 215, 235) if on else (110, 120, 140))

        # ── 模式選擇 ──
        put_text_centered(frame, "挑戰模式（按 4 ~ 7）", w // 2, 376,
                          size=24, color=(210, 220, 240))
        btn_w, btn_h, gap = 190, 58, 22
        total = btn_w * 4 + gap * 3
        x0 = w // 2 - total // 2
        for i, (kk, mode, name) in enumerate(_MODES):
            x = x0 + i * (btn_w + gap)
            active = (mode == self.app.selected_mode)
            fill = (95, 170, 255) if active else (55, 85, 140)
            border = (245, 245, 255) if active else (140, 170, 220)
            draw_button(frame, x, 410, btn_w, btn_h, f"{i + 4} {name}", fill, border=border)

        put_text_centered(frame, "1-3 選動作 ｜ 4-7 選模式 ｜ ENTER 開始 ｜ ESC 返回",
                          w // 2, h - 40, size=24, color=(190, 210, 240))
