# 要件定義書・基本設計書・詳細設計書 第3版改訂 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 要件定義書.md・基本設計書.md・詳細設計書.md を、設計仕様に沿った To-Be 仕様の第3版へ書き直す。

**Architecture:** 先に文書チェック用の小さなスクリプト(禁止語・必須見出し・ID参照)をTDDで作り、各文書の改訂タスクはそのチェックの通過を「テスト」とする。文書は 要件定義書 → 基本設計書 → 詳細設計書(2分割)の順に改訂し、最後に文書間の整合を確認する。

**Tech Stack:** Markdown、Python 3.9(既存のグローバル環境)+ pytest 8

**Spec:** `docs/superpowers/specs/2026-10-16-document-brushup-design.md`(以下「仕様」。§番号は仕様の節)

## Global Constraints

- 出力は .md のみ。.docx は作成・更新しない。
- 改訂対象はプロジェクトルート直下の `要件定義書.md`・`基本設計書.md`・`詳細設計書.md`(ファイル名・場所は変えない)。
- ルート直下の .md/.docx は `.gitignore`(`/*.md`)で追跡対象外。文書そのものはコミットされない。コミットするのは `tools/` と計画・仕様だけ。
- 第2版は改訂前に `旧版_20261016/` へコピーして残す(既存の `旧版_20261009/` と同じ扱い)。
- 各文書の冒頭行: `作成日: 2026-10-09 ／ 改訂日: <作業日 YYYY-MM-DD>(第3版) ／ 作成: NECO3`。改訂履歴に `| 3.0 | <作業日> | 設計仕様(2026-10-16)に基づき To-Be 仕様として全面改訂 |` を追加する。
- 本文(付録より前)には試作の実装状況を書かない。禁止語: `実装済`・`実装状況`・`未実装`・`prototype/`・`試作では`。試作との違いは各文書末尾の `## 付録 試作(prototype)からの変更点` にだけ書く。
- 数値・用語は仕様と一字一句揃える: 安全係数 既定1.1(部門別)、再計算の判定時間 既定3時間、提案作成処理 対象20品で1分以内、画面表示2秒以内、対象日は当日〜15日先、気象APIタイムアウト10秒、Python 3.11、日時は Asia/Tokyo、主指標 WAPE、目標「WAPE 20%以上改善」「作業時間50%削減」「廃棄数10%削減」「不安・信頼が平均1ポイント改善」「提案採用率70%以上」。
- 機能IDは仕様 §3 の F-01〜F-20、業務要件IDは仕様 §2.3 の R-01〜R-06 をそのまま使う。
- 文体は第2版に合わせる(である調、表中心、`> **【確認事項】**` の注記形式)。未確定事項は「仮の前提+ヒアリング項目」として書き、設計を止めない。
- 作業者はこのPCの Windows 環境。Python で日本語ファイルを読むときは必ず `encoding="utf-8"` を指定する(既定の cp1252 では失敗する)。

## Review Focus

1. **文書間の数値・名称の食い違い**: 同じ値(1分・3時間・1.1・15日・状態名「未承認/承認済み/確定/期限切れ」)が3文書で異なる → Task 6 で一覧照合する。
2. **第2版の機能IDとの混同**: 第2版の F-01(需要予測実行)と第3版の F-01(商品マスタ取込)は意味が違う。読者が旧版と並べて読むと誤解する → Task 2 の付録に旧→新のID対応表を入れる。
3. **試作の記述の残り**: 第2版の文章を流用したときに試作の挙動が本文に残る → `tools/check_docs.py` の禁止語チェックで検出する。
4. **基本設計書と詳細設計書で画面・APIの一覧がずれる**: 一方にだけある画面やAPIが出る → 本計画の「画面一覧」「API一覧」を両文書の唯一の出典とし、Task 6 で照合する。
5. **Windows での文字化け**: チェックスクリプトが日本語ファイル名・本文で落ちる → Task 1 のテストで日本語ファイルを読む。

## 共通の設計決定(Task 3〜5 が参照する唯一の出典)

