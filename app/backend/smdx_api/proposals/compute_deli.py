"""惣菜(時間帯別)の製造計画の計算(詳細設計書「処理の流れ」2〜4、「発注数・製造数の計算(惣菜)」「欠損時の扱い」)。

行は 商品 × 対象日の時間帯のうち製造開始時刻(期限)を過ぎていないもの。前日作成(翌日以降の対象日)は全時間帯になる。
計画日は「情報の時点」どおり 対象日 − 1(前日作成)とし、学習用の表と同じ基準日(計画日 − 1)で特徴量を作る。
陳列残数は、対象日×商品で入力時刻が現在以前の最新の1件だけを使い、入力時刻の直後の時間帯から差し引く。
"""
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from smdx_api.clock import JST
from smdx_api.db.models import Department, DisplayStockEntry
from smdx_api.order_calc.deli import calc_deli_production, display_stock_by_band
from smdx_api.predictor.predict import predict
from smdx_api.proposals import inputs
from smdx_api.proposals.basis import build_basis, plain
from smdx_api.proposals.codes import WARNING_CODES
from smdx_api.proposals.compute_fresh import ComputedProposal, ComputeServices, business_hours, department_products
from smdx_api.proposals.deadlines import apply_deadlines
from smdx_api.proposals.schedule import deli_deadline, open_bands
from smdx_api.settings.values import AppSettings
from smdx_api.weather_client.service import get_forecast
from smdx_features.build import BandTarget, build_time_band_features
from smdx_features.columns import feature_columns
from smdx_features.weather import summarize


def latest_display_stock(db: Session, product_ids: Sequence[int], target: date,
                         now: datetime) -> dict[int, tuple[int, datetime]]:
    """商品ID → (陳列残数, 入力時刻)。対象日の入力のうち、入力時刻が now 以前で最も新しいもの。"""
    if not product_ids:
        return {}
    latest = (select(DisplayStockEntry.product_id, func.max(DisplayStockEntry.entered_at).label("at"))
              .where(DisplayStockEntry.product_id.in_(product_ids), DisplayStockEntry.target_date == target,
                     DisplayStockEntry.entered_at <= now)
              .group_by(DisplayStockEntry.product_id).subquery())
    rows = db.execute(select(DisplayStockEntry.product_id, DisplayStockEntry.quantity, DisplayStockEntry.entered_at)
                      .join(latest, (DisplayStockEntry.product_id == latest.c.product_id)
                            & (DisplayStockEntry.entered_at == latest.c.at))
                      .where(DisplayStockEntry.target_date == target))
    return {pid: (qty, at) for pid, qty, at in rows}


def compute_deli(
    db: Session,
    department: Department,
    now: datetime,
    settings: AppSettings,
    services: ComputeServices,
    target: date,
) -> tuple[list[ComputedProposal], str | None]:
    """部門の製造計画を計算する(保存はしない)。2つ目の戻り値は予測の注記(時間帯の設定変更など)。"""
    apply_deadlines(db, now, department.id)
    bands = open_bands(target, now, settings)
    products = department_products(db, department)
    if not bands or not products:
        return [], None

    today = now.astimezone(JST).date()
    plan_date = target - timedelta(days=1)
    since = today - timedelta(days=inputs.HISTORY_DAYS)
    ids = [p.id for p in products]
    _, close_h = business_hours(settings)

    latest_pos = inputs.latest_pos_date(db, department.id)
    missing = inputs.missing_pos_days(db, department.id, since, latest_pos) if latest_pos else set()
    forecast = get_forecast(db, services.weather_client, today, target, now, settings.weather_stale_hours)
    weather = inputs.weather_frame(forecast)
    stock = latest_display_stock(db, ids, target, now)

    rows = [BandTarget(p.product_code, target, b, plan_date) for p in products for b in bands]
    features = build_time_band_features(
        rows, inputs.hourly_sales_frame(db, ids, since), inputs.calendar_data(db, since, target),
        inputs.promotions_frame(db, ids, since, target), weather, settings.deli_time_bands, close_h,
        known_through=latest_pos, missing_days=missing,
    )
    batch = predict(services.registry, "time_band", features, weather_available=forecast.available,
                    current_time_bands=settings.deli_time_bands)

    safety = settings.safety_factor[department.code]
    # 前日分の POS: 基準日(計画日の前日。未来の計画日は当日の前日)までの POS がそろっているか
    expected_pos = min(plan_date, today) - timedelta(days=1)
    out = []
    i = 0
    for p in products:
        qty_entered = stock.get(p.id)
        by_band = display_stock_by_band(qty_entered[1].astimezone(JST).time() if qty_entered else None,
                                        qty_entered[0] if qty_entered else 0, settings.deli_time_bands)
        for band in bands:
            row = {c: plain(features[c].iloc[i]) for c in feature_columns("time_band")}
            demand = batch.values[i]
            display = by_band[band]
            end_h = settings.band_end(band).hour + (1 if settings.band_end(band).minute else 0)
            target_weather = forecast.available and row["weather_code"] is not None and row["temperature"] is not None
            flags = {
                "NO_INVENTORY": False,
                "NO_HISTORY": batch.no_history[i],
                "NO_WEATHER": not target_weather,
                "STALE_POS": latest_pos is None or latest_pos < expected_pos,
            }
            is_baseline = batch.row_is_baseline[i]
            fetched_at = forecast.fetched_at if target_weather else None
            probability = (summarize(weather, target, band, end_h, "max", "probability").precipitation
                           if weather is not None else None)
            basis = build_basis(
                features=row, predicted_qty=demand, model_version="baseline" if is_baseline else batch.model_version,
                is_baseline=is_baseline, precipitation_probability=probability, inventory_qty=None,
                inventory_based_at=None, backlog_qty=None, carry_over_qty=None, expected_sales_qty=None,
                display_stock_qty=display, weather_fetched_at=fetched_at,
            )
            basis["holiday_name"] = plain(features["holiday_name"].iloc[i])
            basis["loaded_model_version"] = batch.loaded_version
            out.append(ComputedProposal(
                product_id=p.id, product_code=p.product_code, target_date=target, time_band=band,
                qty=calc_deli_production(demand, safety, display), deadline=deli_deadline(target, band, settings),
                warnings=tuple(w for w in WARNING_CODES if flags[w]), basis=basis, predicted_qty=float(demand),
                model_version=basis["model_version"], features=row, weather_fetched_at=fetched_at,
            ))
            i += 1
    return out, batch.notice
