import pytest

from smdx_api.auth.passwords import verify_password
from smdx_api.commands.__main__ import main
from smdx_api.commands.create_user import CommandError, create_user

BASE = dict(login_id="x", name="x", role="staff", department_codes=["VEG"], password="pass1234")


@pytest.mark.parametrize("kwargs,msg", [
    (dict(password="short"), "パスワードは8文字以上にしてください"),
    (dict(role="admin"), "role は staff か manager を指定してください"),
    (dict(login_id=""), "login_id を指定してください"),
    (dict(department_codes=[]), "発注担当者は所属部門を1つ以上指定してください"),
])
def test_create_user_rejects_before_db(kwargs, msg):
    # DB に触れる前に検証するため、DB なしでも確かめられる
    with pytest.raises(CommandError, match=msg):
        create_user(None, **(BASE | kwargs))


@pytest.mark.db
def test_create_user_with_departments(db):
    u = create_user(db, "tanaka", "田中", "staff", ["VEG", "FISH"], "pass1234")
    assert verify_password(u.password_hash, "pass1234")
    assert {d.code for d in u.departments} == {"VEG", "FISH"}


@pytest.mark.db
def test_create_user_unknown_department(db):
    with pytest.raises(CommandError, match="未登録の部門コードです: XXX"):
        create_user(db, **(BASE | dict(department_codes=["XXX"])))


@pytest.mark.db
def test_duplicate_login_id(db):
    create_user(db, "dup", "a", "staff", ["VEG"], "pass1234")
    with pytest.raises(CommandError, match="既に登録されています: dup"):
        create_user(db, "dup", "b", "staff", ["VEG"], "pass1234")


def test_main_without_subcommand_returns_2(capsys):
    assert main([]) == 2


def test_main_password_mismatch_returns_1(monkeypatch, capsys):
    answers = iter(["pass1234", "pass9999"])
    monkeypatch.setattr("smdx_api.commands.create_user.getpass", lambda prompt="": next(answers))
    code = main(["create_user", "--login-id", "a", "--name", "a", "--role", "staff", "--departments", "VEG"])
    assert code == 1
    assert "パスワードが一致しません" in capsys.readouterr().err


def test_main_does_not_crash_on_non_utf8_console(monkeypatch):
    # Git Bash などで標準出力が cp1252 のとき、日本語の表示で異常終了しないこと
    import io
    import sys

    fake = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stderr", fake)
    assert main([]) == 2  # 日本語の説明文をヘルプとして表示する


@pytest.mark.parametrize("kwargs,msg", [
    (dict(login_id="a" * 33), "login_id は32文字以内にしてください"),
    (dict(name="あ" * 33), "name は32文字以内にしてください"),
    (dict(name=""), "name を指定してください"),
    (dict(department_codes=["VEG", "VEG"]), "部門コードが重複しています: VEG"),
])
def test_create_user_rejects_bad_input_before_db(kwargs, msg):
    # トレースバックではなく、分かりやすいエラーにする(PR #1 指摘7)
    with pytest.raises(CommandError, match=msg):
        create_user(None, **(BASE | kwargs))
