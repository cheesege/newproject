"""
sounds.py
音效播放 — 動作不標準時發出提示音，提升運動防護價值。

設計
----
- 優先使用 pygame.mixer 播放 assets/sounds/ 下的 wav 音效。
- pygame 不可用、或音效檔不存在時，降級為系統嗶聲（不讓程式崩潰）。
- 內建節流（throttle）：同一種提示音需間隔一段時間才會再響，避免連續洗版。

對外只需：
    sm = SoundManager()
    sm.play("form_alert")          # 一般「動作未達標」提示
    sm.play("squat_depth")         # 進階：深蹲不夠深
    sm.play("pushup_depth")        # 進階：伏地挺身沒到位
"""

import os
import sys
import time
from typing import Dict, Optional

_SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")


class SoundManager:
    def __init__(self, throttle_sec: float = 1.5):
        self.throttle_sec = throttle_sec
        self._last_play: Dict[str, float] = {}
        self._mixer = None
        self._sounds: Dict[str, object] = {}
        self._enabled = True

        # 嘗試啟用 pygame.mixer
        try:
            import pygame
            pygame.mixer.init()
            self._mixer = pygame.mixer
        except Exception as e:
            self._mixer = None
            print(f"🔇  音效系統未啟用（將以系統嗶聲降級）：{e}")

    # ── 內部：載入音效檔 ──────────────────────────────────────────────────────

    def _get_sound(self, name: str) -> Optional[object]:
        if self._mixer is None:
            return None
        if name in self._sounds:
            return self._sounds[name]
        path = os.path.join(_SOUND_DIR, f"{name}.wav")
        if not os.path.exists(path):
            self._sounds[name] = None
            return None
        try:
            snd = self._mixer.Sound(path)
        except Exception:
            snd = None
        self._sounds[name] = snd
        return snd

    @staticmethod
    def _system_beep():
        """跨平台系統嗶聲降級。"""
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.Beep(660, 150)
            else:
                # 終端機響鈴；無音效檔/無 pygame 時的最後手段
                sys.stdout.write("\a")
                sys.stdout.flush()
        except Exception:
            pass

    # ── 對外：播放（含節流） ──────────────────────────────────────────────────

    def play(self, name: str = "form_alert"):
        if not self._enabled:
            return
        now = time.time()
        if now - self._last_play.get(name, 0.0) < self.throttle_sec:
            return                      # 節流：間隔不足，跳過
        self._last_play[name] = now

        snd = self._get_sound(name)
        if snd is not None:
            try:
                snd.play()
                return
            except Exception:
                pass
        self._system_beep()             # 降級

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
