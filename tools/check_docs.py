"""設計文書(要件定義書・基本設計書・詳細設計書)の機械チェック。

- 付録より前の本文に試作の実装状況を表す禁止語が無いこと
- 必須見出しがそろっていること
- 基本設計書・詳細設計書が要件定義書で定義されていない機能ID/業務要件IDを参照していないこと
"""
import re
import sys
from pathlib import Path

FORBIDDEN_TERMS = ["実装済", "実装状況", "未実装", "prototype/", "試作では"]
APPENDIX_HEADING = "## 付録 試作(prototype)からの変更点"

DOC_NAMES = ["要件定義書.md", "基本設計書.md", "詳細設計書.md"]

REQUIRED_HEADINGS = {
    "要件定義書.md": [
        "## 改訂履歴",
        "## プロジェクト概要・背景",
        "## 目的・ゴール",
        "## スコープ(対象範囲)",
        "## ステークホルダー",
        "## 利用者と権限",
        "## 業務要件",
        "### As-Is",
        "### 部門別の業務",
        "### 業務要件一覧",
        "### 業務フロー",
        "### イベント",
        "## 機能要件",
        "## 非機能要件",
        "## 成功基準・評価方法",
        "## トレーサビリティ",
        "## 制約条件",
        "### 前提条件",
        "### リスク",
        "## ヒアリング確認項目",
        "## スケジュール",
        APPENDIX_HEADING,
        "### 機能IDの対応(第2版→第3版)",
    ],
    "基本設計書.md": [
        "## 改訂履歴",
        "## 基本設計書の位置づけ",
        "## システム構成",
        "## 技術スタック",
        "## 実行環境構成",
        "### ローカル開発環境",
        "### 評価環境(AWS)",
        "## 機能構成と処理の流れ",
        "### 事前準備: モデルの作成",
        "### データ取込",
        "### 提案の作成・再計算",
        "### 確認・修正・承認",
        "### 欠損時の扱い",
        "## 画面構成",
        "## データ設計方針",
        "## 外部連携・インターフェース設計方針",
        "## セキュリティ設計方針",
        "## 運用・保守設計方針",
        "## 今後の進め方",
        APPENDIX_HEADING,
    ],
    "詳細設計書.md": [
        "## 改訂履歴",
        "## 詳細設計書の位置づけ",
        "## モジュール構成",
        "## 需要予測モデル",
        "## 予測モデルのインターフェース定義",
        "## 提案作成処理",
        "## 発注数・製造数の計算",
        "## 欠損時の扱い",
        "## 提案の状態遷移",
        "## API仕様",
        "## 画面詳細設計",
        "## データ項目定義",
        "## 標準取込形式",
        "## 研究用サンプルデータ生成仕様",
        "## 外部API仕様(気象データ)",
        "## 設定項目",
        "## テスト・評価方針",
        "## 既知の課題・未確定事項",
        APPENDIX_HEADING,
    ],
}

_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])[FR]-\d{2}(?![A-Za-z0-9])")


def find_forbidden(text: str) -> list:
    """付録見出しより前の行で禁止語を含むものを (行番号, 禁止語) で返す。"""
    found = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.startswith(APPENDIX_HEADING):
            break
        for term in FORBIDDEN_TERMS:
            if term in line:
                found.append((line_no, term))
    return found


def missing_headings(text: str, required: list) -> list:
    lines = text.splitlines()
    return [h for h in required if not any(line.startswith(h) for line in lines)]


def extract_ids(text: str) -> set:
    return set(_ID_PATTERN.findall(text))


def undefined_ids(referenced: set, defined: set) -> list:
    return sorted(referenced - defined)


def main(root: Path) -> int:
    texts = {name: (root / name).read_text(encoding="utf-8") for name in DOC_NAMES}
    defined = extract_ids(texts["要件定義書.md"])
    problems = []
    for name, text in texts.items():
        for line_no, term in find_forbidden(text):
            problems.append(f"{name}:{line_no}: 禁止語「{term}」")
        for heading in missing_headings(text, REQUIRED_HEADINGS[name]):
            problems.append(f"{name}: 見出し不足「{heading}」")
        if name != "要件定義書.md":
            for id_ in undefined_ids(extract_ids(text), defined):
                problems.append(f"{name}: 未定義ID {id_}")
    for problem in problems:
        print(problem)
    print(f"問題 {len(problems)} 件")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(Path(__file__).resolve().parents[1]))
