"""
exercises.py
動作系統 — Strategy 模式

每個健身動作是一個獨立的判定器類別（角度／座標定義 + 一上一下狀態機），
對外提供統一介面 `Exercise`。主迴圈與遊戲邏輯只認介面，不認具體動作。

新增動作 = 新增一個 Exercise 子類，不需更動核心。

統一介面
--------
    name          : 顯示名稱，如「深蹲」
    key           : 內部識別字串，如 "squat"（給資料層存檔用）
    met           : 卡路里計算用的 MET 值
    game_action   : 對應攻擊型態，"single"（單體）/ "triple"（齊射）
    orientation   : 適用體位 "vertical" / "horizontal"

    update(detector) -> bool   每幀呼叫，完成一次完整動作時回傳 True
    current_angle()  -> float|None   供 UI 角度量表顯示（無角度概念則回 None）
    form_feedback    : str     姿勢提示／錯誤訊息
    form_alert       : bool    動作已開始但尚未達標（給音效模組做提示判斷）
    engaged          : bool    目前是否處於動作中段（用於協調者挑選顯示對象）
    reset()                    歸零
"""

from abc import ABC, abstractmethod
from typing import Optional

from mediapipe.tasks.python import vision as mp_vision

from pose_detector import PoseDetector

# PoseLandmark 索引（33 點）
L = mp_vision.PoseLandmark


# ══════════════════════════════════════════════════════════════════════════════
# 抽象基底
# ══════════════════════════════════════════════════════════════════════════════

class Exercise(ABC):
    """所有健身動作的共同介面。"""

    name: str = "動作"
    key: str = "exercise"
    met: float = 3.0                 # 卡路里計算用 MET 值
    seconds_per_rep: float = 3.0     # 每次動作估計耗時（秒），供卡路里推算
    game_action: str = "single"     # "single" | "triple"
    orientation: str = "vertical"   # "vertical" | "horizontal"

    def __init__(self):
        self.count: int = 0
        self.stage: str = "up"               # "up" | "down"
        self.angle: Optional[float] = None
        self.form_feedback: str = ""
        self.form_alert: bool = False        # 動作開始但未達標
        self.engaged: bool = False           # 動作中段（蹲到一半／手舉起）

    @abstractmethod
    def update(self, detector: PoseDetector) -> bool:
        """每幀呼叫；完成一次完整動作時回傳 True。"""
        raise NotImplementedError

    def current_angle(self) -> Optional[float]:
        """供 UI 角度量表顯示；無角度概念的動作回傳 None。"""
        return self.angle

    def form_error(self) -> Optional[str]:
        """供音效模組：動作已開始但未達標時回傳提示訊息，否則 None。

        子類可覆寫以提供更明確的錯誤姿勢偵測（進階版）。
        """
        return self.form_feedback if self.form_alert else None

    def reset(self) -> None:
        self.count = 0
        self.stage = "up"
        self.angle = None
        self.form_alert = False
        self.engaged = False


# ══════════════════════════════════════════════════════════════════════════════
# 深蹲
# ══════════════════════════════════════════════════════════════════════════════

class Squat(Exercise):
    """深蹲：膝蓋角度（髖-膝-踝）由 >UP 降到 <DOWN 再回升，記一次。"""

    name = "深蹲"
    key = "squat"
    met = 5.0
    seconds_per_rep = 3.0
    game_action = "single"
    orientation = "vertical"

    DOWN_ANGLE = 110    # 膝蓋角度 < 此值 → 蹲下
    UP_ANGLE = 160      # 膝蓋角度 > 此值 → 站立

    def update(self, detector: PoseDetector) -> bool:
        left_a = detector.angle(L.LEFT_HIP.value, L.LEFT_KNEE.value, L.LEFT_ANKLE.value)
        right_a = detector.angle(L.RIGHT_HIP.value, L.RIGHT_KNEE.value, L.RIGHT_ANKLE.value)

        angles = [a for a in (left_a, right_a) if a is not None]
        if not angles:
            self.form_feedback = "請讓腿部關節面向攝影機"
            self.form_alert = False
            self.engaged = False
            return False

        self.angle = sum(angles) / len(angles)
        self.form_alert = False
        self.engaged = self.stage == "down"

        completed = False
        if self.angle < self.DOWN_ANGLE:
            if self.stage == "up":
                self.stage = "down"
            self.engaged = True
            self.form_feedback = f"✓ 蹲下姿勢良好！({self.angle:.0f}°)"
        elif self.angle > self.UP_ANGLE:
            if self.stage == "down":
                self.stage = "up"
                self.count += 1
                self.form_feedback = f"深蹲 +1！共 {self.count} 下"
                completed = True
            else:
                self.form_feedback = f"站立中 ({self.angle:.0f}°) — 開始蹲下！"
        else:
            if self.stage == "up":
                self.form_feedback = f"▼ 繼續蹲深！({self.angle:.0f}°)"
                self.form_alert = True       # 下蹲但深度不足
                self.engaged = True
            else:
                self.form_feedback = f"▲ 起立！({self.angle:.0f}°)"
                self.engaged = True

        return completed


# ══════════════════════════════════════════════════════════════════════════════
# 伏地挺身
# ══════════════════════════════════════════════════════════════════════════════

