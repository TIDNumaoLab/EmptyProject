"""サンプルの祝日・行事日。

祝日は内閣府の規則(固定日・ハッピーマンデー・春分/秋分の近似式・振替休日・国民の休日)で計算する。
2020年以降の制度を前提とする(判断 2-3)。行事日は固定の月日。
"""
from datetime import date, timedelta

_FIXED = {
    (1, 1): "元日",
    (2, 11): "建国記念の日",
    (2, 23): "天皇誕生日",
    (4, 29): "昭和の日",
    (5, 3): "憲法記念日",
    (5, 4): "みどりの日",
    (5, 5): "こどもの日",
    (8, 11): "山の日",
    (11, 3): "文化の日",
    (11, 23): "勤労感謝の日",
}
# (月, 第n月曜日): 名称
_HAPPY_MONDAY = {(1, 2): "成人の日", (7, 3): "海の日", (9, 3): "敬老の日", (10, 2): "スポーツの日"}

_EVENTS = {
    (2, 3): "節分",
    (3, 3): "ひな祭り",
    (7, 24): "土用の丑の日",  # 年により異なるため近似
    (12, 24): "クリスマスイブ",
    (12, 31): "大晦日",
}


def _nth_monday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (7 - first.weekday()) % 7  # 最初の月曜日までの日数(月曜=0)
    return first + timedelta(days=offset + 7 * (n - 1))


def _equinoxes(year: int) -> dict[date, str]:
    y = year - 1980
    spring = int(20.8431 + 0.242194 * y - int(y / 4))
    autumn = int(23.2488 + 0.242194 * y - int(y / 4))
    return {date(year, 3, spring): "春分の日", date(year, 9, autumn): "秋分の日"}


def _year_holidays(year: int) -> dict[date, str]:
    base = {date(year, m, d): name for (m, d), name in _FIXED.items()}
    base.update({_nth_monday(year, m, n): name for (m, n), name in _HAPPY_MONDAY.items()})
    base.update(_equinoxes(year))

    result = dict(base)
    # 振替休日: 祝日が日曜なら、その後で最初の祝日でない日
    for d in sorted(base):
        if d.weekday() == 6:
            sub = d + timedelta(days=1)
            while sub in result:
                sub += timedelta(days=1)
            result[sub] = "振替休日"
    # 国民の休日: 前日と翌日が祝日(振替休日を除く)に挟まれた平日
    for d in sorted(base):
        mid = d + timedelta(days=1)
        if mid + timedelta(days=1) in base and mid not in result and mid.weekday() != 6:
            result[mid] = "国民の休日"
    return result


def japanese_holidays(start: date, end: date) -> dict[date, str]:
    out: dict[date, str] = {}
    for year in range(start.year, end.year + 1):
        out.update({d: n for d, n in _year_holidays(year).items() if start <= d <= end})
    return dict(sorted(out.items()))


def event_days(start: date, end: date) -> dict[date, str]:
    out = {}
    for year in range(start.year, end.year + 1):
        for (m, d), name in _EVENTS.items():
            day = date(year, m, d)
            if start <= day <= end:
                out[day] = name
    return dict(sorted(out.items()))
