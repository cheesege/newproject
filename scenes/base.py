"""
scenes/base.py
Scene 狀態機基底（State 模式）。

主迴圈不該是一坨 if-else，而是把輸入與畫面交給「當前 Scene」。
新增畫面 = 新增一個 Scene 子類。

每個 Scene：
    on_enter(**kwargs)  切入此場景時呼叫（可帶參數，如 user_id）
    on_exit()           離開此場景時呼叫
    handle_input(key)   處理按鍵（cv2.waitKey 的回傳值）
    update(dt, frame)   更新狀態（dt 秒；frame 為當前攝影機畫面，可能為 None）
    draw(frame)         畫到畫面上

切換場景：在 handle_input/update 內呼叫 self.go(目標名稱, **kwargs)。
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np

from text_utils import put_text_centered


def fill_bg(frame, color=(16, 20, 32)):
    """把整張畫面填成單色背景（給非攝影機場景用）。"""
    frame[:] = color
    return frame


def draw_placeholder(frame, title: str, hints: List[str], subtitle: str = ""):
    """任務一用：畫場景標題與導覽提示（之後各任務會以真正內容取代）。"""
    h, w = frame.shape[:2]
    fill_bg(frame)
    put_text_centered(frame, title, w // 2, h // 2 - 120, size=56,
                      color=(255, 220, 100), bold=True)
    if subtitle:
        put_text_centered(frame, subtitle, w // 2, h // 2 - 50, size=26,
                          color=(190, 210, 240))
    for i, line in enumerate(hints):
        put_text_centered(frame, line, w // 2, h // 2 + 20 + i * 40, size=24,
                          color=(200, 210, 230))
    return frame


# ── 場景名稱常數 ──────────────────────────────────────────────────────────────
class SceneName:
    USER_SELECT = "USER_SELECT"
    HUB = "HUB"
    PRE_GAME = "PRE_GAME"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    RESULT = "RESULT"
    TRENDS = "TRENDS"
    TWIN = "TWIN"
    CAMERA = "CAMERA"


QUIT = "__quit__"     # 特殊目標：結束程式


class Scene:
    def __init__(self, app):
        self.app = app
        # 要切換到的下一個場景：(name, kwargs)；None 表示不切換
        self.next_scene: Optional[Tuple[str, dict]] = None

    # ── 生命週期 ──
    def on_enter(self, **kwargs) -> None:
        pass

    def on_exit(self) -> None:
        pass

    # ── 每幀 ──
    def handle_input(self, key: int) -> None:
        pass

    def update(self, dt: float, frame) -> None:
        pass

    def draw(self, frame) -> None:
        pass

    # ── 切換工具 ──
    def go(self, name: str, **kwargs) -> None:
        """請求切換到另一個場景。"""
        self.next_scene = (name, kwargs)

    def quit(self) -> None:
        self.next_scene = (QUIT, {})