class Pushup(Exercise):
    """伏地挺身：肘部角度（肩-肘-腕）由 >UP 降到 <DOWN 再回升，記一次。"""

    name = "伏地挺身"
    key = "pushup"
    met = 3.8
    seconds_per_rep = 3.0
    game_action = "triple"
    orientation = "horizontal"

    DOWN_ANGLE = 90     # 肘部角度 < 此值 → 下壓
    UP_ANGLE = 155      # 肘部角度 > 此值 → 撐起

    def update(self, detector: PoseDetector) -> bool:
        left_a = detector.angle(L.LEFT_SHOULDER.value, L.LEFT_ELBOW.value, L.LEFT_WRIST.value)
        right_a = detector.angle(L.RIGHT_SHOULDER.value, L.RIGHT_ELBOW.value, L.RIGHT_WRIST.value)

        angles = [a for a in (left_a, right_a) if a is not None]
        if not angles:
            self.form_feedback = "請讓手臂面向攝影機"
            self.form_alert = False
            self.engaged = False
            return False

        self.angle = sum(angles) / len(angles)
        self.form_alert = False
        self.engaged = self.stage == "down"

        completed = False
        if self.angle < self.DOWN_ANGLE:
            if self.stage == "up":
                self.stage = "down"
            self.engaged = True
            self.form_feedback = f"✓ 下壓良好！({self.angle:.0f}°)"
        elif self.angle > self.UP_ANGLE:
            if self.stage == "down":
                self.stage = "up"
                self.count += 1
                self.form_feedback = f"伏地挺身 +1！共 {self.count} 下"
                completed = True
            else:
                self.form_feedback = f"撐起 ({self.angle:.0f}°) — 下壓！"
        else:
            if self.stage == "up":
                self.form_feedback = f"▼ 繼續壓！({self.angle:.0f}°)"
                self.form_alert = True       # 下壓但深度不足
                self.engaged = True
            else:
                self.form_feedback = f"▲ 撐起！({self.angle:.0f}°)"
                self.engaged = True

        return completed


# ══════════════════════════════════════════════════════════════════════════════
# 舉手（開發測試動作）
# ══════════════════════════════════════════════════════════════════════════════

class RaiseHand(Exercise):
    """
    舉手 — 開發測試動作。

    **用途**：此為開發測試動作，坐姿即可觸發，方便快速驗證遊戲循環與後續功能，
    避免每次測試都要真的做深蹲。

    判定：比較手腕（左 15 / 右 16）與肩膀（左 11 / 右 12）的 y 座標。
      手腕明顯高於肩膀 → up；放下 → down。一上一下記一次。
      沿用「兩段狀態機防誤計」與「左右取平均」做法，不需 MediaPipe Hands。
    """

    name = "舉手(測試)"
    key = "raise_hand"
    met = 2.0
    seconds_per_rep = 2.0
    game_action = "single"
    orientation = "vertical"

    # 正規化 y 差值門檻（y 越小越高）。負值代表手腕在肩膀之上。
    UP_MARGIN = -0.03     # (腕y - 肩y) < 此值 → 手舉起
    DOWN_MARGIN = 0.05    # (腕y - 肩y) > 此值 → 手放下

    def __init__(self):
        super().__init__()
        self.stage = "down"   # 從「手放下」開始

    def _side_diff(self, detector: PoseDetector, wrist_id: int, shoulder_id: int):
        wrist = detector.get_landmark(wrist_id)
        shoulder = detector.get_landmark(shoulder_id)
        if wrist is None or shoulder is None:
            return None
        return wrist[1] - shoulder[1]   # 腕y - 肩y

    def update(self, detector: PoseDetector) -> bool:
        diffs = [
            d for d in (
                self._side_diff(detector, L.LEFT_WRIST.value, L.LEFT_SHOULDER.value),
                self._side_diff(detector, L.RIGHT_WRIST.value, L.RIGHT_SHOULDER.value),
            ) if d is not None
        ]
        if not diffs:
            self.form_feedback = "請讓手臂與肩膀進入畫面"
            self.engaged = False
            return False

        diff = sum(diffs) / len(diffs)
        self.angle = None       # 舉手無關節角度，不顯示角度量表
        self.engaged = self.stage == "up"

        completed = False
        if diff < self.UP_MARGIN:
            if self.stage == "down":
                self.stage = "up"
            self.engaged = True
            self.form_feedback = "手已舉起 — 放下記一次！"
        elif diff > self.DOWN_MARGIN:
            if self.stage == "up":
                self.stage = "down"
                self.count += 1
                self.form_feedback = f"舉手 +1！共 {self.count} 下（測試動作）"
                completed = True
            else:
                self.form_feedback = "舉手測試：把手舉高過肩膀"
        else:
            self.form_feedback = "舉手測試：再高一點過肩"
            self.engaged = True

        return completed


# ══════════════════════════════════════════════════════════════════════════════
# 動作登錄表（供卡路里 / 趨勢圖以 key 反查 MET、名稱等中繼資料）
# ══════════════════════════════════════════════════════════════════════════════

ALL_EXERCISES = [Squat, Pushup, RaiseHand]
_REGISTRY = {cls.key: cls for cls in ALL_EXERCISES}


def get_meta(key: str):
    """以 key 取得動作類別（含 met / seconds_per_rep / name 等類別屬性）。"""
    return _REGISTRY.get(key)

