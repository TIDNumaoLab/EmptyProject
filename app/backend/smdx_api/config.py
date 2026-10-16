"""環境変数からの設定読込(詳細設計書「設定項目」の環境変数)。"""
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    # model_daily_path などの項目名が pydantic の予約名(model_)と重ならないようにする
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=("settings_",)
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5432/supermarket_dx"
    weather_api_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_api_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    weather_api_timeout_seconds: float = 10
    store_latitude: float = 35.6895
    store_longitude: float = 139.6917
    model_daily_path: str = "models/daily.joblib"
    model_time_band_path: str = "models/time_band.joblib"
    # カンマ区切りの文字列で受け、リストに分割する。
    # str との共用型にすると、JSON として読めない値でもエラーにせず検証関数へ渡される
    cors_allow_origins: list[str] | str = ["http://localhost:5173"]
    session_secret: str
    session_cookie_secure: bool = False
    # 最後の操作からこの時間でログアウトになる(SessionMiddleware が応答ごとに Cookie を出し直す)
    session_max_age_hours: float = Field(default=3, gt=0)
    tz: str = "Asia/Tokyo"

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