### 画面一覧
| 画面 | URL | 利用者 | 主な機能 |
|---|---|---|---|
| ログイン | /login | 全員 | F-16 |
| 発注(生鮮) | /orders | 担当者・店長 | F-08, F-10, F-11, F-12。部門・対象日・状態で絞り込み |
| 製造計画(惣菜) | /production | 担当者・店長 | F-08, F-10, F-11, F-12。陳列残数入力 |
| 承認済み発注リスト | /orders/approved | 担当者・店長 | F-13(印刷用レイアウト) |
| データ取込 | /imports | 担当者・店長 | F-01〜F-03 のCSVアップロード、取込履歴 |
| 在庫入力 | /inventory | 担当者・店長 | F-03 手入力 |
| 特売・チラシ | /promotions | 担当者・店長 | F-06 |
| カレンダー | /calendar | 店長 | F-05 |
| 設定 | /settings | 店長 | F-17 |
| 予測と実績の比較(Should) | /review | 担当者・店長 | F-14 |

### API一覧
| メソッド | パス | 概要 |
|---|---|---|
| GET | /health | 稼働確認 |
| POST | /api/auth/login, /api/auth/logout | ログイン・ログアウト |
| GET | /api/me | ログイン中の利用者・役割・所属部門 |
| POST | /api/imports/{kind} | CSV取込(kind: products / pos / inventory / waste) |
| GET | /api/imports | 取込履歴 |
| PUT | /api/inventory | 在庫の手入力(基準日時と商品別在庫数) |
| GET, POST, PATCH, DELETE | /api/promotions | 特売・チラシ |
| GET, POST, DELETE | /api/calendar | 祝日・行事日(更新は店長) |
| GET | /api/proposals | 提案一覧(部門・対象日・状態)。最新性判定を行い、必要なら再計算ジョブを開始して既存提案と鮮度・ジョブ状態を返す |
| POST | /api/proposals/recalculate | 手動再計算(部門・対象日) |
| GET | /api/proposals/jobs/{id} | 再計算ジョブの進捗 |
| PATCH | /api/proposals/{id} | 数量修正(数量・修正理由) |
| POST | /api/proposals/{id}/approve | 個別承認 |
| POST | /api/proposals/approve-bulk | 一括承認(警告付きは除外し、除外したIDを返す) |
| POST | /api/proposals/{id}/cancel-approval | 承認取消(期限前のみ) |
| POST | /api/proposals/{id}/adopt-recalculated | 再計算後の提案値の採用 |
| PUT | /api/production/display-stock | 惣菜の陳列残数入力(対象日・入力時刻・商品別残数) |
| GET | /api/orders/approved | 承認済み発注リスト |
| GET, PUT | /api/settings | 設定(更新は店長) |
| GET | /api/products | 商品一覧 |
| GET | /api/review/accuracy | 予測と実績の比較(Should) |

### テーブル一覧(詳細設計書で項目を定義する)
departments, users, user_departments, products, pos_sales, inventory_snapshots, waste_records, display_stock_entries, weather_forecasts, weather_actuals, calendar_days, promotions, forecasts, proposals, proposal_histories, proposal_jobs, import_logs, settings

発注残は proposals のうち状態「確定」かつ納品日が未到来のものから導出し、専用テーブルは作らない。

---

### Task 1: 文書チェックスクリプト

**Files:**
- Create: `tools/check_docs.py`
- Test: `tools/tests/test_check_docs.py`

**Interfaces:**
- Produces:
  - `FORBIDDEN_TERMS: list[str]` = `["実装済", "実装状況", "未実装", "prototype/", "試作では"]`
  - `APPENDIX_HEADING: str` = `"## 付録 試作(prototype)からの変更点"`
  - `REQUIRED_HEADINGS: dict[str, list[str]]`(キーは文書ファイル名。値は Task 2〜5 の見出し一覧をそのまま転記)
  - `find_forbidden(text: str) -> list[tuple[int, str]]` — 付録見出しより前の行で禁止語を含む (行番号(1始まり), 禁止語) を返す
  - `missing_headings(text: str, required: list[str]) -> list[str]` — 行頭一致で見つからない見出しを返す
  - `extract_ids(text: str) -> set[str]` — 正規表現 `\b[FR]-\d{2}\b` に一致するIDの集合
  - `undefined_ids(referenced: set[str], defined: set[str]) -> list[str]` — ソート済み
  - `main(root: pathlib.Path) -> int` — 3文書を検査し、問題を標準出力に表示して、問題があれば1、無ければ0を返す。要件定義書で定義されたID(`extract_ids(要件定義書)`)を基準に、基本・詳細設計書の未定義IDを報告する。`if __name__ == "__main__": sys.exit(main(Path(__file__).resolve().parents[1]))`、標準出力は `sys.stdout.reconfigure(encoding="utf-8")`

