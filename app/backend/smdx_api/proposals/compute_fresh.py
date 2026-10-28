"""生鮮(日別)の提案の計算(詳細設計書「処理の流れ」2〜4、「発注数・製造数の計算(生鮮)」「欠損時の扱い」)。

予測する日は 当日〜対象日。当日 = 在庫基準日(基準日の残り分)、明日〜対象日の前日 = 途中の日、対象日 = カバー期間(毎日納品)。
対象日を指定した場合は、最も早い納品日がその日以前の商品について、その日を納品日とする提案を作る。
"""
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.clock import JST
from smdx_api.db.models import Department, Product
from smdx_api.order_calc.fresh import (
    FreshInput,
    calc_fresh_order,
    expected_sales,
    hourly_sales_ratio,
    remaining_sales_ratio,
    sales_before_delivery,
)
from smdx_api.predictor.predict import predict
from smdx_api.predictor.registry import ModelRegistry
from smdx_api.proposals import inputs
from smdx_api.proposals.basis import build_basis, plain
from smdx_api.proposals.codes import WARNING_CODES
from smdx_api.proposals.deadlines import apply_deadlines
from smdx_api.proposals.schedule import earliest_delivery_date, fresh_deadline, order_date_for
from smdx_api.settings.values import AppSettings
from smdx_api.weather_client.client import WeatherClient
from smdx_api.weather_client.service import get_forecast
from smdx_features.build import DailyTarget, build_daily_features
from smdx_features.columns import feature_columns
from smdx_features.weather import summarize


@dataclass(frozen=True)
class FreshTargets:
    # None は各商品の最も早い納品日
    explicit_date: date | None


@dataclass(frozen=True)
class ComputeServices:
    registry: ModelRegistry
    weather_client: WeatherClient


@dataclass(frozen=True)
class ComputedProposal:
    product_id: int
    product_code: str
    target_date: date
    time_band: int | None
    qty: int
    deadline: datetime
    warnings: tuple[str, ...]
    basis: dict
    predicted_qty: float
    model_version: str
    features: dict
    weather_fetched_at: datetime | None


def department_products(db: Session, department: Department) -> list[Product]:
    return list(db.scalars(select(Product).where(Product.department_id == department.id, Product.is_active.is_(True))
                           .order_by(Product.product_code)))


def fresh_target_dates(products: Sequence[Product], now: datetime, settings: AppSettings, targets: FreshTargets) -> dict[int, date]:
    """商品ID → 対象日(納品日)。"""
    out = {}
    for p in products:
        earliest = earliest_delivery_date(now, settings.order_cutoff[p.department.code], p.lead_time_days)
        if targets.explicit_date is None:
            out[p.id] = earliest
        elif earliest <= targets.explicit_date:
            out[p.id] = targets.explicit_date
    return out


def _business_hours(settings: AppSettings) -> tuple[int, int]:
    """特徴量の集約に使う営業時間(時)。閉店が HH:30 などの場合はその時を含める。"""
    close = settings.business_close
    return settings.business_open.hour, close.hour + (1 if close.minute else 0)


def _row_features(features, i: int) -> dict[str, Any]:
    return {c: plain(features[c].iloc[i]) for c in feature_columns("daily")}


