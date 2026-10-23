from smdx_api.auth.permissions import Principal, can_access_department


def test_staff_access_only_own_department():
    p = Principal(1, "a", "staff", frozenset({"VEG"}))
    assert can_access_department(p, "VEG")
    assert not can_access_department(p, "FISH")
    assert not can_access_department(p, "veg")


def test_manager_access_all():
    assert can_access_department(Principal(1, "m", "manager", frozenset()), "DELI")
    assert Principal(1, "m", "manager", frozenset()).is_manager