- [ ] **Step 1: テストを書く**

```python
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
```

- [ ] **Step 2: 失敗を確認する**

Run: `python -m pytest tools/tests -v`(プロジェクトルートで実行。`tools/__init__.py` と `tools/tests/__init__.py` を空で作る)
Expected: FAIL(`ModuleNotFoundError: tools.check_docs`)

- [ ] **Step 3: `tools/check_docs.py` を実装する**

ファイル読み込みはすべて `encoding="utf-8"`。

- [ ] **Step 4: テストの通過を確認する**

Run: `python -m pytest tools/tests -v`
Expected: 5 passed

- [ ] **Step 5: 現在の第2版に対して実行し、問題が検出されることを確認する**

Run: `python tools/check_docs.py`
Expected: 終了コード1。禁止語(`実装済` など)と不足見出しが一覧表示される

- [ ] **Step 6: コミット**

```bash
git add tools/
git commit -m "chore: 設計文書チェックスクリプトを追加"
```

---

### Task 2: 第2版の退避と要件定義書 第3版

**Files:**
- Create: `旧版_20261016/要件定義書.md`, `旧版_20261016/基本設計書.md`, `旧版_20261016/詳細設計書.md`, `旧版_20261016/要件定義書.docx`, `旧版_20261016/基本設計書.docx`, `旧版_20261016/詳細設計書.docx`(コピー)
- Modify: `.gitignore`(`/旧版_20261016` を追加)
- Modify: `要件定義書.md`(全面改訂)

**Interfaces:**
- Consumes: Task 1 の `tools/check_docs.py`
- Produces: F-01〜F-20、R-01〜R-06 の定義(Task 3〜5 はこれ以外のIDを使わない)

- [ ] **Step 1: 第2版を `旧版_20261016/` にコピーし、`.gitignore` に `/旧版_20261016` を追記する**

確認: `git status --short` に `旧版_20261016` が出ないこと。

- [ ] **Step 2: 要件定義書.md を次の見出し構成で書き直す**

| 見出し | 内容の出典 |
|---|---|
| `## 改訂履歴` | 第2版の表+3.0の行 |
| `## プロジェクト概要・背景` | 第2版を流用(試作の記述と「第2版では〜」の段落は削除) |
| `## 目的・ゴール` | 第2版を流用 |
| `## スコープ(対象範囲)` | 仕様 §2.2 の部門、§2.6 の対象外(相場・ESLの理由つき)、Papyrus 設計 |
| `## ステークホルダー` | 第2版を流用。期限は「§10 により再調整」と注記 |
| `## 利用者と権限` | 仕様 §2.1 の表 |
| `## 業務要件` | `### As-Is`(第2版)、`### 部門別の業務`(§2.2)、`### 業務要件一覧`(§2.3 R-01〜R-06)、`### 業務フロー`(§2.4)、`### イベント`(§2.5) |
| `## 機能要件` | 仕様 §3 の表(区分・ID・機能・優先度・対応する業務要件ID の5列) |
| `## 非機能要件` | 仕様 §7.2(テスト行を除く)+対象日・タイムアウト(§4.4)+日時基準 |
| `## 成功基準・評価方法` | 仕様 §6 の表と冒頭の判定方針、§6.2 |
| `## トレーサビリティ` | 仕様 §6.1 の表 |
| `## 制約条件` | `### 前提条件`(第2版の4項目を To-Be 向けに更新、状況列は削除)、`### リスク`(第2版の4件+「対応方針」列を仕様に合わせて更新) |
| `## ヒアリング確認項目` | 仕様 §8 の表 |
| `## スケジュール` | 第2版のマイルストーン+仕様 §10 の再調整方針 |
| `## 付録 試作(prototype)からの変更点` | 仕様 §9.1 の表+`### 機能IDの対応(第2版→第3版)`(第2版 F-01〜F-16 それぞれの行き先。廃止は「廃止(根拠表示に統合)」等) |

- [ ] **Step 3: Task 1 の `REQUIRED_HEADINGS["要件定義書.md"]` が上の見出しと一致していることを確認し、チェックを実行する**

Run: `python tools/check_docs.py`
Expected: 要件定義書.md について禁止語0件・不足見出し0件(他の2文書の問題はまだ出てよい)

- [ ] **Step 4: 仕様との突き合わせ**

