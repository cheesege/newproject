"""
exercise_counter.py
動作協調者（Coordinator）

持有一組 Exercise（Strategy，定義於 exercises.py），依「體位自動偵測」決定當下
要判定哪些動作。**本場啟用哪些動作可在訓練前選擇**（set_enabled），計數器不再
寫死深蹲／伏地挺身。

對外維持與舊版相容的介面（squat_count / pushup_count / form_feedback /
current_exercise / current_angle() / reset()），降低呼叫端改動。
"""

from enum import Enum
from typing import Dict, List, Optional

from mediapipe.tasks.python import vision as mp_vision

from pose_detector import PoseDetector
from exercises import Exercise, Squat, Pushup, RaiseHand


class ExerciseType(Enum):
    """保留給 UI（角度量表配色）使用的動作種類。"""
    SQUAT = "squat"
    PUSHUP = "pushup"
    RAISE_HAND = "raise_hand"


_KEY_TO_TYPE = {
    "squat": ExerciseType.SQUAT,
    "pushup": ExerciseType.PUSHUP,
    "raise_hand": ExerciseType.RAISE_HAND,
}


class ExerciseCounter:
    HORIZONTAL_THRESHOLD = 0.12      # 體位門檻（髖與踝 y 差距，正規化）

    def __init__(self, enabled_keys: Optional[List[str]] = None):
        self._mp = mp_vision.PoseLandmark

        # 所有可用動作的實例（計數跨回合保存在這裡，由 reset() 歸零）
        self._all: List[Exercise] = [Squat(), Pushup(), RaiseHand()]
        self._all_by_key: Dict[str, Exercise] = {ex.key: ex for ex in self._all}

        self.body_orientation: str = "vertical"
        self.set_enabled(enabled_keys)
        self.form_feedback: str = "請站在攝影機前並做準備動作"

    # ── 本場啟用的動作 ────────────────────────────────────────────────────────

    def set_enabled(self, enabled_keys: Optional[List[str]] = None):
        """設定本場要判定的動作（key 清單）；None 或空 → 啟用全部。"""
        chosen = [self._all_by_key[k] for k in (enabled_keys or []) if k in self._all_by_key]
        self.exercises: List[Exercise] = chosen or list(self._all)
        self._by_key: Dict[str, Exercise] = {ex.key: ex for ex in self.exercises}
        self._display: Exercise = self.exercises[0]

    @property
    def enabled_keys(self) -> List[str]:
        return [ex.key for ex in self.exercises]

    # ── 公開 API（與舊版相容） ──────────────────────────────────────────────

    def update(self, detector: PoseDetector) -> Optional[Exercise]:
        """回傳完成一次動作的 Exercise；尚未完成回傳 None。"""
        if not detector.is_visible():
            self.form_feedback = "⚠ 未偵測到人物"
            return None

        self._update_orientation(detector)

        active = [ex for ex in self.exercises if ex.orientation == self.body_orientation]
        if not active:
            # 本場沒有符合當前體位的動作：提示玩家切換姿勢
            need = "站立" if any(e.orientation == "vertical" for e in self.exercises) else "趴下"
            self.form_feedback = f"請以「{need}」姿勢進行本場選定的動作"
            return None

        completed: Optional[Exercise] = None
        for ex in active:
            if ex.update(detector) and completed is None:
                completed = ex

        self._display = (
            completed
            or next((ex for ex in active if ex.engaged), None)
            or active[0]
        )
        self.form_feedback = self._display.form_feedback
        return completed

    def current_angle(self) -> Optional[float]:
        return self._display.current_angle()

    @property
    def current_exercise(self) -> ExerciseType:
        return _KEY_TO_TYPE.get(self._display.key, ExerciseType.SQUAT)

    @property
    def form_alert(self) -> bool:
        return self._display.form_alert

    def form_error(self) -> Optional[str]:
        """目前顯示動作的姿勢錯誤訊息（未達標時有值），供音效模組。"""
        return self._display.form_error()

    @property
    def display_exercise(self) -> Exercise:
        return self._display

    def reset(self):
        for ex in self._all:
            ex.reset()
        self._display = self.exercises[0]
        self.form_feedback = "請站在攝影機前並做準備動作"

    # ── 給資料層 / 卡路里使用 ────────────────────────────────────────────────

    def reps(self) -> Dict[str, int]:
        """回傳本場啟用動作的次數，如 {"squat":12, "pushup":8}。"""
        return {ex.key: ex.count for ex in self.exercises}

    def get(self, key: str) -> Optional[Exercise]:
        return self._all_by_key.get(key)

    # ── 相容舊版屬性 ─────────────────────────────────────────────────────────

    @property
    def squat_count(self) -> int:
        return self._all_by_key["squat"].count

    @property
    def pushup_count(self) -> int:
        return self._all_by_key["pushup"].count

    # ── 體位偵測 ──────────────────────────────────────────────────────────────

    def _update_orientation(self, detector: PoseDetector):
        L = self._mp
        left_hip = detector.get_landmark(L.LEFT_HIP.value)
        left_ankle = detector.get_landmark(L.LEFT_ANKLE.value)
        right_hip = detector.get_landmark(L.RIGHT_HIP.value)
        right_ankle = detector.get_landmark(L.RIGHT_ANKLE.value)

        if None in (left_hip, left_ankle, right_hip, right_ankle):
            self.body_orientation = "vertical"
            return

        avg_hip_y = (left_hip[1] + right_hip[1]) / 2
        avg_ankle_y = (left_ankle[1] + right_ankle[1]) / 2
        diff = abs(avg_ankle_y - avg_hip_y)
        self.body_orientation = "horizontal" if diff < self.HORIZONTAL_THRESHOLD else "vertical"
