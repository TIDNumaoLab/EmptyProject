"""在庫の手入力(F-03)と、商品ごとの最新の在庫。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.api.deps import current_user, department_for, get_db
from smdx_api.auth.permissions import Principal
from smdx_api.db.models import InventorySnapshot, Product
from smdx_api.imports.manual import ManualInputError, save_manual_inventory
from smdx_api.schemas.inventory import InventoryInput, LatestInventoryOut, SavedOut

router = APIRouter(prefix="/api")


@router.put("/inventory", response_model=SavedOut)
def put_inventory(body: InventoryInput, p: Principal = Depends(current_user), db: Session = Depends(get_db)) -> SavedOut:
    department = department_for(body.department_code, p, db)
    try:
        n = save_manual_inventory(db, department, body.based_at, [(i.product_code, i.quantity) for i in body.items], p.user_id)
    except ManualInputError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=e.reason) from None
    db.commit()
    return SavedOut(saved=n)


@router.get("/inventory", response_model=list[LatestInventoryOut])
def latest_inventory(
    department_code: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)
) -> list[LatestInventoryOut]:
    """部門の取扱中の商品すべてについて、基準日時が最も新しい在庫(無ければ空)。在庫入力画面の「前回」表示用(判断 2-8)。"""
    department = department_for(department_code, p, db)
    latest = (
        select(InventorySnapshot.product_id, InventorySnapshot.quantity, InventorySnapshot.based_at)
        .distinct(InventorySnapshot.product_id)
        .order_by(InventorySnapshot.product_id, InventorySnapshot.based_at.desc())
        .subquery()
    )
    rows = db.execute(
        select(Product.product_code, Product.name, latest.c.quantity, latest.c.based_at)
        .outerjoin(latest, latest.c.product_id == Product.id)
        .where(Product.department_id == department.id, Product.is_active.is_(True))
        .order_by(Product.product_code)
    )
    return [LatestInventoryOut(product_code=c, product_name=n, quantity=q, based_at=t) for c, n, q, t in rows]