`grep -c "F-[0-9][0-9]" 要件定義書.md` で機能表の20行を目視確認し、Global Constraints の数値をすべて含むことを確認する。

(文書はgit追跡外のためコミットなし。`.gitignore` も未追跡のためコミットしない)

---

### Task 3: 基本設計書 第3版

**Files:**
- Modify: `基本設計書.md`(全面改訂)

**Interfaces:**
- Consumes: Task 2 の F/R ID、本計画の「画面一覧」「API一覧」「テーブル一覧」

- [ ] **Step 1: 次の見出し構成で書き直す**

| 見出し | 内容の出典 |
|---|---|
| `## 改訂履歴` | 第2版+3.0 |
| `## 基本設計書の位置づけ` | 第2版を流用し To-Be 向けに更新。Papyrus によるモデルベース設計を明記 |
| `## システム構成` | 仕様 §7.1 の図と部品分け(取込/特徴量作成/予測/発注計算/提案・承認/認証)、モデル分離の概要(§5.3) |
| `## 技術スタック` | 第2版の表を Python 3.11 統一・LightGBM候補追加で更新 |
| `## 実行環境構成` | `### ローカル開発環境`(Docker Compose)、`### 評価環境(AWS)`(EC2 1台、DBは同サーバーのコンテナ、HTTPS、アクセス元限定) |
| `## 機能構成と処理の流れ` | `### 事前準備: モデルの作成`(§5.2 概要、別プロジェクト)、`### データ取込`(§4.3)、`### 提案の作成・再計算`(§5.4)、`### 確認・修正・承認`(§5.7 概要)、`### 欠損時の扱い`(§5.6 の表) |
| `## 画面構成` | 本計画の画面一覧+画面遷移(ログイン → 発注/製造計画、サイドバーから各画面) |
| `## データ設計方針` | 仕様 §4.1・§4.2、本計画のテーブル一覧(概要のみ)、根拠のスナップショット方針(§4.3) |
| `## 外部連携・インターフェース設計方針` | 画面⇔API(本計画のAPI一覧の区分レベル)、気象(§4.4)、POS・在庫(標準取込形式)、既存発注システム(F-19) |
| `## セキュリティ設計方針` | 仕様 §7.2 セキュリティ・データ管理、§2.1 権限 |
| `## 運用・保守設計方針` | スモールスタート評価計画(§6.2)、モデルの更新手順(§5.2-8)、修正履歴の活用、/health、Alembic |
| `## 今後の進め方` | 詳細設計書への引き継ぎ、仕様 §10 の実装順(生鮮→惣菜) |
| `## 付録 試作(prototype)からの変更点` | 仕様 §9.1 から構成・画面・運用に関わる行 |

- [ ] **Step 2: `REQUIRED_HEADINGS["基本設計書.md"]` を上と一致させ、チェックを実行する**

Run: `python tools/check_docs.py`
Expected: 基本設計書.md について禁止語0件・不足見出し0件・未定義ID 0件

- [ ] **Step 3: 画面一覧・API区分が本計画の表と一致することを目視確認する**

---

### Task 4: 詳細設計書 第3版(前半: ロジック)

**Files:**
- Modify: `詳細設計書.md`(全面改訂の前半)

**Interfaces:**
- Consumes: Task 2 の ID、本計画の API・テーブル一覧

- [ ] **Step 1: 次の見出しを書く**

| 見出し | 内容の出典 |
|---|---|
| `## 改訂履歴` | 第2版+3.0 |
| `## 詳細設計書の位置づけ` | To-Be 向けに更新 |
| `## モジュール構成` | 本体: 取込/特徴量作成/予測(モデル読込とベースライン)/発注計算/提案・承認/認証/気象クライアント/API/画面。別プロジェクト: モデル作成・評価、サンプルデータ生成。各モジュールの役割と依存先の表(ファイルパスではなくモジュール名で書く) |
| `## 需要予測モデル` | 仕様 §5.1(特徴量表: 名称・種別・内容・日別/時間帯別の区別・情報の時点)、日別気象の集約規則、§5.2 の学習・評価・バックテスト手順 |
| `## 予測モデルのインターフェース定義` | 仕様 §5.3。入力列の表(列名は英小文字スネークケース: product_code, target_date, day_of_week, time_band(日別モデルでは列なし), is_holiday, holiday_seq, is_promotion, weather_code, temperature, precipitation(確率または量。§8 で確定), sales_lag_7d, sales_avg_7d)、出力、付随情報、ベースラインへの切替条件、適合テスト |
| `## 提案作成処理` | 仕様 §5.4(きっかけ・対象・自動再計算の5条件・保護される提案・対象日の算出・処理順・二重実行防止「部門×対象日」・鮮度表示) |
| `## 発注数・製造数の計算` | 仕様 §5.5 の式と例(42 の計算例を含む)、売上構成比の求め方 |
| `## 欠損時の扱い` | 仕様 §5.6 の表 |
| `## 提案の状態遷移` | 仕様 §5.7 の表+遷移ごとの API と 409/403 応答 |

