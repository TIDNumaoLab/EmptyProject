"""商品一覧(全員が全部門を見られる)。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.api.deps import NOT_FOUND, current_user, get_db
from smdx_api.auth.permissions import Principal
from smdx_api.db.models import Department, Product
from smdx_api.schemas.products import ProductOut

router = APIRouter(prefix="/api")


@router.get("/products", response_model=list[ProductOut])
def list_products(
    department_code: str | None = None, _: Principal = Depends(current_user), db: Session = Depends(get_db)
) -> list[ProductOut]:
    q = (
        select(Product, Department.code)
        .join(Department, Product.department_id == Department.id)
        .where(Product.is_active.is_(True))
        .order_by(Product.product_code)
    )
    if department_code:
        if db.scalar(select(Department.id).where(Department.code == department_code)) is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        q = q.where(Department.code == department_code)
    return [
        ProductOut(
            product_code=p.product_code,
            name=p.name,
            department_code=code,
            order_unit=p.order_unit,
            lead_time_days=p.lead_time_days,
            can_carry_over=p.can_carry_over,
            cost_price=float(p.cost_price) if p.cost_price is not None else None,
            selling_price=float(p.selling_price) if p.selling_price is not None else None,
            is_active=p.is_active,
        )
        for p, code in db.execute(q)
    ]
