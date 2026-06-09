"""
game_objects.py
遊戲物件：怪物 / 雷射 / 爆炸 / 遊戲狀態管理
"""

import cv2
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from text_utils import put_text, put_text_centered, text_size

import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# 怪物類型
# ══════════════════════════════════════════════════════════════════════════════

class MonsterType(Enum):
    ZOMBIE   = "zombie"
    SKELETON = "skeleton"
    BAT      = "bat"


class MonsterMode(Enum):
    ZOMBIE   = "zombie"
    SKELETON = "skeleton"
    BAT      = "bat"
    MIXED    = "mixed"


# ══════════════════════════════════════════════════════════════════════════════
# 怪物
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Monster:
    x: float
    y: float
    hp: int
    max_hp: int
    speed: float
    mtype: MonsterType
    size: int   = 38
    alive: bool = True
    flash: int  = 0      # 受擊白閃幀數
    wobble: int = 0      # 動畫計數

    # ── 更新 ─────────────────────────────────────────────────────────────────

    def update(self, tx: float, ty: float):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.x += dx / dist * self.speed
            self.y += dy / dist * self.speed
        if self.flash > 0:
            self.flash -= 1
        self.wobble += 1

    # ── 繪製 ─────────────────────────────────────────────────────────────────

    def draw(self, frame: np.ndarray):
        if not self.alive:
            return
        x, y, s = int(self.x), int(self.y), self.size
        wobble_y = int(math.sin(self.wobble * 0.15) * 3)  # 上下浮動

        if self.flash > 0:
            body_color = (255, 255, 255)
            eye_color  = (255, 100, 100)
        else:
            body_color, eye_color = self._colors()

        if self.mtype == MonsterType.ZOMBIE:
            self._draw_zombie(frame, x, y + wobble_y, s, body_color, eye_color)
        elif self.mtype == MonsterType.SKELETON:
            self._draw_skeleton(frame, x, y + wobble_y, s, body_color, eye_color)
        else:
            self._draw_bat(frame, x, y + wobble_y, s, body_color, eye_color)

        self._draw_hp_bar(frame, x, y + wobble_y, s)

    def _colors(self) -> Tuple:
        return {
            MonsterType.ZOMBIE:   ((30, 160, 30),   (255, 50, 50)),
            MonsterType.SKELETON: ((200, 200, 220),  (255, 100, 50)),
            MonsterType.BAT:      ((160, 30, 180),   (255, 50, 200)),
        }[self.mtype]

    def _draw_zombie(self, frame, x, y, s, c, ec):
        # 身體
        cv2.rectangle(frame, (x - s//3, y - s//2), (x + s//3, y + s//2), c, -1)
        cv2.rectangle(frame, (x - s//3, y - s//2), (x + s//3, y + s//2), (0,0,0), 1)
        # 頭
        cv2.circle(frame, (x, y - s//2 - s//4), s//4, c, -1)
        cv2.circle(frame, (x, y - s//2 - s//4), s//4, (0,0,0), 1)
        # 伸直的雙手
        cv2.line(frame, (x - s//3, y - s//5), (x - s*3//4, y - s//5), c, 5)
        cv2.line(frame, (x + s//3, y - s//5), (x + s*3//4, y - s//5), c, 5)
        # X 形眼睛
        for ox in [-s//7, s//7]:
            ex = x + ox
            ey = y - s//2 - s//4
            cv2.line(frame, (ex-4, ey-4), (ex+4, ey+4), ec, 2)
            cv2.line(frame, (ex+4, ey-4), (ex-4, ey+4), ec, 2)

    def _draw_skeleton(self, frame, x, y, s, c, ec):
        # 頭
        cv2.circle(frame, (x, y - s//2), s//5, c, 2)
        # 脊椎
        cv2.line(frame, (x, y - s//3), (x, y + s//3), c, 3)
        # 肋骨
        for i in range(2):
            ry = y - s//6 + i * (s//5)
            cv2.ellipse(frame, (x, ry), (s//3, s//9), 0, 0, 180, c, 2)
        # 手臂
        cv2.line(frame, (x, y - s//5), (x - s//2, y + s//8), c, 3)
        cv2.line(frame, (x, y - s//5), (x + s//2, y + s//8), c, 3)
        # 腿
        cv2.line(frame, (x, y + s//3), (x - s//3, y + s*3//4), c, 3)
        cv2.line(frame, (x, y + s//3), (x + s//3, y + s*3//4), c, 3)
        # 眼睛（空洞）
        cv2.circle(frame, (x - s//8, y - s//2 - s//20), 3, ec, -1)
        cv2.circle(frame, (x + s//8, y - s//2 - s//20), 3, ec, -1)

    def _draw_bat(self, frame, x, y, s, c, ec):
        # 翅膀
        wing_pts = np.array([
            [x,      y],
            [x - s,  y - s//3],
            [x - s//2, y + s//4],
            [x + s//2, y + s//4],
            [x + s,  y - s//3],
        ], np.int32)
        cv2.fillPoly(frame, [wing_pts], c)
        # 身體
        cv2.ellipse(frame, (x, y), (s//4, s//3), 0, 0, 360, c, -1)
        # 耳朵
        cv2.fillPoly(frame, [np.array([[x-s//5, y-s//3],[x-s//3, y-s*2//3],[x, y-s//3]], np.int32)], c)
        cv2.fillPoly(frame, [np.array([[x+s//5, y-s//3],[x+s//3, y-s*2//3],[x, y-s//3]], np.int32)], c)
        # 眼睛
        cv2.circle(frame, (x - s//7, y - s//10), 4, ec, -1)
        cv2.circle(frame, (x + s//7, y - s//10), 4, ec, -1)

    def _draw_hp_bar(self, frame, x, y, s):
        bw = s + 10
        bx, by = x - bw//2, y - s - 16
        cv2.rectangle(frame, (bx, by), (bx + bw, by + 7), (40, 40, 40), -1)
        ratio = self.hp / self.max_hp
        hp_color = (0, 220, 0) if ratio > 0.5 else (0, 165, 255) if ratio > 0.25 else (0, 0, 255)
        cv2.rectangle(frame, (bx, by), (bx + int(bw * ratio), by + 7), hp_color, -1)

    # ── 工具 ─────────────────────────────────────────────────────────────────

    def dist_to(self, px: float, py: float) -> float:
        return math.hypot(self.x - px, self.y - py)

    def reached(self, px: float, py: float, threshold: float = 65) -> bool:
        return self.dist_to(px, py) < threshold


# ══════════════════════════════════════════════════════════════════════════════
# 雷射
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Laser:
    sx: float; sy: float   # 起點（玩家位置）
    ex: float; ey: float   # 終點（怪物位置）
    lifetime: int = 14
    color: Tuple = (0, 220, 255)

    def update(self):
        self.lifetime -= 1

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    def draw(self, frame: np.ndarray):
        if not self.alive:
            return
        alpha  = self.lifetime / 14.0
        thick  = max(1, int(4 * alpha))
        sx, sy = int(self.sx), int(self.sy)
        ex, ey = int(self.ex), int(self.ey)

        # 外層光暈
        cv2.line(frame, (sx, sy), (ex, ey), self.color, thick * 3, cv2.LINE_AA)
        # 核心白光
        cv2.line(frame, (sx, sy), (ex, ey), (255, 255, 255), thick, cv2.LINE_AA)
        # 命中閃光
        if self.lifetime > 8:
            cv2.circle(frame, (ex, ey), 14, (255, 200, 50), -1)
            cv2.circle(frame, (ex, ey),  7, (255, 255, 255), -1)


# ══════════════════════════════════════════════════════════════════════════════
# 爆炸
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Explosion:
    x: float
    y: float
    lifetime: int = 22
    _max: int = field(default=22, init=False, repr=False)

    def __post_init__(self):
        self._max = self.lifetime

    def update(self):
        self.lifetime -= 1

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    def draw(self, frame: np.ndarray):
        if not self.alive:
            return
        ratio  = self.lifetime / self._max
        cx, cy = int(self.x), int(self.y)
        radius = int((1 - ratio) * 55) + 4

        rings = [(255, 80, 0), (255, 200, 50), (255, 255, 255)]
        for i, col in enumerate(rings):
            r = radius - i * 10
            if r > 0:
                cv2.circle(frame, (cx, cy), r, col, max(1, int(4 * ratio)), cv2.LINE_AA)

        # 火花（固定種子，每幀一致）
        rng = np.random.default_rng(self.lifetime * 7)
        for _ in range(8):
            angle = rng.uniform(0, 2 * math.pi)
            d     = rng.uniform(10, radius + 15)
            sx    = cx + int(d * math.cos(angle))
            sy    = cy + int(d * math.sin(angle))
            cv2.circle(frame, (sx, sy), 2, (255, 240, 100), -1)


# ══════════════════════════════════════════════════════════════════════════════
# 遊戲狀態
# ══════════════════════════════════════════════════════════════════════════════

class GameState:
    MAX_LIVES          = 3
    BASE_SPAWN_INTERVAL = 120   # 幀
    SCORE_PER_KILL     = 10
    SCORE_PER_LEVEL    = 100

    def __init__(self, frame_size: Tuple[int, int], monster_mode: MonsterMode = MonsterMode.MIXED):
        self.fw, self.fh = frame_size
        self.monsters:   List[Monster]   = []
        self.lasers:     List[Laser]     = []
        self.explosions: List[Explosion] = []

        self.score:     int  = 0
        self.lives:     int  = self.MAX_LIVES
        self.level:     int  = 1
        self.game_over: bool = False
        self.paused:    bool = False
        self.monster_mode: MonsterMode = monster_mode

        self.frame_count:   int = 0
        self.spawn_counter: int = 0

        self.message:       str = ""
        self.message_timer: int = 0

        self.laser_ready:    bool = True
        self.laser_cooldown: int  = 0
        self.LASER_COOLDOWN_FRAMES = 18

    # ── 訊息 ─────────────────────────────────────────────────────────────────

    def show_message(self, msg: str, duration: int = 60):
        self.message       = msg
        self.message_timer = duration

    # ── 生成怪物 ─────────────────────────────────────────────────────────────

    def _spawn_monster(self):
        edge = random.randint(0, 3)
        margin = 40
        if edge == 0:
            x, y = random.uniform(margin, self.fw - margin), -margin
        elif edge == 1:
            x, y = self.fw + margin, random.uniform(margin, self.fh - margin)
        elif edge == 2:
            x, y = random.uniform(margin, self.fw - margin), self.fh + margin
        else:
            x, y = -margin, random.uniform(margin, self.fh - margin)

        if self.monster_mode == MonsterMode.ZOMBIE:
            mtype = random.choices(
                [MonsterType.ZOMBIE, MonsterType.SKELETON, MonsterType.BAT],
                weights=[80, 15, 5], k=1
            )[0]
        elif self.monster_mode == MonsterMode.SKELETON:
            mtype = random.choices(
                [MonsterType.SKELETON, MonsterType.ZOMBIE, MonsterType.BAT],
                weights=[75, 15, 10], k=1
            )[0]
        elif self.monster_mode == MonsterMode.BAT:
            mtype = random.choices(
                [MonsterType.BAT, MonsterType.ZOMBIE, MonsterType.SKELETON],
                weights=[70, 15, 15], k=1
            )[0]
        else:
            mtype = random.choice(list(MonsterType))

        base_speed = 1.0 + self.level * 0.12
        if mtype == MonsterType.BAT:
            speed = random.uniform(1.2, 1.9) * base_speed
        else:
            speed = random.uniform(0.8, 1.6) * base_speed

        hp = max(1, random.randint(1, 2) + (self.level - 1) // 3)

        self.monsters.append(Monster(
            x=x, y=y, hp=hp, max_hp=hp,
            speed=speed, mtype=mtype,
            size=random.randint(30, 44),
        ))

    # ── 發射雷射 ─────────────────────────────────────────────────────────────

    def fire_laser(
        self, px: float, py: float,
        pushup_mode: bool = False
    ) -> bool:
        """
        發射雷射。
        pushup_mode=True：多目標齊射（伏地挺身）
        pushup_mode=False：單目標（深蹲）
        回傳是否實際發射。
        """
        alive = [m for m in self.monsters if m.alive]
        if not alive:
            return False
        if not self.laser_ready:
            return False

        if pushup_mode:
            # 伏地挺身：攻擊最近 3 隻怪物
            targets = sorted(alive, key=lambda m: m.dist_to(px, py))[:3]
            laser_color = (180, 50, 255)
        else:
            # 深蹲：攻擊最近的怪物
            targets     = [min(alive, key=lambda m: m.dist_to(px, py))]
            laser_color = (0, 220, 255)

        for target in targets:
            self.lasers.append(Laser(px, py, target.x, target.y, color=laser_color))
            target.hp    -= 1
            target.flash  = 6
            if target.hp <= 0:
                target.alive = False
                self.explosions.append(Explosion(target.x, target.y))
                pts = self.SCORE_PER_KILL * self.level
                self.score += pts
                self.show_message(f"+{pts} 分!", 35)

        self.laser_ready    = False
        self.laser_cooldown = self.LASER_COOLDOWN_FRAMES
        return True

    # ── 主更新 ───────────────────────────────────────────────────────────────

    def update(self, px: Optional[float] = None, py: Optional[float] = None):
        if self.game_over or self.paused:
            return

        self.frame_count  += 1
        px = px if px is not None else self.fw / 2
        py = py if py is not None else self.fh / 2

        # 生成怪物
        self.spawn_counter += 1
        spawn_interval = max(30, self.BASE_SPAWN_INTERVAL - self.level * 8)
        if self.spawn_counter >= spawn_interval:
            self.spawn_counter = 0
            for _ in range(min(self.level, 3)):
                self._spawn_monster()

        # 更新怪物
        reached = []
        for m in self.monsters:
            if m.alive:
                m.update(px, py)
                if m.reached(px, py):
                    reached.append(m)

        for m in reached:
            m.alive  = False
            self.lives -= 1
            self.show_message("!! 被攻擊！", 60)
            if self.lives <= 0:
                self.game_over = True
                self.show_message("GAME OVER", 9999)

        self.monsters    = [m for m in self.monsters if m.alive]
        self.lasers      = [l for l in self.lasers    if l.alive]
        self.explosions  = [e for e in self.explosions if e.alive]

        for l in self.lasers:
            l.update()
        for e in self.explosions:
            e.update()

        # 雷射冷卻
        if not self.laser_ready:
            self.laser_cooldown -= 1
            if self.laser_cooldown <= 0:
                self.laser_ready = True

        # 等級提升
        new_level = 1 + self.score // self.SCORE_PER_LEVEL
        if new_level > self.level:
            self.level = new_level
            self.show_message(f"Level {self.level} 升級！", 90)

        # 訊息計時
        if self.message_timer > 0:
            self.message_timer -= 1
        elif self.message_timer == 0 and not self.game_over:
            self.message = ""

    # ── 繪製 HUD ─────────────────────────────────────────────────────────────

    def draw_hud(self, frame: np.ndarray):
        h, w = frame.shape[:2]

        # 頂部半透明欄
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 62), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        # 分數（左）
        put_text(frame, f"Score: {self.score}",
                 (12, 10), size=30, color=(255, 220, 50), shadow=True)

        # 等級（分數右側）
        sw, _ = text_size(f"Score: {self.score}", 30)
        put_text(frame, f"Lv.{self.level}",
                 (sw + 24, 10), size=30, color=(80, 255, 200), shadow=True)

        # 怪物數（中央）
        alive_cnt = len(self.monsters)
        put_text_centered(frame, f"MOB x{alive_cnt}",
                          w // 2, 14, size=26, color=(200, 100, 255), shadow=True)

        # 生命值（右，紅色圓點）
        for i in range(self.MAX_LIVES):
            cx    = w - 30 - i * 38
            color = (30, 30, 220) if i < self.lives else (50, 50, 50)
            cv2.circle(frame, (cx, 32), 13, color, -1)
            cv2.circle(frame, (cx, 32), 13, (0, 0, 0), 1)

        # 雷射充能條
        bx, by, bw_, bh_ = 12, h - 105, 160, 12
        cv2.rectangle(frame, (bx, by), (bx + bw_, by + bh_), (30, 30, 30), -1)
        if self.laser_ready:
            cv2.rectangle(frame, (bx, by), (bx + bw_, by + bh_), (0, 255, 255), -1)
            put_text(frame, "LASER READY!", (bx + bw_ + 8, by - 4),
                     size=16, color=(0, 255, 255))
        else:
            charge = 1.0 - self.laser_cooldown / self.LASER_COOLDOWN_FRAMES
            fill_w = int(bw_ * charge)
            fill_c = (0, int(200 * charge), int(255 * charge))
            cv2.rectangle(frame, (bx, by), (bx + fill_w, by + bh_), fill_c, -1)
            put_text(frame, "Charging...", (bx + bw_ + 8, by - 4),
                     size=16, color=(120, 120, 120))

        # 中央訊息
        if self.message and self.message_timer > 0:
            ty = h // 2 - 90
            put_text_centered(frame, self.message, w // 2, ty,
                              size=46, color=(255, 220, 50), shadow=True)

        # Game Over 遮罩
        if self.game_over:
            overlay2 = frame.copy()
            cv2.rectangle(overlay2, (0, 0), (w, h), (0, 0, 0), -1)
            cv2.addWeighted(overlay2, 0.72, frame, 0.28, 0, frame)

            for text, sz, color, ty in [
                ("GAME OVER",                    64, (50,  50, 255),   h // 2 - 130),
                (f"最終分數: {self.score}",        40, (255, 255, 255), h // 2 -  40),
                ("按 R 重新開始，按 H 返回首頁，按 Q 離開", 24, (210, 210, 210), h // 2 +  32),
            ]:
                put_text_centered(frame, text, w // 2, ty,
                                  size=sz, color=color, shadow=True)

            # 按鈕樣式提示
            btn_w, btn_h = 220, 60
            btn_gap = 24
            center_x = w // 2
            left_x = center_x - btn_w - btn_gap // 2
            right_x = center_x + btn_gap // 2
            btn_y = h // 2 + 70

            cv2.rectangle(frame, (left_x, btn_y), (left_x + btn_w, btn_y + btn_h), (30, 40, 80), -1)
            cv2.rectangle(frame, (left_x, btn_y), (left_x + btn_w, btn_y + btn_h), (170, 200, 255), 2)
            put_text_centered(frame, "R 重新開始", left_x + btn_w // 2, btn_y + btn_h // 2 - 8,
                              size=24, color=(180, 230, 255), bold=True)

            cv2.rectangle(frame, (right_x, btn_y), (right_x + btn_w, btn_y + btn_h), (50, 40, 40), -1)
            cv2.rectangle(frame, (right_x, btn_y), (right_x + btn_w, btn_y + btn_h), (255, 180, 130), 2)
            put_text_centered(frame, "H 返回首頁", right_x + btn_w // 2, btn_y + btn_h // 2 - 8,
                              size=24, color=(255, 210, 170), bold=True)
            
            exit_x = center_x - btn_w // 2
            exit_y = btn_y + btn_h + 16
            cv2.rectangle(frame, (exit_x, exit_y), (exit_x + btn_w, exit_y + btn_h), (60, 40, 40), -1)
            cv2.rectangle(frame, (exit_x, exit_y), (exit_x + btn_w, exit_y + btn_h), (220, 120, 120), 2)
            put_text_centered(frame, "Q 退出遊戲", exit_x + btn_w // 2, exit_y + btn_h // 2 - 8,
                              size=24, color=(255, 200, 200), bold=True)