- [ ] **Step 2: チェックを実行する**

Run: `python tools/check_docs.py`
Expected: 詳細設計書.md について禁止語0件・未定義ID 0件(不足見出しは Task 5 分だけが残る)

---

### Task 5: 詳細設計書 第3版(後半: API・画面・データ)

**Files:**
- Modify: `詳細設計書.md`(後半)

**Interfaces:**
- Consumes: Task 4 の状態名・計算式、本計画の画面・API・テーブル一覧

- [ ] **Step 1: 次の見出しを書く**

| 見出し | 内容の出典 |
|---|---|
| `## API仕様` | 本計画のAPI一覧(全件)、各APIの入力・出力の主項目、権限、エラー応答表(400 入力不正・401 未ログイン・403 権限なし/他部門・404・409 状態不正/期限切れ・422 検証エラー・503 気象API失敗時は提案側の警告で返し、APIエラーにはしない旨) |
| `## 画面詳細設計` | 本計画の画面一覧の各画面: 表示項目・操作・警告/鮮度の表示・空状態・エラー文言 |
| `## データ項目定義` | 本計画のテーブル一覧の各テーブル: 項目・型・内容(主キー・外部キー・一意制約。proposals は「部門×商品×対象日×時間帯」で一意、根拠スナップショット列を持つ) |
| `## 標準取込形式` | 仕様 §4.1 の4種類のCSV列定義(列名・型・必須・例)と上書き単位(§4.3) |
| `## 研究用サンプルデータ生成仕様` | 仕様 §4.5 |
| `## 外部API仕様(気象データ)` | 第2版の表を更新(予報・過去実績、タイムアウト10秒、保存)と第2版の WMO 天候コード対応表 |
| `## 設定項目` | F-17 の項目(画面で変更)と環境変数(DB接続先、気象APIのURL、店舗の緯度経度、CORS、モデルファイルのパス)の表と既定値 |
| `## テスト・評価方針` | 仕様 §7.2 テスト行、§6 の評価方法、Review Focus と同等の観点 |
| `## 既知の課題・未確定事項` | 仕様 §8 の項目への参照と、詳細設計で残った未確定点 |
| `## 付録 試作(prototype)からの変更点` | 仕様 §9.1 の全行 |

- [ ] **Step 2: チェックを実行する**

Run: `python tools/check_docs.py`
Expected: 詳細設計書.md について問題0件

---

### Task 6: 文書間の整合確認と仕上げ

**Files:**
- Modify: 3文書(不整合の修正のみ)

- [ ] **Step 1: 全体チェック**

Run: `python tools/check_docs.py`
Expected: 終了コード0、出力に問題なし

- [ ] **Step 2: 数値・名称の照合**

Run(Git Bash): `grep -n -E "1分|3時間|1\.1|15日|2秒|10秒|WAPE|3\.11|未承認|承認済み|確定|期限切れ" 要件定義書.md 基本設計書.md 詳細設計書.md`
Expected: 同じ項目について3文書で値・表記が一致している(違いがあれば仕様に合わせて修正)

- [ ] **Step 3: 画面・APIの照合**

基本設計書の `## 画面構成` と詳細設計書の `## 画面詳細設計`、基本設計書の外部連携節と詳細設計書の `## API仕様` が本計画の一覧と過不足なく一致することを確認する。

- [ ] **Step 4: 仕様の全節がどこかの文書に反映されていることを確認する**

仕様 §2〜§9 の各節について、反映先の文書と見出しを一覧にして目視確認する(仕様 §9 の振り分け表と照合)。

- [ ] **Step 5: 作業結果を報告する**

文書はgit追跡外のため、変更した3文書と退避先 `旧版_20261016/` を報告する。tools/ に追加変更があればコミットする。
