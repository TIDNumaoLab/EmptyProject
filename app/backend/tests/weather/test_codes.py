import pytest

from smdx_api.weather_client.codes import weather_label


@pytest.mark.parametrize("code,label", [
    (0, "快晴"), (1, "晴れ"), (2, "晴れ"), (3, "曇り"), (45, "霧"), (48, "霧"), (51, "小雨"), (53, "小雨"),
    (55, "雨"), (61, "雨"), (63, "雨"), (65, "大雨"), (71, "雪"), (73, "雪"), (75, "大雪"),
    (80, "にわか雨"), (81, "にわか雨"), (82, "激しいにわか雨"), (95, "雷雨"), (96, "雷雨"), (99, "雷雨"),
    (4, "不明"), (77, "不明"), (None, "不明"),
])
def test_weather_label(code, label):
    assert weather_label(code) == label
