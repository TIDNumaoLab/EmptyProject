"""ログインの照合と、ログイン中の利用者の読み込み。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.auth.passwords import hash_password, verify_password
from smdx_api.auth.permissions import Principal
from smdx_api.db.models import User

# 存在しない利用者でも照合と同じ時間をかけ、応答時間から利用者の有無を推測させない
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def authenticate(db: Session, login_id: str, password: str) -> User | None:
    """無効な利用者・存在しない利用者・パスワード不一致はすべて None。"""
    user = db.scalar(select(User).where(User.login_id == login_id))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password) or not user.is_active:
        return None
    return user


def load_principal(db: Session, user_id: int) -> Principal | None:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return Principal(
        user_id=user.id,
        name=user.name,
        role=user.role,
        department_codes=frozenset(d.code for d in user.departments),
    )
