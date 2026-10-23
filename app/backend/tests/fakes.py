"""試験用の偽の気象クライアント(Open-Meteo を実際に呼ばない)。段階3以降の試験でも使う。"""
from datetime import date, datetime, timedelta

from smdx_api.clock import JST
from smdx_api.weather_client.client import HourlyWeather, WeatherUnavailable


def hourly_rows(start: date, end: date, code: int = 1, temperature: float = 20.0,
                probability: float | None = 10.0, precipitation: float | None = 0.0) -> list[HourlyWeather]:
    rows = []
    day = start
    while day <= end:
        for h in range(24):
            rows.append(HourlyWeather(datetime(day.year, day.month, day.day, h, tzinfo=JST), code, temperature, probability, precipitation))
        day += timedelta(days=1)
    return rows


class FakeWeatherClient:
    """指定期間の1時間ごとの行(既定は晴れ・20℃)を返し、呼び出し回数を数える。"""

    def __init__(self, code: int = 1, temperature: float = 20.0, probability: float = 10.0, precipitation: float = 0.0) -> None:
        self.code, self.temperature, self.probability, self.precipitation = code, temperature, probability, precipitation
        self.calls = 0

    def fetch_forecast(self, start: date, end: date) -> list[HourlyWeather]:
        self.calls += 1
        return hourly_rows(start, end, self.code, self.temperature, self.probability, self.precipitation)

    def fetch_archive(self, start: date, end: date) -> list[HourlyWeather]:
        self.calls += 1
        return hourly_rows(start, end, self.code, self.temperature, None, self.precipitation)


class FailingWeatherClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_forecast(self, start: date, end: date) -> list[HourlyWeather]:
        self.calls += 1
        raise WeatherUnavailable("試験用の失敗")

    def fetch_archive(self, start: date, end: date) -> list[HourlyWeather]:
        self.calls += 1
        raise WeatherUnavailable("試験用の失敗")
