"""手動テスト(テスト項目一覧「3. 結合テスト(業務シナリオ・手動)」)で取り込む CSV を作る。

POS・在庫の日付は実行日(日本時間)に合わせる必要があるため、固定のファイルではなく実行のたびに作る。
土台のデータ(400日分)は研究用サンプルデータ生成(smdx_sample)で作り、このスクリプトはその上に重ねる分だけを作る。

使い方(リポジトリのルートで実行):
    app/.venv/Scripts/python テスト/手動テストデータ/make_data.py [--date YYYY-MM-DD] [--time HH:MM]

--date・--time を省略すると現在の日本時間を使う。出力先は テスト/手動テストデータ/output/(Git に含めない)。
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
OUT = Path(__file__).resolve().parent / "output"

PRODUCTS_HEADER = ["product_code", "product_name", "department_code", "order_unit", "lead_time_days",
                   "can_carry_over", "cost_price", "selling_price"]
VEG_CODES = ["VEG-001", "VEG-002", "VEG-003", "VEG-004", "VEG-005", "VEG-006"]


def write_csv(name: str, header: list[str], rows: list[list[object]], encoding: str = "utf-8") -> Path:
    path = OUT / name
    with path.open("w", encoding=encoding, newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def write_text(name: str, text: str, encoding: str = "utf-8") -> Path:
    path = OUT / name
    path.write_bytes(text.encode(encoding))
    return path


def make(today: date, now: time) -> list[Path]:
    yesterday = today - timedelta(days=1)
    y = yesterday.isoformat()
    # 在庫の基準日時は現在の5分前(未来の基準日時の在庫は使われないため)
    based = (datetime.combine(today, now, JST) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
    files = []

    # A. 商品マスタの追加(店長が取り込む)。正しい行2件 + 不正な行5件
    files.append(write_csv("A_商品マスタ_追加とエラー行.csv", PRODUCTS_HEADER, [
        ["VEG-101", "新じゃが(新商品)", "VEG", 1, 1, 1, 60, 98],     # 販売実績なし → NO_HISTORY
        ["VEG-102", "かぼちゃ(LT2日)", "VEG", 2, 2, 1, 150, 248],    # リードタイム2日 → 納品日が1日遅い
        ["VEG-103", "", "VEG", 1, 1, 1, "", ""],                      # 商品名なし
        ["VEG-104", "れんこん", "VEG", 0, 1, 1, "", ""],              # 発注単位0
        ["VEG-105", "ごぼう", "VEG", 1, -1, 1, "", ""],               # リードタイムが負
        ["VEG-106", "しょうが", "VEG", 1, 1, 2, "", ""],              # 持越可否が0/1でない
        ["XXX-001", "不明部門の商品", "XXX", 1, 1, 1, "", ""],        # 未登録の部門
    ]))

    # B. 青果の POS(前日分)。正しい行 + 不正な行
    rows: list[list[object]] = [[y, "", c, 12] for c in VEG_CODES if c != "VEG-002"]
    rows += [
        [y, "10:15", "VEG-002", 3],          # 時刻つき
        [y, "", "VEG-002", 9],               # 同じ日・商品に日計が混在 → VEG-002 の行はすべてエラー
        [y, "", "VEG-999", 5],               # 未登録の商品
        [y, "", "FISH-001", 5],              # 取込先(青果)と違う部門の商品
        [y, "", "VEG-003", -1],              # 負の数量
        [yesterday.strftime("%Y/%m/%d"), "", "VEG-004", 5],  # 日付の形式違い
        [y, "", "VEG-005", ""],              # 数量なし
    ]
    files.append(write_csv("B_POS_青果_前日_エラー行入り.csv", ["sales_date", "sales_time", "product_code", "quantity"], rows))

    # C. 在庫(当日)。青果のみ。鮮魚は入れずに NO_INVENTORY を確かめる
    qty = {"VEG-001": 8, "VEG-002": 5, "VEG-003": 3, "VEG-004": 10, "VEG-005": 20, "VEG-006": 6,
           "VEG-101": 0, "VEG-102": 2}
    files.append(write_csv("C_在庫_青果_当日.csv", ["based_at", "product_code", "quantity"],
                           [[based, c, q] for c, q in qty.items()]))

    # D. 廃棄(前日)。鮮魚
    files.append(write_csv("D_廃棄_鮮魚_前日.csv", ["waste_date", "product_code", "quantity"],
                           [[y, "FISH-001", 2], [y, "FISH-003", 4]]))

    # E. 取込全体が拒否されるファイル(すべて 422、取込履歴は残らない)
    files.append(write_text("E1_拒否_必須列なし.csv", f"sales_date,product_code\n{y},VEG-001\n"))
    files.append(write_text("E2_拒否_見出しの重複.csv", f"sales_date,sales_time,product_code,quantity,quantity\n{y},,VEG-001,1,1\n"))
    files.append(write_text("E3_拒否_閉じていない引用符.csv", f'sales_date,sales_time,product_code,quantity\n{y},,"VEG-001,1\n{y},,VEG-002,1\n'))
    # Excel で保存し直したときと同じ Shift_JIS(UTF-8 で読めない)
    files.append(write_csv("E4_拒否_ShiftJIS.csv", PRODUCTS_HEADER, [["VEG-107", "みょうが", "VEG", 1, 1, 1, "", ""]],
                           encoding="cp932"))

    # F. 引用符の中の改行・BOMつき UTF-8(取り込める)
    files.append(write_text("F_BOMつき_引用符内の改行.csv",
                            "product_code,product_name,department_code,order_unit,lead_time_days,can_carry_over,cost_price,selling_price\n"
                            '"VEG-108","ズッキーニ\n(2行の名前)",VEG,1,1,1,,\n', encoding="utf-8-sig"))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", type=date.fromisoformat, help="テストを行う日(既定は今日。日本時間)")
    parser.add_argument("--time", type=time.fromisoformat, help="在庫の基準にする現在時刻 HH:MM(既定は今)")
    args = parser.parse_args()
    now = datetime.now(JST)
    today = args.date or now.date()
    OUT.mkdir(exist_ok=True)
    files = make(today, args.time or now.time().replace(second=0, microsecond=0))
    print(f"テストを行う日: {today.isoformat()}(サンプルデータの --end-date には {(today - timedelta(days=1)).isoformat()} を指定)")
    for f in files:
        print(f"  {f.relative_to(OUT.parent.parent.parent)}")


if __name__ == "__main__":
    main()
