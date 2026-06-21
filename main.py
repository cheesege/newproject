#!/usr/bin/env python3
"""
體感硬核健身房 — 以使用者養成為核心的體感健身遊戲
==================================================
用真實動作（深蹲／伏地挺身／舉手測試）打怪，所有訓練成果累積到「你的角色」身上，
化為一個會成長、會預測未來的數位分身。

動線：選擇/創建使用者 → 主頁 → 訓練前設定 → 訓練 → 結算（看分身成長）→ 回主頁。

本檔精簡為「初始化 + Scene 狀態機主迴圈」，各畫面邏輯在 scenes/ 套件中。

使用方式
--------
  pip install -r requirements.txt
  python main.py                                   # 本機鏡頭
  python main.py --source http://手機IP:8080/video  # 手機串流
"""

import argparse
import sys
import time

import cv2
import numpy as np

import storage
from camera_source import open_camera
from exercise_counter import ExerciseCounter
from game_objects import MonsterMode
from pose_detector import PoseDetector
from sounds import SoundManager
from value_input import KeyboardValueReader
from scenes import build_scenes, SceneName, QUIT


WIN = "體感健身房 — Fitness Battle"


class GameApp:
    """持有共用資源，跑 Scene 狀態機主迴圈。各 Scene 透過 self.app 取用這些資源。"""

    def __init__(self, cli_source=None):
        # ── 攝影機來源（失敗不致命：以空畫面讓選單仍可操作） ──
        self.camera = open_camera(cli_source, width=1280, height=720)
        if self.camera.opened:
            self.W, self.H = self.camera.width, self.camera.height
        else:
            print("⚠  無攝影機可用，仍可瀏覽選單；訓練畫面將為空白。")
            self.W, self.H = 1280, 720

        # ── 視窗 ──
        self.win = WIN
        cv2.namedWindow(self.win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.win, self.W, self.H)

        # ── 基礎設施 / 領域物件（共用） ──
        print("🦾  載入姿態偵測模型...")
        self.detector = PoseDetector(min_detection_confidence=0.6, min_tracking_confidence=0.5)
        self.counter = ExerciseCounter()
        self.sound_mgr = SoundManager()
        self.value_reader = KeyboardValueReader(self.camera, self.win, (self.W, self.H))

        # ── 跨場景共用狀態 ──
        self.current_user = None            # 目前選定的使用者（storage.User）
        self.selected_mode = MonsterMode.MIXED
        self.selected_exercises = ["squat"]   # 本場選定的動作（每輪一個，PRE_GAME 可改）
        self.game = None                    # 目前的 GameState（PLAYING 建立）
        self.game_start_iso = None
        self.last_result = None             # 給 RESULT 顯示的本場結果 dict

        # ── 狀態機 ──
        self.scenes = build_scenes(self)
        self.current = None
        self.running = True

    # ── 影像 ──
    def read_frame(self):
        """取得一張鏡像後的攝影機畫面；無攝影機則回傳深色空白畫面。

        不論來源解析度為何，都統一縮放成 (W, H)，讓版面與遊戲邏輯一致——
        這也讓「執行中切換到不同解析度的手機串流」不會破壞畫面。
        """
        if self.camera is not None and self.camera.opened:
            ret, frame = self.camera.read()
            if ret:
                if frame.shape[1] != self.W or frame.shape[0] != self.H:
                    frame = cv2.resize(frame, (self.W, self.H))
                return cv2.flip(frame, 1)
        return np.full((self.H, self.W, 3), (16, 20, 32), dtype=np.uint8)

    def set_camera(self, new_cam) -> bool:
        """執行中切換攝影機來源。new_cam 需已成功 open。回傳是否切換成功。"""
        if new_cam is None or not new_cam.opened:
            return False
        old = self.camera
        self.camera = new_cam
        self.value_reader._cap = new_cam      # 讓輸入畫面背景也用新來源
        self.source = getattr(new_cam, "desc", "?")
        if old is not None and old is not new_cam:
            old.release()
        return True

    # ── 場景切換 ──
    def switch(self, name, **kwargs):
        if self.current is not None:
            self.current.on_exit()
        self.current = self.scenes[name]
        self.current.next_scene = None
        self.current.on_enter(**kwargs)

    def run(self, start_scene=SceneName.USER_SELECT):
        self.switch(start_scene)
        prev = time.time()
        print("\n🎮  遊戲就緒！")
        while self.running:
            now = time.time()
            dt = max(now - prev, 1e-4)
            prev = now

            frame = self.read_frame()
            scene = self.current
            scene.update(dt, frame)
            scene.draw(frame)
            cv2.imshow(self.win, frame)

            key = cv2.waitKey(1) & 0xFF
            if key != 255:
                scene.handle_input(key)

            if scene.next_scene is not None:
                name, kwargs = scene.next_scene
                scene.next_scene = None
                if name == QUIT:
                    self.running = False
                else:
                    self.switch(name, **kwargs)

        self.cleanup()

    def cleanup(self):
        self.camera.release()
        cv2.destroyAllWindows()
        print("\n🎮  再見！")


def main():
    parser = argparse.ArgumentParser(description="體感硬核健身房")
    parser.add_argument("--source", "-s", default=None,
                        help="攝影機來源：本機索引(如 0) 或手機串流 URL；"
                             "也可用環境變數 GYM_CAMERA 或 camera.cfg 指定。")
    args = parser.parse_args()

    app = GameApp(cli_source=args.source)
    app.run()


if __name__ == "__main__":
    main()
