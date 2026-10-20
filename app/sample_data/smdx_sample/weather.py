"""1時間ごとの擬似気象。

季節の平均気温 16 − 9·cos(2π(通日−15)/365)、日内変動 ±4℃(14時が最高)。
雨の日はマルコフ連鎖(前日が雨なら0.5、晴れなら0.25)で決め、連続3〜10時間を雨にする。
雨の時間は気温−3℃、降水確率70〜90%、降水量0.5〜5mm、天候コード61(2℃未満は雪71)。
それ以外の時間は天候コード1〜3、降水確率0〜20%、降水量0。
"""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from smdx_sample.tz import JST

HOURS = range(0, 24)
COLUMNS = ["observed_time", "weather_code", "temperature", "precipitation_probability", "precipitation"]

RAIN_CODE = 61
SNOW_CODE = 71
SNOW_BELOW = 2.0


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def generate_weather(start: date, end: date, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    rained_yesterday = False
    for day in _days(start, end):
        rainy_day = rng.random() < (0.5 if rained_yesterday else 0.25)
        rained_yesterday = rainy_day
        rain_hours: set[int] = set()
        if rainy_day:
            length = int(rng.integers(3, 11))
            first = int(rng.integers(0, 24 - length + 1))
            rain_hours = set(range(first, first + length))
        doy = day.timetuple().tm_yday
        day_mean = 16 - 9 * np.cos(2 * np.pi * (doy - 15) / 365) + rng.normal(0, 2)
        dry_codes = rng.choice([1, 2, 3], size=24, p=[0.4, 0.35, 0.25])
        for h in HOURS:
            temp = day_mean + 4 * np.cos(2 * np.pi * (h - 14) / 24)
            if h in rain_hours:
                temp -= 3
                code = SNOW_CODE if temp < SNOW_BELOW else RAIN_CODE
                prob = rng.uniform(70, 90)
                precip = rng.uniform(0.5, 5)
            else:
                code = int(dry_codes[h])
                prob = rng.uniform(0, 20)
                precip = 0.0
            rows.append((datetime(day.year, day.month, day.day, h, tzinfo=JST), code,
                         round(float(temp), 1), round(float(prob)), round(float(precip), 1)))
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["weather_code"] = df["weather_code"].astype("int64")
    return df
