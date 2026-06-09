"""
exercise_counter.py
深蹲 / 伏地挺身 動作計數與姿勢回饋模組

深蹲判斷：膝蓋角度（髖-膝-踝）
  站立  > SQUAT_UP_ANGLE   (160°)
  蹲下  < SQUAT_DOWN_ANGLE (100°)

伏地挺身判斷：手肘角度（肩-肘-腕）
  撐起  > PUSHUP_UP_ANGLE   (155°)
  下壓  < PUSHUP_DOWN_ANGLE  (90°)

體位偵測：比較肩膀 y 與腳踝 y 的差距
  站立：差距大（vertical）
  水平：差距小（horizontal → 伏地挺身模式）
"""

from enum import Enum
from typing import Optional
from mediapipe.tasks.python import vision as mp_vision

from pose_detector import PoseDetector


class ExerciseType(Enum):
    SQUAT = "squat"
    PUSHUP = "pushup"


class ExerciseCounter:
    # ── 深蹲門檻 ──
    SQUAT_DOWN_ANGLE = 110    # 膝蓋角度 < 此值 → 蹲下
    SQUAT_UP_ANGLE   = 160    # 膝蓋角度 > 此值 → 站立

    # ── 伏地挺身門檻 ──
    PUSHUP_DOWN_ANGLE = 90    # 肘部角度 < 此值 → 下壓
    PUSHUP_UP_ANGLE   = 155   # 肘部角度 > 此值 → 撐起

    # ── 體位門檻（髖與踝的 y 差距，正規化） ──
    HORIZONTAL_THRESHOLD = 0.12

    def __init__(self):
        self._mp = mp_vision.PoseLandmark

        self.squat_count: int = 0
        self.pushup_count: int = 0

        self._squat_stage: str = "up"    # "up" | "down"
        self._pushup_stage: str = "up"

        self.current_exercise: ExerciseType = ExerciseType.SQUAT
        self.body_orientation: str = "vertical"  # "vertical" | "horizontal"

        # 即時資料（供 UI 顯示）
        self.knee_angle: Optional[float] = None
        self.elbow_angle: Optional[float] = None
        self.form_feedback: str = "請站在攝影機前並做準備動作"

    # ── 公開 API ──────────────────────────────────────────────────────────────

    def update(self, detector: PoseDetector) -> Optional[ExerciseType]:
        """
        從 PoseDetector 更新動作狀態。
        回傳：完成一次動作的 ExerciseType；尚未完成回傳 None。
        """
        if not detector.is_visible():
            self.form_feedback = "⚠ 未偵測到人物"
            return None

        self._update_orientation(detector)

        if self.body_orientation == "horizontal":
            self.current_exercise = ExerciseType.PUSHUP
            return self._check_pushup(detector)
        else:
            self.current_exercise = ExerciseType.SQUAT
            return self._check_squat(detector)

    def current_angle(self) -> Optional[float]:
        """目前主要動作的關節角度。"""
        return (
            self.knee_angle
            if self.current_exercise == ExerciseType.SQUAT
            else self.elbow_angle
        )

    def reset(self):
        self.squat_count = 0
        self.pushup_count = 0
        self._squat_stage = "up"
        self._pushup_stage = "up"

    # ── 體位偵測 ──────────────────────────────────────────────────────────────

    def _update_orientation(self, detector: PoseDetector):
        L = self._mp
        left_hip    = detector.get_landmark(L.LEFT_HIP.value)
        left_ankle  = detector.get_landmark(L.LEFT_ANKLE.value)
        right_hip   = detector.get_landmark(L.RIGHT_HIP.value)
        right_ankle = detector.get_landmark(L.RIGHT_ANKLE.value)

        if None in (left_hip, left_ankle, right_hip, right_ankle):
            self.body_orientation = "vertical"
            return

        # 左右腳踝平均 y；若與臀部 y 差距小 → 水平
        avg_hip_y   = (left_hip[1]   + right_hip[1])   / 2
        avg_ankle_y = (left_ankle[1] + right_ankle[1]) / 2
        diff = abs(avg_ankle_y - avg_hip_y)

        self.body_orientation = (
            "horizontal" if diff < self.HORIZONTAL_THRESHOLD else "vertical"
        )

    # ── 深蹲偵測 ──────────────────────────────────────────────────────────────

    def _check_squat(self, detector: PoseDetector) -> Optional[ExerciseType]:
        L = self._mp

        left_a  = detector.angle(L.LEFT_HIP.value,  L.LEFT_KNEE.value,  L.LEFT_ANKLE.value)
        right_a = detector.angle(L.RIGHT_HIP.value, L.RIGHT_KNEE.value, L.RIGHT_ANKLE.value)

        angles = [a for a in (left_a, right_a) if a is not None]
        if not angles:
            self.form_feedback = "請讓腿部關節面向攝影機"
            return None

        self.knee_angle = sum(angles) / len(angles)

        if self.knee_angle < self.SQUAT_DOWN_ANGLE:
            if self._squat_stage == "up":
                self._squat_stage = "down"
            self.form_feedback = f"✓ 蹲下姿勢良好！({self.knee_angle:.0f}°)"
        elif self.knee_angle > self.SQUAT_UP_ANGLE:
            if self._squat_stage == "down":
                self._squat_stage = "up"
                self.squat_count += 1
                self.form_feedback = f"深蹲 +1！共 {self.squat_count} 下"
                return ExerciseType.SQUAT
            self.form_feedback = f"站立中 ({self.knee_angle:.0f}°) — 開始蹲下！"
        else:
            status = "▼ 繼續蹲深！" if self._squat_stage == "up" else "▲ 起立！"
            self.form_feedback = f"{status} ({self.knee_angle:.0f}°)"

        return None

    # ── 伏地挺身偵測 ──────────────────────────────────────────────────────────

    def _check_pushup(self, detector: PoseDetector) -> Optional[ExerciseType]:
        L = self._mp

        left_a  = detector.angle(L.LEFT_SHOULDER.value,  L.LEFT_ELBOW.value,  L.LEFT_WRIST.value)
        right_a = detector.angle(L.RIGHT_SHOULDER.value, L.RIGHT_ELBOW.value, L.RIGHT_WRIST.value)

        angles = [a for a in (left_a, right_a) if a is not None]
        if not angles:
            self.form_feedback = "請讓手臂面向攝影機"
            return None

        self.elbow_angle = sum(angles) / len(angles)

        if self.elbow_angle < self.PUSHUP_DOWN_ANGLE:
            if self._pushup_stage == "up":
                self._pushup_stage = "down"
            self.form_feedback = f"✓ 下壓良好！({self.elbow_angle:.0f}°)"
        elif self.elbow_angle > self.PUSHUP_UP_ANGLE:
            if self._pushup_stage == "down":
                self._pushup_stage = "up"
                self.pushup_count += 1
                self.form_feedback = f"伏地挺身 +1！共 {self.pushup_count} 下"
                return ExerciseType.PUSHUP
            self.form_feedback = f"撐起 ({self.elbow_angle:.0f}°) — 下壓！"
        else:
            status = "▼ 繼續壓！" if self._pushup_stage == "up" else "▲ 撐起！"
            self.form_feedback = f"{status} ({self.elbow_angle:.0f}°)"

        return None
