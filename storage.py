"""
storage.py
資料層 — 集中所有 SQLite 存取（標準庫 sqlite3，離線、零額外依賴）。

**使用者是骨幹**：所有數據（身高體重、BMI、場次、數位分身）都掛在某位 user 身上。
其他層一律透過 `User` 模型或本模組函式讀寫，不直接散落 SQL。
資料庫檔放專案根目錄 gym.db，首次使用自動建表。

資料表
------
users        使用者基本資料（name / 身高 / 體重 / 性別 / 年齡）
bmi_history  每次更新身體數據的 BMI 紀錄（含 user_id、日期）
sessions     每場遊戲結果（user_id、reps_json、分數、等級、卡路里）
twin_state   每位使用者的數位分身快照（力量/耐力/體態/等級）
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 資料庫路徑：預設專案根目錄 gym.db（玩家的存檔）。
# 可用環境變數 GYM_DB 覆寫——測試時指向暫存檔，避免動到玩家真正的存檔。
DB_PATH = os.environ.get("GYM_DB") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gym.db")

DEFAULT_WEIGHT_KG = 65.0     # 尚無體重時的保底值


# ══════════════════════════════════════════════════════════════════════════════
# 連線與建表
# ══════════════════════════════════════════════════════════════════════════════

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建立所有資料表（若不存在）。"""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                height_cm  REAL,
                weight_kg  REAL,
                sex        TEXT,
                age        INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS bmi_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                date      TEXT,
                height_cm REAL,
                weight_kg REAL,
                bmi       REAL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                started_at TEXT,
                ended_at   TEXT,
                reps_json  TEXT,
                score      INTEGER,
                level      INTEGER,
                calories   REAL
            );

            CREATE TABLE IF NOT EXISTS twin_state (
                user_id    INTEGER PRIMARY KEY,
                strength   REAL DEFAULT 0,
                stamina    REAL DEFAULT 0,
                physique   REAL DEFAULT 0,
                level      INTEGER DEFAULT 1,
                updated_at TEXT
            );
            """
        )


# ══════════════════════════════════════════════════════════════════════════════
# BMI 計算
# ══════════════════════════════════════════════════════════════════════════════

def compute_bmi(height_cm: float, weight_kg: float) -> float:
    """BMI = 體重(kg) / 身高(m)²。"""
    h_m = (height_cm or 0) / 100.0
    if h_m <= 0:
        return 0.0
    return weight_kg / (h_m * h_m)


# ══════════════════════════════════════════════════════════════════════════════
# User 模型
# ══════════════════════════════════════════════════════════════════════════════

class User:
    """使用者模型：封裝該使用者的所有讀寫，呼叫端不直接碰 SQL。"""

    def __init__(self, row: sqlite3.Row):
        self.id = row["id"]
        self.name = row["name"]
        self.height_cm = row["height_cm"]
        self.weight_kg = row["weight_kg"]
        self.sex = row["sex"]
        self.age = row["age"]
        self.created_at = row["created_at"]

    # ── 身體數據 ──
    def update_body(self, height_cm: float, weight_kg: float) -> float:
        """更新身高體重並新增一筆 BMI 紀錄；回傳 BMI。"""
        bmi = update_body(self.id, height_cm, weight_kg)
        self.height_cm, self.weight_kg = height_cm, weight_kg
        return bmi

    @property
    def weight(self) -> float:
        return float(self.weight_kg) if self.weight_kg else DEFAULT_WEIGHT_KG

    def latest_bmi(self) -> Optional[float]:
        return latest_bmi(self.id)

    def bmi_change_last_month(self) -> Optional[float]:
        return bmi_change_last_month(self.id)

    def get_bmi_history(self) -> List[Dict]:
        return get_bmi_history(self.id)

    # ── 場次 ──
    def add_session(self, reps, score, level, calories, started_at=None, ended_at=None):
        add_session(self.id, reps, score, level, calories, started_at, ended_at)

    def get_sessions(self) -> List[Dict]:
        return get_sessions(self.id)

    # ── 數位分身 ──
    def get_twin_state(self) -> Dict:
        return get_twin_state(self.id)

    def save_twin_state(self, strength, stamina, physique, level):
        save_twin_state(self.id, strength, stamina, physique, level)


# ══════════════════════════════════════════════════════════════════════════════
# 使用者 CRUD
# ══════════════════════════════════════════════════════════════════════════════

def create_user(name: str, height_cm: float, weight_kg: float,
                sex: Optional[str] = None, age: Optional[int] = None) -> User:
    """建立使用者，並初始化第一筆 BMI 紀錄與 twin_state。"""
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, height_cm, weight_kg, sex, age, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, height_cm, weight_kg, sex, age, now),
        )
        uid = cur.lastrowid
        conn.execute(
            "INSERT INTO bmi_history (user_id, date, height_cm, weight_kg, bmi) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, now, height_cm, weight_kg, compute_bmi(height_cm, weight_kg)),
        )
        conn.execute(
            "INSERT INTO twin_state (user_id, strength, stamina, physique, level, updated_at) "
            "VALUES (?, 0, 0, 0, 1, ?)",
            (uid, now),
        )
    return get_user(uid)


def list_users() -> List[User]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
    return [User(r) for r in rows]


def get_user(uid: int) -> Optional[User]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return User(row) if row else None


def update_body(uid: int, height_cm: float, weight_kg: float) -> float:
    now = datetime.now().isoformat(timespec="seconds")
    bmi = compute_bmi(height_cm, weight_kg)
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET height_cm=?, weight_kg=? WHERE id=?",
            (height_cm, weight_kg, uid),
        )
        conn.execute(
            "INSERT INTO bmi_history (user_id, date, height_cm, weight_kg, bmi) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, now, height_cm, weight_kg, bmi),
        )
    return bmi


# ══════════════════════════════════════════════════════════════════════════════
# BMI 歷史
# ══════════════════════════════════════════════════════════════════════════════

def get_bmi_history(uid: int) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT date, height_cm, weight_kg, bmi FROM bmi_history "
            "WHERE user_id=? ORDER BY date ASC", (uid,)
        ).fetchall()
    return [dict(r) for r in rows]


def latest_bmi(uid: int) -> Optional[float]:
    hist = get_bmi_history(uid)
    return hist[-1]["bmi"] if hist else None


def bmi_change_last_month(uid: int) -> Optional[float]:
    """最新 BMI 與約一個月前最接近紀錄的差值；紀錄不足兩筆回 None。"""
    hist = get_bmi_history(uid)
    if len(hist) < 2:
        return None
    parse = datetime.fromisoformat
    latest = hist[-1]
    target = parse(latest["date"]) - timedelta(days=30)
    prior = hist[:-1]
    ref = min(prior, key=lambda r: abs((parse(r["date"]) - target).total_seconds()))
    return latest["bmi"] - ref["bmi"]


# ══════════════════════════════════════════════════════════════════════════════
# 場次
# ══════════════════════════════════════════════════════════════════════════════

def add_session(uid: int, reps: Dict[str, int], score: int, level: int,
                calories: float, started_at: Optional[str] = None,
                ended_at: Optional[str] = None) -> None:
    ended = ended_at or datetime.now().isoformat(timespec="seconds")
    started = started_at or ended
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, started_at, ended_at, reps_json, score, level, calories) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, started, ended, json.dumps(reps), int(score), int(level), float(calories)),
        )


def get_sessions(uid: int) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY ended_at ASC", (uid,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["reps"] = json.loads(d.get("reps_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["reps"] = {}
        out.append(d)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 數位分身狀態
# ══════════════════════════════════════════════════════════════════════════════

def get_twin_state(uid: int) -> Dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM twin_state WHERE user_id=?", (uid,)).fetchone()
    if row:
        return dict(row)
    return {"user_id": uid, "strength": 0, "stamina": 0, "physique": 0, "level": 1}


def save_twin_state(uid: int, strength: float, stamina: float,
                    physique: float, level: int) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO twin_state (user_id, strength, stamina, physique, level, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "strength=excluded.strength, stamina=excluded.stamina, "
            "physique=excluded.physique, level=excluded.level, updated_at=excluded.updated_at",
            (uid, float(strength), float(stamina), float(physique), int(level), now),
        )


# 模組載入時確保資料表存在
init_db()
