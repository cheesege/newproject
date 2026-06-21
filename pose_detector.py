"""
pose_detector.py  — MediaPipe Tasks API 版（相容 0.10.35+）
公開介面與舊版完全相同，exercise_counter.py / main.py 無需修改。

首次執行時會自動下載 pose_landmarker_full.task（約 6 MB）。
"""

import os
import time
import urllib.request
from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python import BaseOptions

# ── 模型下載 ──────────────────────────────────────────────────────────────────

# 採用 lite 模型：CPU 推論明顯比 full 快，對深蹲／伏地挺身的角度判定已足夠，
# 大幅提升遊戲 FPS（full 模型的推論本身就是 FPS 瓶頸，且其內部會把輸入縮到固定大小，
# 故只縮小輸入畫面助益有限，換較輕的模型才是關鍵）。
_MODEL_FILENAME = "pose_landmarker_lite.task"
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _MODEL_FILENAME)
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)


def _ensure_model():
    """如果模型檔不存在則自動下載。"""
    if os.path.exists(_MODEL_PATH):
        return
    print(f"⬇  首次執行：下載姿態偵測模型 ({_MODEL_FILENAME}) ...")
    try:
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print(f"✅  模型已儲存至 {_MODEL_PATH}")
    except Exception as e:
        raise RuntimeError(
            f"模型下載失敗：{e}\n"
            f"請手動下載並放到同目錄：\n{_MODEL_URL}"
        ) from e


# ── 骨架繪製顏色 ───────────────────────────────────────────────────────────────

_LANDMARK_COLOR = (0, 255, 0)       # 綠色關節點
_CONNECTION_COLOR = (255, 255, 255) # 白色連線
_LANDMARK_R = 4
_CONNECTION_THICKNESS = 2

# ══════════════════════════════════════════════════════════════════════════════
# PoseDetector（與舊版同介面）
# ══════════════════════════════════════════════════════════════════════════════

