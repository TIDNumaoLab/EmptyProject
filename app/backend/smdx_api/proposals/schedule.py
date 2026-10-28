"""生鮮の対象日・発注日・期限(詳細設計書「対象日の算出」)。日付はすべて日本時間で決める。"""
from datetime import date, datetime, time, timedelta

from smdx_api.clock import JST
from smdx_api.proposals.codes import MAX_DAYS_AHEAD

TARGET_OUT_OF_RANGE = "対象日は当日から15日先までを指定してください"


class TargetOutOfRange(ValueError):
    def __init__(self) -> None:
        super().__init__(TARGET_OUT_OF_RANGE)


def check_target_range(target: date, today: date) -> None:
    if not today <= target <= today + timedelta(days=MAX_DAYS_AHEAD):
        raise TargetOutOfRange()


def earliest_delivery_date(now: datetime, cutoff: time, lead_time_days: int) -> date:
    """最も早い納品日。締め時刻より前なら 今日+リードタイム、締め時刻ちょうど以後は 今日+リードタイム+1日。"""
    local = now.astimezone(JST)
    days = lead_time_days if local.time() < cutoff else lead_time_days + 1
    return local.date() + timedelta(days=days)


def order_date_for(target: date, lead_time_days: int) -> date:
    return target - timedelta(days=lead_time_days)


def fresh_deadline(target: date, lead_time_days: int, cutoff: time) -> datetime:
    """承認期限 = 対象の納品日に向けた発注日の発注締め時刻。"""
    return datetime.combine(order_date_for(target, lead_time_days), cutoff, JST)
