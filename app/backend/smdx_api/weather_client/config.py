"""気象APIの設定(環境変数)。

本体の AppConfig と同じ項目名・既定値を持つ。管理コマンド(fetch_weather_actuals)は SESSION_SECRET を
必要としないため、こちらを使う。読み方は本体と同じ(環境変数 → .env → 既定値)。
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_LATITUDE = 35.6895
DEFAULT_LONGITUDE = 139.6917


class WeatherConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    weather_api_base_url: str = DEFAULT_FORECAST_URL
    weather_api_archive_url: str = DEFAULT_ARCHIVE_URL
    weather_api_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    store_latitude: float = DEFAULT_LATITUDE
    store_longitude: float = DEFAULT_LONGITUDE