class PoseDetector:
    """
    封裝 MediaPipe Tasks PoseLandmarker。

    提供：
      process(frame)            → 偵測一幀
      is_visible()              → 是否偵測到人物
      draw_landmarks(frame)     → 繪製骨架
      get_landmark(id)          → (x, y, z) 正規化座標
      get_pixel(id, shape)      → (px, py) 像素座標
      body_center_pixel(shape)  → 臀部中心像素座標
      angle(a, b, c)            → 以 b 為頂點的夾角（度）
      Landmark                  → PoseLandmark enum（同舊版）
    """

    # 姿態偵測用的輸入寬度上限。畫面以原解析度顯示，但送進 MediaPipe 前先縮小，
    # 大幅降低 CPU 負擔、提升 FPS；landmark 為正規化座標(0~1)，縮放不影響對應。
    DETECT_WIDTH = 640

    def __init__(
        self,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float  = 0.5,
        model_complexity: int = 1,          # 保留參數，不使用（相容舊版呼叫）
    ):
        _ensure_model()

        opts = mp_vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self._landmarker = mp_vision.PoseLandmarker.create_from_options(opts)
        self._connections = list(mp_vision.PoseLandmarksConnections.POSE_LANDMARKS)

        self._result: Optional[mp_vision.PoseLandmarkerResult] = None
        self._landmarks = None      # list[NormalizedLandmark] | None
        self._ts_ms: int = 0        # 遞增時間戳（VIDEO mode 必須遞增）

    # ── 基本偵測 ──────────────────────────────────────────────────────────────

    def process(self, frame: np.ndarray) -> object:
        """處理一幀 BGR 影像，內部更新骨架狀態。"""
        # 偵測前先縮小到 DETECT_WIDTH（保持長寬比），加速 MediaPipe 推論。
        h, w = frame.shape[:2]
        if w > self.DETECT_WIDTH:
            scale = self.DETECT_WIDTH / w
            small = cv2.resize(frame, (self.DETECT_WIDTH, int(h * scale)),
                               interpolation=cv2.INTER_AREA)
        else:
            small = frame
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # VIDEO mode 要求時間戳嚴格遞增（單位：毫秒）
        self._ts_ms += 1
        self._result = self._landmarker.detect_for_video(mp_img, self._ts_ms)

        if self._result.pose_landmarks:
            self._landmarks = self._result.pose_landmarks[0]
        else:
            self._landmarks = None

        return self._result

    def is_visible(self) -> bool:
        """是否偵測到人物骨架。"""
        return self._landmarks is not None

    # ── 繪製 ──────────────────────────────────────────────────────────────────

    def draw_landmarks(self, frame: np.ndarray) -> np.ndarray:
        """在 frame 上繪製骨架連線與關節點（直接用 OpenCV 繪製）。"""
        if not self.is_visible():
            return frame

        h, w = frame.shape[:2]
        lms  = self._landmarks

        # 連線
        for conn in self._connections:
            p1 = lms[conn.start]
            p2 = lms[conn.end]
            if p1.visibility < 0.4 or p2.visibility < 0.4:
                continue
            x1, y1 = int(p1.x * w), int(p1.y * h)
            x2, y2 = int(p2.x * w), int(p2.y * h)
            cv2.line(frame, (x1, y1), (x2, y2), _CONNECTION_COLOR, _CONNECTION_THICKNESS, cv2.LINE_AA)

        # 關節點
        for lm in lms:
            if lm.visibility < 0.4:
                continue
            px, py = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (px, py), _LANDMARK_R, _LANDMARK_COLOR, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), _LANDMARK_R, (0, 0, 0), 1, cv2.LINE_AA)

        return frame

    # ── 座標存取 ──────────────────────────────────────────────────────────────

    def get_landmark(self, landmark_id: int) -> Optional[Tuple[float, float, float]]:
        """回傳正規化座標 (x, y, z)，偵測失敗回傳 None。"""
        if self._landmarks is None:
            return None
        lm = self._landmarks[landmark_id]
        if lm.visibility < 0.35:
            return None
        return (lm.x, lm.y, lm.z)

    def get_pixel(
        self, landmark_id: int, frame_shape: Tuple
    ) -> Optional[Tuple[int, int]]:
        """回傳像素座標 (px, py)，偵測失敗回傳 None。"""
        coord = self.get_landmark(landmark_id)
        if coord is None:
            return None
        h, w = frame_shape[:2]
        return (int(coord[0] * w), int(coord[1] * h))

    def body_center_pixel(
        self, frame_shape: Tuple
    ) -> Optional[Tuple[int, int]]:
        """回傳身體中心（左右臀平均）的像素座標。"""
        L = mp_vision.PoseLandmark
        lh = self.get_pixel(int(L.LEFT_HIP),  frame_shape)
        rh = self.get_pixel(int(L.RIGHT_HIP), frame_shape)
        if lh is None or rh is None:
            return None
        return ((lh[0] + rh[0]) // 2, (lh[1] + rh[1]) // 2)

    # ── 角度計算 ──────────────────────────────────────────────────────────────

    def angle(
        self, id_a: int, id_b: int, id_c: int
    ) -> Optional[float]:
        """計算以 id_b 為頂點，a-b-c 三點夾角（度）。"""
        a = self.get_landmark(id_a)
        b = self.get_landmark(id_b)
        c = self.get_landmark(id_c)
        if None in (a, b, c):
            return None
        return self._angle_deg(
            np.array(a[:2]), np.array(b[:2]), np.array(c[:2])
        )

    @staticmethod
    def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        ba, bc = a - b, c - b
        cos_v  = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return float(np.degrees(np.arccos(np.clip(cos_v, -1.0, 1.0))))

    # ── 相容舊版的屬性 ────────────────────────────────────────────────────────

    @property
    def Landmark(self):
        """回傳 PoseLandmark enum（和舊版 mp.solutions.pose.PoseLandmark 同值）。"""
        return mp_vision.PoseLandmark

    @property
    def results(self):
        """向後相容：回傳最新偵測結果。"""
        return self._result
