"""設定値の既定値・解決・検証(DB不要)。"""
from datetime import time

import pytest

from smdx_api.settings.values import SettingsError, resolve, to_flat, validate_changes

DEPTS = [("VEG", "order"), ("FISH", "order"), ("DELI", "production")]


def test_defaults():
    s = resolve({}, DEPTS)
    assert (s.business_open, s.business_close) == (time(10), time(20))
    assert s.safety_factor == {"VEG": 1.1, "FISH": 1.1, "DELI": 1.1}
    assert s.order_cutoff == {"VEG": time(20), "FISH": time(20)}
    assert s.delivery_time == {"VEG": time(10), "FISH": time(10)}
    assert s.deli_time_bands == [10, 11, 14, 17]
    assert s.deli_production_start == {10: time(9), 11: time(10), 14: time(13), 17: time(16)}
    assert s.weather_stale_hours == 3
    assert s.band_end(17) == time(20) and s.band_end(11) == time(14)


def test_cutoff_default_follows_stored_close():
    s = resolve({"business_hours": {"open": "09:00", "close": "21:00"}}, DEPTS)
    assert s.order_cutoff["VEG"] == time(21) and s.delivery_time["VEG"] == time(9)
    # 既定の時間帯の区切りは「開店〜11時」なので、最初の区切りも開店時に合わせる
    assert s.deli_time_bands == [9, 11, 14, 17]


def test_stored_values_override_defaults():
    s = resolve({"safety_factor.VEG": 1.3, "order_cutoff.FISH": "18:30", "weather_stale_hours": 2}, DEPTS)
    assert s.safety_factor["VEG"] == 1.3 and s.safety_factor["FISH"] == 1.1
    assert s.order_cutoff["FISH"] == time(18, 30)
    assert s.weather_stale_hours == 2


@pytest.mark.parametrize("changes,key", [
    ({"business_hours": {"open": "25:00", "close": "20:00"}}, "business_hours"),
    ({"business_hours": {"open": "20:00", "close": "10:00"}}, "business_hours"),
    ({"deli_time_bands": [11, 10, 14]}, "deli_time_bands"),
    ({"deli_time_bands": [9, 11, 14]}, "deli_time_bands"),       # 開店(10時)より前
    ({"deli_time_bands": [10, 11, 20]}, "deli_time_bands"),      # 閉店時以降
    ({"safety_factor.VEG": 0}, "safety_factor.VEG"),
    ({"order_cutoff.DELI": "18:00"}, "order_cutoff.DELI"),       # production 部門には無いキー
    ({"unknown_key": 1}, "unknown_key"),
    ({"deli_production_start": {"11": "11:30"}}, "deli_production_start"),  # 時間帯の開始より後
    ({"weather_stale_hours": "x"}, "weather_stale_hours"),
    ({"deli_time_bands": [10, 25]}, "deli_time_bands"),           # 時は 0〜23
    ({"safety_factor.VEG": float("nan")}, "safety_factor.VEG"),    # JSON に保存できない値
    ({"weather_stale_hours": float("inf")}, "weather_stale_hours"),
])
def test_invalid_changes_raise(changes, key):
    with pytest.raises(SettingsError) as e:
        validate_changes(changes, {}, DEPTS)
    assert e.value.key == key


def test_band_change_recomputes_production_start():
    out = validate_changes({"deli_time_bands": [10, 12, 16]}, {}, DEPTS)
    assert out["deli_time_bands"] == [10, 12, 16]
    assert out["deli_production_start"] == {"10": "09:00", "12": "11:00", "16": "15:00"}


def test_business_hours_change_with_default_bands_is_valid():
    # 時間帯の区切りを保存していなければ、既定の区切りが新しい開店時刻に追従する
    out = validate_changes({"business_hours": {"open": "09:00", "close": "21:00"}}, {}, DEPTS)
    assert out == {"business_hours": {"open": "09:00", "close": "21:00"}}


def test_partial_production_start_is_merged():
    out = validate_changes({"deli_production_start": {"11": "10:30"}}, {}, DEPTS)
    assert out["deli_production_start"] == {"10": "09:00", "11": "10:30", "14": "13:00", "17": "16:00"}


def test_flat_has_all_keys_and_excludes_internal():
    flat = to_flat(resolve({}, DEPTS))
    assert flat["business_hours"] == {"open": "10:00", "close": "20:00"}
    assert flat["order_cutoff.VEG"] == "20:00" and "order_cutoff.DELI" not in flat
    assert flat["deli_production_start"] == {"10": "09:00", "11": "10:00", "14": "13:00", "17": "16:00"}
    assert all(not k.startswith("internal.") for k in flat)
