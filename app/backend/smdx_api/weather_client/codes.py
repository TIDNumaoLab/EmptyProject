"""WMO 天候コードと表示区分の対応(詳細設計書「天候コード(WMO)と表示区分の対応」)。"""

_LABELS = {
    0: "快晴",
    1: "晴れ", 2: "晴れ",
    3: "曇り",
    45: "霧", 48: "霧",
    51: "小雨", 53: "小雨",
    55: "雨", 61: "雨", 63: "雨",
    65: "大雨",
    71: "雪", 73: "雪",
    75: "大雪",
    80: "にわか雨", 81: "にわか雨",
    82: "激しいにわか雨",
    95: "雷雨", 96: "雷雨", 99: "雷雨",
}

UNKNOWN = "不明"


def weather_label(code: int | None) -> str:
    return _LABELS.get(code, UNKNOWN) if code is not None else UNKNOWN
