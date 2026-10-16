from pathlib import Path
from tools.check_docs import (find_forbidden, missing_headings, extract_ids,
                              undefined_ids, main, APPENDIX_HEADING)


def test_forbidden_only_before_appendix():
    text = f"# 題\n本文は実装済です\n{APPENDIX_HEADING}\n試作では手動実行\n"
    assert find_forbidden(text) == [(2, "実装済")]


def test_missing_headings():
    assert missing_headings("## 目的\n## 機能要件\n", ["## 目的", "## 非機能要件"]) == ["## 非機能要件"]


def test_extract_ids():
    assert extract_ids("F-01 と R-06、F-1 と XF-02X は対象外") == {"F-01", "R-06"}


def test_undefined_ids():
    assert undefined_ids({"F-21", "F-01", "R-07"}, {"F-01"}) == ["F-21", "R-07"]


def test_main_reads_japanese_files(tmp_path: Path):
    for name in ["要件定義書.md", "基本設計書.md", "詳細設計書.md"]:
        (tmp_path / name).write_text("# 文書\nF-01\n", encoding="utf-8")
    assert main(tmp_path) == 1   # 必須見出しが無いので問題あり
