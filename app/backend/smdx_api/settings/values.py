"""画面で変更する設定(F-17)の既定値・解決・検証。DB に依存しない。

項目と既定値は詳細設計書「設定項目」に従う。DB の settings テーブルには、店長が保存した
キーだけを JSON で持ち、保存されていないキーは既定値で補う。
開店・閉店に依存する既定値(発注締め時刻・納品時刻・時間帯の区切り)は、保存済みの営業時間から求める。
"""
import re
from collections.abc import Mapping, Sequence
from datetime import time
from typing import Any

from pydantic import BaseModel, ConfigDict

INTERNAL_PREFIX = "internal."
DEFAULT_BUSINESS_HOURS = {"open": "10:00", "close": "20:00"}
DEFAULT_SAFETY_FACTOR = 1.1
# 既定の時間帯の区切り: 開店〜11時、11〜14時、14〜17時、17時〜閉店
DEFAULT_LATER_BANDS = [11, 14, 17]
DEFAULT_WEATHER_STALE_HOURS = 3

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

Departments = Sequence[tuple[str, str]]  # (部門コード, business_type)


class SettingsError(Exception):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key
        self.message = message


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    business_open: time
    business_close: time
    safety_factor: dict[str, float]
    order_cutoff: dict[str, time]
    delivery_time: dict[str, time]
    deli_time_bands: list[int]
    deli_production_start: dict[int, time]
    weather_stale_hours: float

    def band_end(self, start: int) -> time:
        """時間帯の終わり(次の区切りの開始時。最後の時間帯は閉店時刻)。"""
        later = [b for b in self.deli_time_bands if b > start]
        return time(later[0]) if later else self.business_close


def _parse_time(key: str, value: Any) -> time:
    if not isinstance(value, str) or not (m := _TIME_RE.match(value)):
        raise SettingsError(key, "時刻は HH:MM の形式で指定してください")
    return time(int(m.group(1)), int(m.group(2)))


def _fmt(t: time) -> str:
    return t.strftime("%H:%M")


def _positive(key: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise SettingsError(key, "0より大きい数値を指定してください")
    return float(value)


def _default_production_start(bands: Sequence[int]) -> dict[str, str]:
    # 製造開始は各時間帯の1時間前
    return {str(b): f"{max(b - 1, 0):02d}:00" for b in bands}


def allowed_keys(departments: Departments) -> set[str]:
    keys = {"business_hours", "deli_time_bands", "deli_production_start", "weather_stale_hours"}
    for code, business_type in departments:
        keys.add(f"safety_factor.{code}")
        if business_type == "order":
            keys.add(f"order_cutoff.{code}")
            keys.add(f"delivery_time.{code}")
    return keys


def resolve(stored: Mapping[str, Any], departments: Departments) -> AppSettings:
    """保存済みの値と既定値から設定を組み立てる。値が不正なら SettingsError。"""
    hours = stored.get("business_hours", DEFAULT_BUSINESS_HOURS)
    if not isinstance(hours, Mapping):
        raise SettingsError("business_hours", "開店・閉店の時刻を指定してください")
    open_ = _parse_time("business_hours", hours.get("open"))
    close = _parse_time("business_hours", hours.get("close"))
    if close <= open_:
        raise SettingsError("business_hours", "閉店時刻は開店時刻より後にしてください")

    safety, cutoff, delivery = {}, {}, {}
    for code, business_type in departments:
        key = f"safety_factor.{code}"
        safety[code] = _positive(key, stored.get(key, DEFAULT_SAFETY_FACTOR))
        if business_type == "order":
            key = f"order_cutoff.{code}"
            cutoff[code] = _parse_time(key, stored[key]) if key in stored else close
            key = f"delivery_time.{code}"
            delivery[code] = _parse_time(key, stored[key]) if key in stored else open_

    bands = stored.get("deli_time_bands")
    if bands is None:
        bands = [open_.hour] + [b for b in DEFAULT_LATER_BANDS if b > open_.hour]
    bands = _validate_bands(bands, open_, close)

    raw_start = stored.get("deli_production_start", _default_production_start(bands))
    if not isinstance(raw_start, Mapping) or set(raw_start) != {str(b) for b in bands}:
        raise SettingsError("deli_production_start", "製造開始時刻はすべての時間帯について指定してください")
    production_start = {}
    for b in bands:
        t = _parse_time("deli_production_start", raw_start[str(b)])
        if t > time(b):
            raise SettingsError("deli_production_start", "製造開始時刻は時間帯の開始以前にしてください")
        production_start[b] = t

    return AppSettings(
        business_open=open_,
        business_close=close,
        safety_factor=safety,
        order_cutoff=cutoff,
        delivery_time=delivery,
        deli_time_bands=bands,
        deli_production_start=production_start,
        weather_stale_hours=_positive("weather_stale_hours", stored.get("weather_stale_hours", DEFAULT_WEATHER_STALE_HOURS)),
    )


def _validate_bands(bands: Any, open_: time, close: time) -> list[int]:
    key = "deli_time_bands"
    if not isinstance(bands, list) or not bands or not all(isinstance(b, int) and not isinstance(b, bool) for b in bands):
        raise SettingsError(key, "時間帯の区切りは開始時(整数)の一覧で指定してください")
    if any(a >= b for a, b in zip(bands, bands[1:])):
        raise SettingsError(key, "時間帯の区切りは昇順にしてください")
    if bands[0] != open_.hour:
        raise SettingsError(key, "最初の時間帯は開店時刻(時)から始めてください")
    if time(bands[-1]) >= close:
        raise SettingsError(key, "時間帯は閉店時刻より前にしてください")
    return list(bands)


def validate_changes(changes: Mapping[str, Any], stored: Mapping[str, Any], departments: Departments) -> dict[str, Any]:
    """変更内容を検証し、保存する値(JSON にできる形)を返す。

    stored は DB に保存済みの値(既定値で補う前)。変更後の全体で整合を確かめる。
    時間帯の区切りを変えて製造開始時刻を指定しない場合は、新しい区切りの既定値を返り値に含める。
    製造開始時刻は一部の時間帯だけの指定も受け付け、保存済みの値に重ねる。
    """
    allowed = allowed_keys(departments)
    for key in changes:
        if key not in allowed:
            raise SettingsError(key, "この設定項目はありません")

    out = dict(changes)
    if "deli_time_bands" in out and "deli_production_start" not in out:
        bands = out["deli_time_bands"]
        if isinstance(bands, list):
            out["deli_production_start"] = _default_production_start(bands)
    elif "deli_production_start" in out and isinstance(out["deli_production_start"], Mapping):
        current = to_flat(resolve(stored, departments))["deli_production_start"]
        out["deli_production_start"] = {**current, **{str(k): v for k, v in out["deli_production_start"].items()}}

    resolve({**stored, **out}, departments)
    return out


def to_flat(s: AppSettings) -> dict[str, Any]:
    """API 応答用の平坦な辞書(内部用キーは含めない)。"""
    flat: dict[str, Any] = {
        "business_hours": {"open": _fmt(s.business_open), "close": _fmt(s.business_close)},
        "deli_time_bands": list(s.deli_time_bands),
        "deli_production_start": {str(b): _fmt(t) for b, t in s.deli_production_start.items()},
        "weather_stale_hours": s.weather_stale_hours,
    }
    for code, v in s.safety_factor.items():
        flat[f"safety_factor.{code}"] = v
    for code, t in s.order_cutoff.items():
        flat[f"order_cutoff.{code}"] = _fmt(t)
    for code, t in s.delivery_time.items():
        flat[f"delivery_time.{code}"] = _fmt(t)
    return flat
