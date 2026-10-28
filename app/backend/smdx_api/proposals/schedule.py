"""生鮮・惣菜の対象日・発注日・期限(詳細設計書「対象日の算出」)。日付はすべて日本時間で決める。"""
from datetime import date, datetime, time, timedelta

from smdx_api.clock import JST
from smdx_api.proposals.codes import MAX_DAYS_AHEAD
from smdx_api.settings.values import AppSettings

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


def deli_deadline(target: date, band: int, settings: AppSettings) -> datetime:
    """惣菜の承認期限 = 対象日のその時間帯の製造開始時刻。"""
    return datetime.combine(target, settings.deli_production_start[band], JST)


def deli_default_target(now: datetime, settings: AppSettings) -> date:
    """製造計画の既定の対象日。最初の時間帯の製造開始時刻より前なら当日、ちょうど以後は翌日。"""
    local = now.astimezone(JST)
    first = settings.deli_production_start[min(settings.deli_time_bands)]
    return local.date() if local.time() < first else local.date() + timedelta(days=1)


def open_bands(target: date, now: datetime, settings: AppSettings) -> list[int]:
    """期限(製造開始時刻)が now より後の時間帯。ちょうどの時間帯は締め切り済みとする。"""
    return [b for b in sorted(settings.deli_time_bands) if deli_deadline(target, b, settings) > now]
