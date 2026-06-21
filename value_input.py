"""
value_input.py
數值輸入介面 — 把「取得一個數值」與「怎麼取得」解耦。

本輪只實作鍵盤輸入（KeyboardValueReader），但對外是抽象介面 ValueReader，
之後語音／手寫只要新增一個子類接同一個 read() 介面，呼叫端（main.py）不必更改。

設計
----
    reader = KeyboardValueReader(cap, window_name, (W, H))
    height = reader.read("請輸入身高", unit="cm", min_v=80, max_v=250)
    weight = reader.read("請輸入體重", unit="kg", min_v=20, max_v=300)
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2
import numpy as np

from text_utils import put_text, put_text_centered


class ValueReader(ABC):
    """數值輸入的統一介面。回傳數值；使用者取消時回傳 None。"""

    @abstractmethod
    def read(
        self,
        prompt: str,
        unit: str = "",
        min_v: Optional[float] = None,
        max_v: Optional[float] = None,
    ) -> Optional[float]:
        raise NotImplementedError

    def read_text(self, prompt: str, max_len: int = 16) -> Optional[str]:
        """讀取一段文字（如使用者名稱）。取消時回傳 None。"""
        raise NotImplementedError


class KeyboardValueReader(ValueReader):
    """
    OpenCV 視窗內的鍵盤數值輸入。

    自行管理輸入緩衝：逐字元接收 waitKey、Enter 確認、Backspace 刪除、ESC 取消。
    輸入期間持續顯示攝影機畫面當背景（讀不到畫面時退回深色底）。
    """

    def __init__(self, cap, window_name: str, frame_size: Tuple[int, int]):
        self._cap = cap
        self._win = window_name
        self._w, self._h = frame_size

    def _background(self) -> np.ndarray:
        if self._cap is not None:
            ret, frame = self._cap.read()
            if ret:
                return cv2.flip(frame, 1)
        return np.full((self._h, self._w, 3), (18, 22, 36), dtype=np.uint8)

    def _draw_panel(self, frame: np.ndarray, prompt: str, unit: str,
                    buffer: str, error: str):
        h, w = frame.shape[:2]
        # 半透明遮罩
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # 輸入卡片
        cx0, cy0 = w // 2 - 320, h // 2 - 130
        cx1, cy1 = w // 2 + 320, h // 2 + 130
        cv2.rectangle(frame, (cx0, cy0), (cx1, cy1), (28, 36, 58), -1)
        cv2.rectangle(frame, (cx0, cy0), (cx1, cy1), (130, 160, 220), 2)

        put_text_centered(frame, prompt, w // 2, cy0 + 26, size=30,
                          color=(255, 220, 100), bold=True)

        # 輸入框
        bx0, by0 = w // 2 - 220, h // 2 - 30
        bx1, by1 = w // 2 + 220, h // 2 + 30
        cv2.rectangle(frame, (bx0, by0), (bx1, by1), (12, 16, 28), -1)
        cv2.rectangle(frame, (bx0, by0), (bx1, by1), (90, 200, 255), 2)
        shown = (buffer or "_") + (f"  {unit}" if unit else "")
        put_text(frame, shown, (bx0 + 16, by0 + 8), size=34, color=(240, 250, 255))

        if error:
            put_text_centered(frame, error, w // 2, cy1 - 64, size=20, color=(120, 120, 255))
        put_text_centered(frame, "輸入數字 → Enter 確認 ｜ Backspace 刪除 ｜ Esc 取消",
                          w // 2, cy1 - 30, size=20, color=(190, 210, 240))

    def read(
        self,
        prompt: str,
        unit: str = "",
        min_v: Optional[float] = None,
        max_v: Optional[float] = None,
    ) -> Optional[float]:
        buffer = ""
        error = ""
        while True:
            frame = self._background()
            self._draw_panel(frame, prompt, unit, buffer, error)
            cv2.imshow(self._win, frame)

            key = cv2.waitKey(20) & 0xFF
            if key == 255:                      # 無按鍵
                continue
            if key == 27:                       # ESC 取消
                return None
            if key in (13, 10):                 # Enter 確認
                if not buffer:
                    error = "請先輸入數值"
                    continue
                try:
                    val = float(buffer)
                except ValueError:
                    error = "格式錯誤，請重新輸入"
                    buffer = ""
                    continue
                if min_v is not None and val < min_v:
                    error = f"數值需 ≥ {min_v:g}"
                    continue
                if max_v is not None and val > max_v:
                    error = f"數值需 ≤ {max_v:g}"
                    continue
                return val
            if key == 8:                        # Backspace
                buffer = buffer[:-1]
                error = ""
                continue
            ch = chr(key)
            if ch.isdigit():
                buffer += ch
                error = ""
            elif ch == "." and "." not in buffer:
                buffer += ch
                error = ""

    def read_text(self, prompt: str, max_len: int = 16) -> Optional[str]:
        """讀取一段文字（如使用者名稱）。Enter 確認、Backspace 刪除、ESC 取消。

        註：OpenCV 視窗的 waitKey 僅能取得 ASCII 鍵，故名稱以英數字為主
        （中文輸入法無法在 OpenCV 視窗運作）。
        """
        buffer = ""
        error = ""
        while True:
            frame = self._background()
            self._draw_panel(frame, prompt, "", buffer, error)
            cv2.imshow(self._win, frame)

            key = cv2.waitKey(20) & 0xFF
            if key == 255:
                continue
            if key == 27:                       # ESC 取消
                return None
            if key in (13, 10):                 # Enter 確認
                name = buffer.strip()
                if not name:
                    error = "請先輸入名稱"
                    continue
                return name
            if key == 8:                        # Backspace
                buffer = buffer[:-1]
                error = ""
                continue
            if 32 <= key <= 126 and len(buffer) < max_len:   # 可列印 ASCII
                buffer += chr(key)
                error = ""
