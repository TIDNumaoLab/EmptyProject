from collections import Counter

from smdx_sample.products import BAND_SHARES, PRODUCTS


def test_products_breakdown():
    by_dept = Counter(p.department_code for p in PRODUCTS)
    assert by_dept == {"VEG": 6, "FISH": 4, "DELI": 5}
    assert len({p.code for p in PRODUCTS}) == 15
    assert all(p.lead_time_days == (0 if p.department_code == "DELI" else 1) for p in PRODUCTS)
    assert all(not p.can_carry_over for p in PRODUCTS if p.department_code in ("FISH", "DELI"))
    assert all(p.can_carry_over for p in PRODUCTS if p.department_code == "VEG")
    assert all(p.order_unit == 1 for p in PRODUCTS if p.department_code == "DELI")


def test_band_shares_cover_deli_and_sum_to_one():
    assert set(BAND_SHARES) == {p.code for p in PRODUCTS if p.department_code == "DELI"}
    for shares in BAND_SHARES.values():
        assert sorted(shares) == [10, 11, 14, 17] and abs(sum(shares.values()) - 1) < 1e-9
    assert BAND_SHARES["DELI-003"] == {10: 0.1, 11: 0.5, 14: 0.15, 17: 0.25}
