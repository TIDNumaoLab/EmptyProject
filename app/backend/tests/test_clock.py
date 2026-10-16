from datetime import timedelta

from smdx_api import clock


def test_now_is_tokyo_aware():
    n = clock.now()
    assert n.tzinfo is not None and n.utcoffset() == timedelta(hours=9)
