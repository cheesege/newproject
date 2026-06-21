"""
scenes 套件 — Scene 狀態機的所有場景。

build_scenes(app) 會建立所有場景實例並回傳 {name: Scene} 字典，供 main.py
的狀態機使用。新增場景只要在這裡多註冊一個。
"""

from scenes.base import Scene, SceneName, QUIT
from scenes.user_select import UserSelectScene
from scenes.hub import HubScene
from scenes.pre_game import PreGameScene
from scenes.playing import PlayingScene
from scenes.paused import PausedScene
from scenes.result import ResultScene
from scenes.trends import TrendsScene
from scenes.twin import TwinScene
from scenes.camera_settings import CameraScene


def build_scenes(app):
    return {
        SceneName.USER_SELECT: UserSelectScene(app),
        SceneName.HUB: HubScene(app),
        SceneName.PRE_GAME: PreGameScene(app),
        SceneName.PLAYING: PlayingScene(app),
        SceneName.PAUSED: PausedScene(app),
        SceneName.RESULT: ResultScene(app),
        SceneName.TRENDS: TrendsScene(app),
        SceneName.TWIN: TwinScene(app),
        SceneName.CAMERA: CameraScene(app),
    }


__all__ = ["Scene", "SceneName", "QUIT", "build_scenes"]
