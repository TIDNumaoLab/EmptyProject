"""マイグレーション・管理コマンドの接続先(本体と同じく .env も読む)。"""
from smdx_api.db.url import DEFAULT_DATABASE_URL, database_url_from_env


def test_default_when_nothing_set(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url_from_env() == DEFAULT_DATABASE_URL


def test_reads_dotenv_like_the_app(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://u:p@otherhost:5432/smdx\nSESSION_SECRET=\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url_from_env() == "postgresql://u:p@otherhost:5432/smdx"


def test_environment_overrides_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://u:p@otherhost:5432/smdx\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/supermarket_dx")
    assert database_url_from_env() == "postgresql://u:p@db:5432/supermarket_dx"
