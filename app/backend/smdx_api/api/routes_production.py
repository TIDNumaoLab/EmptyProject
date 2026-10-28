"""惣菜の陳列残数の入力(F-08)。保存後は、製造開始時刻を過ぎていない時間帯を再計算する。"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from smdx_api.api.deps import current_user, department_of_type, get_db, get_job_launcher
from smdx_api.api.routes_proposals import job_out, parse_targets
from smdx_api.auth.permissions import Principal
from smdx_api.clock import get_now
from smdx_api.imports.manual import ManualInputError, save_display_stock
from smdx_api.proposals.jobs import start_or_get_job
from smdx_api.proposals.service import JobLauncher, job_key, wanted
from smdx_api.schemas.production import DisplayStockInput, DisplayStockOut
from smdx_api.settings.service import load_settings

router = APIRouter(prefix="/api/production")


@router.put("/display-stock", response_model=DisplayStockOut)
def put_display_stock(
    body: DisplayStockInput,
    background_tasks: BackgroundTasks,
    p: Principal = Depends(current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    launcher: JobLauncher = Depends(get_job_launcher),
) -> DisplayStockOut:
    """保存し、その部門×対象日の再計算ジョブを最新性判定なしで開始する(手動再計算と同じ。実行中があればそれを返す)。"""
    department = department_of_type(body.department_code, p, db, "production")
    targets = parse_targets(body.target_date, now)
    try:
        n = save_display_stock(db, department, body.target_date, body.entered_at,
                               [(i.product_code, i.quantity) for i in body.items], p.user_id)
    except ManualInputError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=e.reason) from None
    db.commit()
    settings = load_settings(db)
    total = len(wanted(db, department, now, settings, targets))
    job, created = start_or_get_job(db, department, job_key(department, now, settings, targets), now, total)
    if created:
        launcher.launch(background_tasks, job.id, targets)
    return DisplayStockOut(saved=n, job=job_out(job))
