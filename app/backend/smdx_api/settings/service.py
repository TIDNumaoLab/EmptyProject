"""設定値の読込・更新(DB の settings テーブル)。"""
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.db.models import Department, Setting
from smdx_api.settings.values import INTERNAL_PREFIX, AppSettings, resolve, validate_changes

# 特売・カレンダーの最終変更日時(削除も含む)。最新性判定で使う(判断 2-10)
EVENTS_CHANGED_KEY = f"{INTERNAL_PREFIX}events_changed_at"


def _departments(db: Session) -> list[tuple[str, str]]:
    return [(d.code, d.business_type) for d in db.scalars(select(Department).order_by(Department.code))]


def _stored(db: Session) -> dict[str, Any]:
    """保存済みの設定(内部用キーを除く)。"""
    return {s.key: s.value for s in db.scalars(select(Setting)) if not s.key.startswith(INTERNAL_PREFIX)}


def load_settings(db: Session) -> AppSettings:
    return resolve(_stored(db), _departments(db))


def update_settings(db: Session, changes: dict[str, Any], user_id: int) -> AppSettings:
    """変更を検証して保存する。不正なら SettingsError を送出し、何も保存しない。"""
    departments = _departments(db)
    values = validate_changes(changes, _stored(db), departments)
    existing = {s.key: s for s in db.scalars(select(Setting).where(Setting.key.in_(values)))}
    for key, value in values.items():
        row = existing.get(key)
        if row is None:
            db.add(Setting(key=key, value=value, updated_by=user_id))
        else:
            row.value = value
            row.updated_by = user_id
    db.flush()
    return load_settings(db)


def touch_internal(db: Session, key: str, at: datetime) -> None:
    """内部用キーに日時を記録する(設定 API には出さない)。"""
    if not key.startswith(INTERNAL_PREFIX):
        raise ValueError(f"内部用キーは {INTERNAL_PREFIX} で始める: {key}")
    row = db.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        db.add(Setting(key=key, value=at.isoformat()))
    else:
        row.value = at.isoformat()
    db.flush()


def read_internal_datetime(db: Session, key: str) -> datetime | None:
    value = db.scalar(select(Setting.value).where(Setting.key == key))
    return datetime.fromisoformat(value) if value else None
