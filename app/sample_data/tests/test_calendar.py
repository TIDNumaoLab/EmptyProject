from datetime import date

from smdx_sample.calendar import event_days, japanese_holidays

HOLIDAYS_2026 = {date(2026, m, d) for m, d in [
    (1, 1), (1, 12), (2, 11), (2, 23), (3, 20), (4, 29), (5, 3), (5, 4), (5, 5), (5, 6),
    (7, 20), (8, 11), (9, 21), (9, 22), (9, 23), (10, 12), (11, 3), (11, 23),
]}


def test_holidays_2026():
    h = japanese_holidays(date(2026, 1, 1), date(2026, 12, 31))
    assert set(h) == HOLIDAYS_2026
    assert h[date(2026, 5, 6)] == "振替休日"
    assert h[date(2026, 9, 22)] == "国民の休日"
    assert h[date(2026, 3, 20)] == "春分の日"


def test_holidays_2025_substitute_and_equinox():
    h = japanese_holidays(date(2025, 1, 1), date(2025, 12, 31))
    # 2025-02-23(天皇誕生日)は日曜 → 2/24 が振替休日。秋分の日は 9/23
    assert h[date(2025, 2, 24)] == "振替休日"
    assert h[date(2025, 9, 23)] == "秋分の日"
    assert len(h) == 19


def test_range_is_inclusive_and_clipped():
    h = japanese_holidays(date(2026, 1, 2), date(2026, 2, 11))
    assert set(h) == {date(2026, 1, 12), date(2026, 2, 11)}


def test_events():
    ev = event_days(date(2026, 1, 1), date(2026, 12, 31))
    assert ev[date(2026, 7, 24)] == "土用の丑の日"
    assert set(ev) == {date(2026, 2, 3), date(2026, 3, 3), date(2026, 7, 24), date(2026, 12, 24), date(2026, 12, 31)}
