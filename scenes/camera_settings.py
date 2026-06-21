"""scenes/camera_settings.py — 攝影機設定（程式內連線手機鏡頭）。

不必再用命令列參數：在此畫面即可切換本機鏡頭 / 連線手機 Wi-Fi 串流 / USB 有線，
即時生效。連線失敗會保留原本來源並顯示錯誤。
"""

from camera_source import LocalCamera, StreamCamera, USBCamera
from scenes.base import Scene, SceneName, fill_bg
from text_utils import put_text, put_text_centered


class CameraScene(Scene):
    def on_enter(self, back=SceneName.HUB, **kwargs):
        self._back = back
        cur = getattr(self.app.camera, "desc", "（無）") if self.app.camera else "（無）"
        ok = self.app.camera is not None and self.app.camera.opened
        self._msg = f"目前來源：{cur}　狀態：{'已連線' if ok else '未連線'}"

    def _try(self, source):
        """嘗試開啟並切換到新來源；失敗則保留原本來源。"""
        print(f"🎥  嘗試連線：{source.desc} ...")
        if source.open() and self.app.set_camera(source):
            self._msg = f"已連線：{source.desc}"
            print(f"✅  {self._msg}")
        else:
            source.release()
            self._msg = f"連線失敗：{source.desc}（維持原來來源）"
            print(f"⚠  {self._msg}")

    def handle_input(self, key):
        W, H = self.app.W, self.app.H
        if key == ord('1'):
            self._try(LocalCamera(0, width=W, height=H))
        elif key == ord('2'):
            url = self.app.value_reader.read_text(
                "輸入手機串流網址 例 http://192.168.0.10:8080/video", max_len=64)
            if url:
                self._try(StreamCamera(url, width=W, height=H))
        elif key == ord('3'):
            url = self.app.value_reader.read_text("USB 裝置索引（數字，例 1）", max_len=3)
            if url and url.isdigit():
                self._try(USBCamera(int(url), width=W, height=H))
        elif key in (13, 10, 27, ord('h')):
            self.go(self._back)

    def draw(self, frame):
        h, w = frame.shape[:2]
        fill_bg(frame)
        put_text_centered(frame, "攝影機設定", w // 2, 60, size=48,
                          color=(255, 220, 100), bold=True)
        put_text_centered(frame, "把鏡頭架遠才能拍到全身（做伏地挺身必要）",
                          w // 2, 112, size=22, color=(190, 210, 240))

        x = w // 2 - 360
        opts = [
            ("1", "使用本機鏡頭", "電腦內建 / USB webcam"),
            ("2", "連線手機 Wi-Fi 串流", "手機裝 IP Webcam / DroidCam，與電腦同一 Wi-Fi"),
            ("3", "USB 有線攝影機", "DroidCam / iVCam USB 模式，輸入裝置索引"),
        ]
        for i, (k, name, desc) in enumerate(opts):
            y = 180 + i * 84
            put_text(frame, f"{k}.  {name}", (x, y), size=30, color=(150, 235, 180), bold=True)
            put_text(frame, desc, (x + 40, y + 40), size=21, color=(195, 205, 225))

        # 狀態列
        put_text_centered(frame, self._msg, w // 2, h - 96, size=24, color=(255, 230, 150))
        put_text_centered(frame,
                          "手機 App（IP Webcam）串流網址通常為 http://手機IP:8080/video",
                          w // 2, h - 60, size=20, color=(180, 195, 220))
        put_text_centered(frame, "1 / 2 / 3 選擇 ｜ ENTER / ESC 返回",
                          w // 2, h - 28, size=22, color=(190, 210, 240))
