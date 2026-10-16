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

## 設定

`backend/.env.example` をコピーして `backend/.env` を作り、`SESSION_SECRET` を設定する。

## 試験

```bash
.venv/Scripts/python -m pytest backend/tests -q
```

DB を使う試験(`db` マーカー)は、環境変数 `TEST_DATABASE_URL` に試験専用の PostgreSQL 16 のデータベースを指定したときだけ実行される(未指定ならスキップ)。試験はそのデータベースの `public` スキーマを作り直すので、開発用のデータベースを指定しないこと。

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smdx_test .venv/Scripts/python -m pytest backend/tests -q
```

## 管理コマンド

画面を持たない初期設定は、`app/backend` をカレントにして管理コマンドで行う。接続先は環境変数 `DATABASE_URL`(未指定なら `postgresql://postgres:postgres@localhost:5432/supermarket_dx`)。

### 利用者の登録(create_user)

利用者を登録する画面は無い。役割(`staff`=発注担当者 / `manager`=店長)と所属部門(VEG=青果、FISH=鮮魚、DELI=惣菜。カンマ区切り)を指定する。
初期パスワードは8文字以上。`--password` を省略すると入力を求められる(シェルの履歴に残さないため省略を推奨)。

```bash
../.venv/Scripts/python -m smdx_api.commands create_user --login-id tanaka --name 田中 --role staff --departments VEG,FISH
../.venv/Scripts/python -m smdx_api.commands create_user --login-id tencho --name 店長 --role manager
```
