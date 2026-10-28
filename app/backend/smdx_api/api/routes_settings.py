"""設定の取得(全員)と更新(店長のみ)。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from smdx_api.api.deps import current_user, get_db, require_manager
from smdx_api.auth.permissions import Principal
from smdx_api.clock import get_now
from smdx_api.schemas.settings import SettingsBody
from smdx_api.settings.service import load_settings, update_settings
from smdx_api.settings.values import SettingsError, to_flat

router = APIRouter(prefix="/api")


@router.get("/settings", response_model=SettingsBody)
def get_settings(_: Principal = Depends(current_user), db: Session = Depends(get_db)) -> SettingsBody:
    return SettingsBody(settings=to_flat(load_settings(db)))


@router.put("/settings", response_model=SettingsBody)
def put_settings(body: SettingsBody, p: Principal = Depends(require_manager), db: Session = Depends(get_db),
                 now: datetime = Depends(get_now)):
    try:
        s = update_settings(db, body.settings, p.user_id, now)
    except SettingsError as e:
        db.rollback()
        return JSONResponse(status_code=422, content={"detail": [{"key": e.key, "msg": e.message}]})
    db.commit()
    return SettingsBody(settings=to_flat(s))
