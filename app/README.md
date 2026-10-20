# スーパーマーケットDX システム(app/)

気象・イベント連動の需要予測と、生鮮の発注提案・惣菜の製造計画を行うシステムプロトタイプ。
設計は `../設計書/` を正とする。フォルダ構成は `../設計書/技術スタック・ファイル構成.md` を参照。

## 開発環境の構築(Python 3.11)

Python は 3.11 に統一する。uv で導入し、仮想環境は `app/.venv` の1つを全プロジェクトで共用する。
以下はすべて `app/` をカレントにして実行する(Windows の Git Bash の例。Linux/macOS では `.venv/Scripts/python` を `.venv/bin/python` に読み替える)。

```bash
py -3.9 -m pip install --user uv          # uv が無い場合(PATH にあれば以降の `py -3.9 -m uv` は `uv` でよい)
py -3.9 -m uv python install 3.11
py -3.9 -m uv venv --python 3.11 .venv
py -3.9 -m uv pip install --python .venv -c constraints.txt -e "./backend[dev]"
```

ライブラリのバージョンは `constraints.txt` で固定している。インストールには必ず `-c constraints.txt` を付ける。

## 研究用サンプルデータ(F-20)

実データが無い間の開発・動作確認・バックテスト用。15品(青果6・鮮魚4・惣菜5)、実行日の前日までの400日、乱数シード42で生成する。
同じ終端日・日数・シードなら同じ内容になる。出力先 `sample_data/output/` は Git 管理外。

```bash
py -3.9 -m uv pip install --python .venv -c constraints.txt -e "./sample_data[dev]"
.venv/Scripts/python -m smdx_sample --out sample_data/output --end-date 2026-10-15
```

出力: 標準取込形式の `products.csv`・`pos_sales.csv`・`inventory.csv`・`waste.csv` と、`weather.csv`・`calendar.csv`・`promotions.csv`・`true_demand.csv`(評価用の真の需要)。

## 設定

`backend/.env.example` をコピーして `backend/.env` を作り、`SESSION_SECRET` を設定する(32文字以上。空のままでは起動しない)。

## 試験

```bash
.venv/Scripts/python -m pytest backend/tests -q
```

DB を使う試験(`db` マーカー)は、環境変数 `TEST_DATABASE_URL` に試験専用の PostgreSQL 16 のデータベースを指定したときだけ実行される(未指定ならスキップ)。試験はそのデータベースの `public` スキーマを作り直すので、開発用のデータベースを指定しないこと。

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smdx_test .venv/Scripts/python -m pytest backend/tests -q
```

## 起動

### Docker Compose(推奨)

`backend/.env` を作ってから、`app/infra` で起動する。DB(PostgreSQL 16)・本体・画面がまとめて起動し、DB構造は起動時に `alembic upgrade head` で最新になる。

```bash
docker compose up -d --build
```

- 画面: http://localhost:5173/login
- 本体API: http://localhost:8000(Swagger UI は /docs、稼働確認は /health)
- 試験用のデータベースを作る場合: `docker compose exec db createdb -U postgres smdx_test`(`TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smdx_test`)
- データは Docker ボリューム `db-data` に残る。`docker compose down -v` はデータを消すので注意する。

### Docker を使わない場合

PostgreSQL 16 を別に用意し、`backend/.env` の `DATABASE_URL` をその接続先にする。

```bash
cd backend
../.venv/Scripts/python -m alembic upgrade head
../.venv/Scripts/python -m uvicorn --factory smdx_api.main:create_app --reload --port 8000
```

画面は `frontend` で `npm install` → `npm run dev`(`frontend/.env.example` を参考に `VITE_API_BASE_URL` を設定)。

## 管理コマンド

画面を持たない初期設定は、`app/backend` をカレントにして管理コマンドで行う。接続先は本体と同じで、環境変数 `DATABASE_URL` → `backend/.env` の `DATABASE_URL` → 既定値(`postgresql://postgres:postgres@localhost:5432/supermarket_dx`)の順に決まる。マイグレーション(`alembic upgrade head`)も同じ規則。

### 利用者の登録(create_user)

利用者を登録する画面は無い。役割(`staff`=発注担当者 / `manager`=店長)と所属部門(VEG=青果、FISH=鮮魚、DELI=惣菜。カンマ区切り)を指定する。
初期パスワードは8文字以上。`--password` を省略すると入力を求められる(シェルの履歴に残さないため省略を推奨)。

```bash
../.venv/Scripts/python -m smdx_api.commands create_user --login-id tanaka --name 田中 --role staff --departments VEG,FISH
../.venv/Scripts/python -m smdx_api.commands create_user --login-id tencho --name 店長 --role manager
```
