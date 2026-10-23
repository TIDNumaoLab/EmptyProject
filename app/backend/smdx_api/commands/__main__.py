"""管理コマンドの入口。サブコマンドごとに処理を振り分ける。"""
import argparse
import sys

from smdx_api.commands import create_user, fetch_weather_actuals, import_holidays, import_sample


def _safe_console() -> None:
    """表示できない文字は ? に置き換える(Git Bash など標準出力が UTF-8 でない端末で日本語を出しても異常終了しない)。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    _safe_console()
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
