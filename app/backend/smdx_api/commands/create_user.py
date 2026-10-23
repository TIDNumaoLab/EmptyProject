"""利用者の登録(利用者を登録する画面は設けない。要件定義書「利用者と権限」)。"""
import argparse
import sys
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.auth.passwords import hash_password
from smdx_api.commands import CommandError, open_session
from smdx_api.db.models import Department, User, UserDepartment

MIN_PASSWORD_LENGTH = 8


def create_user(
    db: Session | None, login_id: str, name: str, role: str, department_codes: list[str], password: str
) -> User:
    # DB に触れる前に確かめられることを先に確かめる
    if not login_id:
        raise CommandError("login_id を指定してください")
    if role not in ("staff", "manager"):
        raise CommandError("role は staff か manager を指定してください")
    # 店長は全部門を操作できるため、所属部門は任意(要件定義書「利用者と権限」)
    if role == "staff" and not department_codes:
        raise CommandError("発注担当者は所属部門を1つ以上指定してください")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise CommandError(f"パスワードは{MIN_PASSWORD_LENGTH}文字以上にしてください")

    if db.scalar(select(User).where(User.login_id == login_id)) is not None:
        raise CommandError(f"既に登録されています: {login_id}")
    departments = []
    for code in department_codes:
        dept = db.scalar(select(Department).where(Department.code == code))
        if dept is None:
            raise CommandError(f"未登録の部門コードです: {code}")
        departments.append(dept)

    user = User(login_id=login_id, name=name, password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    db.flush()
    for dept in departments:
        db.add(UserDepartment(user_id=user.id, department_id=dept.id))
    db.flush()
    db.expire(user, ["departments"])
    return user


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("create_user", help="利用者を登録する")
    p.add_argument("--login-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", required=True, choices=["staff", "manager"])
    p.add_argument("--departments", default="", help="所属部門のコード(カンマ区切り。例: VEG,FISH)。staff は必須、manager は任意")
    p.add_argument("--password", help="省略すると入力を求める(履歴に残さないため省略を推奨)")
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    password = args.password
    if password is None:
        password = getpass("初期パスワード: ")
        if getpass("初期パスワード(確認): ") != password:
            print("パスワードが一致しません", file=sys.stderr)
            return 1
    codes = [c.strip() for c in args.departments.split(",") if c.strip()]
    with open_session() as db:
        try:
            user = create_user(db, args.login_id, args.name, args.role, codes, password)
        except CommandError as e:
            print(e, file=sys.stderr)
            return 1
        db.commit()
        print(f"登録しました: {user.login_id}({user.name}、{user.role}、所属: {','.join(codes) or 'なし'})")
    return 0
