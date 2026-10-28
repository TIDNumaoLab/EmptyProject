import pytest

from smdx_api.settings.service import SETTINGS_CHANGED_KEY, read_internal_datetime
from tests.conftest import jst


def test_settings_requires_login(client):
    assert client.get("/api/settings").status_code == 401


@pytest.mark.db
def test_get_settings_for_staff(client, user_factory, login):
    login(client, user_factory(role="staff"))
    s = client.get("/api/settings").json()["settings"]
    assert s["safety_factor.VEG"] == 1.1 and s["deli_time_bands"] == [10, 11, 14, 17]


@pytest.mark.db
def test_put_settings_manager_only(client, user_factory, login):
    login(client, user_factory(role="staff"))
    res = client.put("/api/settings", json={"settings": {"weather_stale_hours": 2}})
    assert res.status_code == 403
    assert res.json()["detail"] == "この操作を行う権限がありません"


@pytest.mark.db
def test_put_settings_saves_and_rejects_invalid(client, user_factory, login):
    login(client, user_factory(role="manager", departments=()))
    saved = client.put("/api/settings", json={"settings": {"safety_factor.VEG": 1.2}})
    assert saved.json()["settings"]["safety_factor.VEG"] == 1.2
    bad = client.put("/api/settings", json={"settings": {"business_hours": {"open": "25:00", "close": "20:00"}}})
    assert bad.status_code == 422 and bad.json()["detail"][0]["key"] == "business_hours"
    assert client.get("/api/settings").json()["settings"]["business_hours"] == {"open": "10:00", "close": "20:00"}
    assert client.get("/api/settings").json()["settings"]["safety_factor.VEG"] == 1.2


@pytest.mark.db
@pytest.mark.parametrize("body", [
    {"deli_time_bands": [10, 25]},
    {"deli_time_bands": [11, 10, 14]},
])
def test_put_invalid_bands_is_422_not_500(client, user_factory, login, body):
    login(client, user_factory(role="manager", departments=()))
    res = client.put("/api/settings", json={"settings": body})
    assert res.status_code == 422 and res.json()["detail"][0]["key"] == "deli_time_bands"


@pytest.mark.db
def test_put_settings_records_change_for_recalculation(client, user_factory, login, fixed_now, db):
    """計算に関わる値が変わったら最新性判定の日時を記録する(判定時間だけの変更・同じ値では記録しない)。"""
    login(client, user_factory(role="manager", departments=()))
    client.put("/api/settings", json={"settings": {"weather_stale_hours": 2}})
    client.put("/api/settings", json={"settings": {"safety_factor.VEG": 1.1}})   # 既定値と同じ
    assert read_internal_datetime(db, SETTINGS_CHANGED_KEY) is None
    fixed_now.set(jst(2026, 10, 16, 11))
    client.put("/api/settings", json={"settings": {"order_cutoff.VEG": "19:00"}})
    assert read_internal_datetime(db, SETTINGS_CHANGED_KEY) == jst(2026, 10, 16, 11)
    assert "internal.settings_changed_at" not in client.get("/api/settings").json()["settings"]
