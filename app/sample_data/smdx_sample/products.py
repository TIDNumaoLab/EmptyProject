"""サンプル商品マスタ(15品: 青果6・鮮魚4・惣菜5)。

商品名・入数・原価・売価・基準数量・気温効果は実装計画 段階2 の判断 2-2 の表に従う。
惣菜は製造計画のため入数1・リードタイム0(判断 2-1)。
"""
from dataclasses import dataclass
from typing import Literal

TempEffect = Literal["none", "fried", "hot_decrease"]


@dataclass(frozen=True)
class SampleProduct:
    code: str
    name: str
    department_code: str
    order_unit: int
    lead_time_days: int
    can_carry_over: bool
    cost_price: float
    selling_price: float
    # 曜日・天候などの効果を掛ける前の1日の需要
    base_qty: float
    # fried: 低温で需要が増える(揚げ物)、hot_decrease: 高温で需要が減る(鍋物向けの青果など)
    temp_effect: TempEffect


def _p(code, name, dept, unit, lt, carry, cost, price, base, effect="none") -> SampleProduct:
    return SampleProduct(code, name, dept, unit, lt, carry, cost, price, base, effect)


PRODUCTS: list[SampleProduct] = [
    _p("VEG-001", "キャベツ", "VEG", 6, 1, True, 98, 158, 40),
    _p("VEG-002", "トマト", "VEG", 4, 1, True, 120, 198, 35),
    _p("VEG-003", "白菜", "VEG", 4, 1, True, 150, 248, 20, "hot_decrease"),
    _p("VEG-004", "大根", "VEG", 6, 1, True, 90, 148, 25, "hot_decrease"),
    _p("VEG-005", "きゅうり", "VEG", 10, 1, True, 40, 68, 30),
    _p("VEG-006", "バナナ", "VEG", 6, 1, True, 110, 178, 45),
    _p("FISH-001", "生鮭切身", "FISH", 1, 1, False, 200, 348, 25),
    _p("FISH-002", "まぐろ刺身", "FISH", 1, 1, False, 350, 598, 20),
    _p("FISH-003", "さんま", "FISH", 5, 1, False, 80, 148, 15),
    _p("FISH-004", "あじ", "FISH", 5, 1, False, 70, 128, 15),
    _p("DELI-001", "唐揚げ", "DELI", 1, 0, False, 180, 398, 40, "fried"),
    _p("DELI-002", "コロッケ", "DELI", 1, 0, False, 40, 98, 35, "fried"),
    _p("DELI-003", "幕の内弁当", "DELI", 1, 0, False, 250, 498, 30),
    _p("DELI-004", "おにぎり", "DELI", 1, 0, False, 50, 128, 50),
    _p("DELI-005", "ポテトサラダ", "DELI", 1, 0, False, 60, 198, 20),
]

# 惣菜の時間帯(開始時 10/11/14/17、閉店20時)ごとの需要の構成比
_DEFAULT_SHARES = {10: 0.1, 11: 0.3, 14: 0.2, 17: 0.4}
BAND_SHARES: dict[str, dict[int, float]] = {
    p.code: ({10: 0.1, 11: 0.5, 14: 0.15, 17: 0.25} if p.code == "DELI-003" else dict(_DEFAULT_SHARES))
    for p in PRODUCTS
    if p.department_code == "DELI"
}

TIME_BANDS = [10, 11, 14, 17]
BUSINESS_OPEN_HOUR = 10
BUSINESS_CLOSE_HOUR = 20


def band_hours(band: int) -> range:
    """時間帯に含まれる時(開始時 ≤ 時 < 次の開始時。最後は閉店時まで)。"""
    later = [b for b in TIME_BANDS if b > band]
    return range(band, later[0] if later else BUSINESS_CLOSE_HOUR)
