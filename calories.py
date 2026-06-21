"""
calories.py
卡路里估算 — 依使用者體重與動作種類計算消耗。

公式
----
    卡路里 ≈ MET × 體重(kg) × 運動時數(hr)

假設
----
運動時數採「動作次數 × 每次估計秒數」推算（非整場遊戲時長），
因此純發呆不會累積卡路里，較貼近實際運動量。
每個動作的 MET 與每次秒數定義在其 Exercise 類別（exercises.py），
集中管理、方便依場地與裝置調校。
"""

from typing import Dict

from exercises import get_meta


def calories_for(met: float, weight_kg: float, count: int,
                 seconds_per_rep: float) -> float:
    """單一動作的卡路里：MET × 體重 × (次數 × 每次秒數 / 3600)。"""
    hours = (count * seconds_per_rep) / 3600.0
    return met * weight_kg * hours


def session_calories(reps: Dict[str, int], weight_kg: float) -> float:
    """
    依各動作次數與使用者體重，估算整場消耗卡路里。
    reps 例如 {"squat":12, "pushup":8, "raise_hand":3}。
    未知的動作 key 會被忽略。
    """
    total = 0.0
    for key, count in reps.items():
        meta = get_meta(key)
        if meta is None or not count:
            continue
        total += calories_for(meta.met, weight_kg, count, meta.seconds_per_rep)
    return total
