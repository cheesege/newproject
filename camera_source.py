"""
camera_source.py
攝影機來源抽象（CameraSource）— 讓畫面來源可切換，方便把鏡頭架遠拍全身。

三種來源：
  - LocalCamera ：本機鏡頭（預設，cv2.VideoCapture(0)）。
  - StreamCamera：Wi-Fi 串流，手機 IP 攝影機 App（IP Webcam / DroidCam）的
                  HTTP(MJPEG) / RTSP URL。
  - USBCamera   ：USB 有線（DroidCam / iVCam USB 模式），以裝置索引指定。

來源由「啟動參數 > 環境變數 GYM_CAMERA > 設定檔 camera.cfg > 預設本機 0」決定，
切換來源不需改程式碼。連線失敗會印清楚錯誤並自動退回本機鏡頭。

**不採用藍牙**：藍牙頻寬（約 1–3 Mbps）與缺視訊 profile，無法承載即時串流；
請改用 Wi-Fi 或 USB。

spec 字串格式：
  "0" / "1" ...        → 本機鏡頭索引（LocalCamera）
  "usb:1"              → USB 有線裝置索引 1（USBCamera）
  "http://.../video"   → Wi-Fi MJPEG 串流（StreamCamera）
  "rtsp://.../live"    → RTSP 串流（StreamCamera）
"""

import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2

ENV_VAR = "GYM_CAMERA"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera.cfg")


# ══════════════════════════════════════════════════════════════════════════════
# 抽象基底
# ══════════════════════════════════════════════════════════════════════════════

class CameraSource(ABC):
    """
    攝影機來源抽象基底。

    採**背景執行緒抓幀**：相機讀取是阻塞操作（webcam 約 33ms/幀），若與姿態偵測
    串在同一迴圈會讓 FPS 砍半。背景緒持續抓最新幀，主迴圈 read() 立即取得最新畫面，
    使相機讀取與偵測/繪製平行進行，明顯提升 FPS。
    """
    desc = "攝影機"

    def __init__(self, width: int = 1280, height: int = 720, threaded: bool = True):
        self._cap: Optional[cv2.VideoCapture] = None
        self._w, self._h = width, height
        self.width = width
        self.height = height
        self._threaded = threaded
        self._lock = threading.Lock()
        self._latest = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @abstractmethod
    def _make_capture(self) -> cv2.VideoCapture:
        ...

    def open(self) -> bool:
        cap = self._make_capture()
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._h)
        # 降低相機內部緩衝，盡量取得最新幀（部分後端支援）
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or self._w
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self._h
        self._cap = cap
        if self._threaded:
            self._running = True
            self._thread = threading.Thread(target=self._grab_loop, daemon=True)
            self._thread.start()
        return True

    def _grab_loop(self):
        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._latest = frame
            else:
                time.sleep(0.005)

    @property
    def opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Tuple[bool, object]:
        if self._cap is None:
            return False, None
        if self._threaded:
            with self._lock:
                if self._latest is None:
                    return False, None
                return True, self._latest.copy()
        return self._cap.read()

    def release(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None


# ══════════════════════════════════════════════════════════════════════════════
# 具體來源
# ══════════════════════════════════════════════════════════════════════════════

class LocalCamera(CameraSource):
    def __init__(self, index: int = 0, **kw):
        super().__init__(**kw)
        self.index = index
        self.desc = f"本機鏡頭 #{index}"

    def _make_capture(self):
        return cv2.VideoCapture(self.index)


class USBCamera(CameraSource):
    """USB 有線（DroidCam/iVCam USB 模式），實際上也是裝置索引。"""
    def __init__(self, index: int = 1, **kw):
        super().__init__(**kw)
        self.index = index
        self.desc = f"USB 有線裝置 #{index}"

    def _make_capture(self):
        return cv2.VideoCapture(self.index)


class StreamCamera(CameraSource):
    """Wi-Fi 串流（MJPEG / RTSP URL）。"""
    def __init__(self, url: str, **kw):
        super().__init__(**kw)
        self.url = url
        self.desc = f"Wi-Fi 串流 {url}"

    def _make_capture(self):
        return cv2.VideoCapture(self.url)


# ══════════════════════════════════════════════════════════════════════════════
# 來源解析與開啟（含容錯退回）
# ══════════════════════════════════════════════════════════════════════════════

def _read_config() -> Optional[str]:
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        return None
    return None


def resolve_spec(cli_source: Optional[str] = None) -> str:
    """依優先序決定來源字串：啟動參數 > 環境變數 > 設定檔 > 預設 '0'。"""
    if cli_source:
        return cli_source.strip()
    env = os.environ.get(ENV_VAR)
    if env:
        return env.strip()
    cfg = _read_config()
    if cfg:
        return cfg.strip()
    return "0"


def build_source(spec: str, width: int = 1280, height: int = 720) -> CameraSource:
    """把 spec 字串轉成對應的 CameraSource（尚未 open）。"""
    spec = spec.strip()
    low = spec.lower()
    if low.startswith("usb:"):
        idx = int(spec.split(":", 1)[1] or 1)
        return USBCamera(idx, width=width, height=height)
    if low.startswith(("http://", "https://", "rtsp://", "rtmp://")):
        return StreamCamera(spec, width=width, height=height)
    if spec.isdigit():
        return LocalCamera(int(spec), width=width, height=height)
    # 不認得的格式：當作串流網址嘗試
    return StreamCamera(spec, width=width, height=height)


def open_camera(cli_source: Optional[str] = None,
                width: int = 1280, height: int = 720) -> CameraSource:
    """
    解析來源並開啟，回傳 CameraSource（已 open 或已退回本機）。
    指定來源失敗 → 印清楚錯誤並退回本機鏡頭 0；連本機都失敗時 opened 為 False。
    """
    spec = resolve_spec(cli_source)
    source = build_source(spec, width, height)
    print(f"🎥  嘗試開啟攝影機來源：{source.desc}")
    if source.open():
        print(f"✅  攝影機已開啟：{source.desc}（{source.width}x{source.height}）")
        return source

    print(f"⚠  無法開啟「{source.desc}」。")
    if not isinstance(source, LocalCamera) or source.index != 0:
        print("↩  自動退回本機鏡頭 0 ...")
        fallback = LocalCamera(0, width=width, height=height)
        if fallback.open():
            print(f"✅  已使用 {fallback.desc}")
            return fallback
        source = fallback

    print("❌  找不到任何可用攝影機（將以空白畫面執行）。")
    return source
