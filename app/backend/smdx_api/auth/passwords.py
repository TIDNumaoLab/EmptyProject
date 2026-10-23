"""パスワードのハッシュ化(argon2id)。"""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# PasswordHasher の既定は argon2id
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerificationError, InvalidHashError):
        return False