def compute_fresh(
    db: Session,
    department: Department,
    now: datetime,
    settings: AppSettings,
    services: ComputeServices,
    targets: FreshTargets,
) -> tuple[list[ComputedProposal], str | None]:
    """部門の生鮮の提案を計算する(保存はしない)。2つ目の戻り値は予測の注記(時間帯の設定変更など)。"""
    # 発注残の集計の前に、期限経過による状態更新を行う
    apply_deadlines(db, now, department.id)
    products = department_products(db, department)
    target_by_id = fresh_target_dates(products, now, settings, targets)
    products = [p for p in products if p.id in target_by_id]
    if not products:
        return [], None

    code = department.code
    cutoff, delivery_time = settings.order_cutoff[code], settings.delivery_time[code]
    today = now.astimezone(JST).date()
    last_day = max(target_by_id.values())
    since = today - timedelta(days=inputs.HISTORY_DAYS)
    ids = [p.id for p in products]

    inventory = inputs.latest_inventory_today(db, ids, now)
    latest_pos = inputs.latest_pos_date(db, department.id)
    missing = inputs.missing_pos_days(db, department.id, since, latest_pos) if latest_pos else set()
    forecast = get_forecast(db, services.weather_client, today, last_day, now, settings.weather_stale_hours)
    weather = inputs.weather_frame(forecast)

    # 商品ごとに 当日〜対象日 の行を並べる
    rows: list[DailyTarget] = []
    spans: dict[int, tuple[int, int]] = {}
    for p in products:
        target = target_by_id[p.id]
        order_date = order_date_for(target, p.lead_time_days)
        start = len(rows)
        d = today
        while d <= target:
            rows.append(DailyTarget(p.product_code, d, order_date))
            d += timedelta(days=1)
        spans[p.id] = (start, len(rows) - 1)

    features = build_daily_features(
        rows, inputs.daily_sales_frame(db, ids, since), inputs.calendar_data(db, since, last_day),
        inputs.promotions_frame(db, ids, since, last_day), weather, _business_hours(settings),
        known_through=latest_pos, missing_days=missing,
    )
    batch = predict(services.registry, "daily", features, weather_available=forecast.available, current_time_bands=None)
    open_h, close_h = _business_hours(settings)

    out = []
    for p in products:
        target = target_by_id[p.id]
        first, last = spans[p.id]
        order_date = order_date_for(target, p.lead_time_days)
        inv = inventory.get(p.id)
        based_at = inv[1] if inv else now.astimezone(JST)

        # 基準日の残り分 + 途中の日 + 納品日の納品前の分。当日が納品日の場合(リードタイム0)は販売見込を数えない
        if target > today:
            hourly = list(inputs.hourly_sales_rows(db, p.id, since))
            until = today - timedelta(days=1)
            ratio = hourly_sales_ratio(hourly, today.weekday(), until)
            remaining = remaining_sales_ratio(based_at.time(), settings.business_open, settings.business_close, ratio)
            sales = expected_sales(batch.values[first], remaining, batch.values[first + 1:last])
            sales += sales_before_delivery(batch.values[last], delivery_time, settings.business_open,
                                           settings.business_close, hourly_sales_ratio(hourly, target.weekday(), until))
        else:
            sales = 0.0
        backlog = inputs.backlog_qty(db, p.id, based_at, target, delivery_time)
        demand = batch.values[last]
        result = calc_fresh_order(FreshInput(
            demand_forecast=demand, expected_sales_qty=sales, inventory_qty=inv[0] if inv else None,
            backlog_qty=backlog, can_carry_over=p.can_carry_over, safety_factor=settings.safety_factor[code],
            order_unit=p.order_unit,
        ))

        row = _row_features(features, last)
        target_weather = forecast.available and row["weather_code"] is not None and row["temperature"] is not None
        # 前日分の POS: 発注日(未来の発注日は当日)の前日までの POS がそろっているか
        expected_pos = min(order_date, today) - timedelta(days=1)
        flags = {
            "NO_INVENTORY": inv is None,
            "NO_HISTORY": batch.no_history[last],
            "NO_WEATHER": not target_weather,
            "STALE_POS": latest_pos is None or latest_pos < expected_pos,
        }
        warnings = tuple(w for w in WARNING_CODES if flags[w])
        is_baseline = batch.row_is_baseline[last]
        model_version = "baseline" if is_baseline else batch.model_version
        fetched_at = forecast.fetched_at if target_weather else None
        probability = (summarize(weather, target, open_h, close_h, "max", "probability").precipitation
                       if weather is not None else None)
        basis = build_basis(
            features=row, predicted_qty=demand, model_version=model_version, is_baseline=is_baseline,
            precipitation_probability=probability, inventory_qty=inv[0] if inv else None,
            inventory_based_at=inv[1] if inv else None, backlog_qty=backlog,
            carry_over_qty=_round(result.carry_over_qty), expected_sales_qty=_round(sales), display_stock_qty=None,
            weather_fetched_at=fetched_at,
        )
        basis["holiday_name"] = plain(features["holiday_name"].iloc[last])
        # 最新性判定で比べるのは、計算時に読み込んでいたモデルの版(行がベースラインになったかどうかとは分ける)
        basis["loaded_model_version"] = batch.loaded_version
        out.append(ComputedProposal(
            product_id=p.id, product_code=p.product_code, target_date=target, time_band=None, qty=result.order_qty,
            deadline=fresh_deadline(target, p.lead_time_days, cutoff), warnings=warnings, basis=basis,
            predicted_qty=float(demand), model_version=model_version, features=row, weather_fetched_at=fetched_at,
        ))
    return out, batch.notice


def _round(v: float) -> float:
    """根拠の表示用に小数第3位で丸める(浮動小数の端数を残さない)。"""
    return 0.0 if math.isclose(v, 0, abs_tol=1e-12) else round(v, 3)
