"""気象の過去実績の取得(再学習の前に実行する)。"""
import argparse
import sys
from datetime import date

from smdx_api.commands import open_session
from smdx_api.weather_client.client import OpenMeteoClient, WeatherUnavailable
from smdx_api.weather_client.config import WeatherConfig
from smdx_api.weather_client.service import fetch_weather_actuals


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("fetch_weather_actuals", help="気象の過去実績を取得して保存する")
    p.add_argument("--start", required=True, type=date.fromisoformat, help="開始日 YYYY-MM-DD")
    p.add_argument("--end", required=True, type=date.fromisoformat, help="終了日 YYYY-MM-DD")
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    if args.end < args.start:
        print("終了日は開始日以降にしてください", file=sys.stderr)
        return 1
    client = OpenMeteoClient.from_config(WeatherConfig())
    with open_session() as db:
        try:
            n = fetch_weather_actuals(db, client, args.start, args.end)
        except WeatherUnavailable as e:
            print(e.reason, file=sys.stderr)
            return 1
        db.commit()
    print(f"気象の過去実績を {n} 時間分保存しました({args.start}〜{args.end})")
    return 0
