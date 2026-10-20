"""管理コマンドの入口。サブコマンドごとに処理を振り分ける。"""
import argparse
import sys

from smdx_api.commands import create_user, fetch_weather_actuals, import_holidays, import_sample


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m smdx_api.commands", description="スーパーマーケットDX 管理コマンド")
    sub = parser.add_subparsers(dest="command")
    create_user.add_parser(sub)
    import_holidays.add_parser(sub)
    fetch_weather_actuals.add_parser(sub)
    import_sample.add_parser(sub)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
