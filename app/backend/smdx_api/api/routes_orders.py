"""承認済み発注リスト(F-13)。既存の発注システム・PDAへ入力しやすいよう、商品コード順に返す。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.api.deps import current_user, get_db
from smdx_api.api.routes_proposals import order_department
from smdx_api.auth.permissions import Principal
from smdx_api.clock import JST, get_now
from smdx_api.db.models import Product, Proposal, User
from smdx_api.proposals.deadlines import apply_deadlines
from smdx_api.schemas.orders import ApprovedOrderOut

router = APIRouter(prefix="/api/orders")


@router.get("/approved", response_model=list[ApprovedOrderOut])
def approved_orders(
    department_code: str,
    target_date: date | None = None,
    p: Principal = Depends(current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> list[ApprovedOrderOut]:
    """状態が承認済み・確定の提案。対象日を指定しなければ当日以降のすべて。"""
    department = order_department(department_code, p, db)
    apply_deadlines(db, now, department.id)
    db.commit()
    q = (select(Proposal, Product, User.name)
         .join(Product, Product.id == Proposal.product_id)
         .outerjoin(User, User.id == Proposal.approved_by)
         .where(Proposal.department_id == department.id, Proposal.status.in_(("approved", "confirmed"))))
    if target_date is not None:
        q = q.where(Proposal.target_date == target_date)
    else:
        q = q.where(Proposal.target_date >= now.astimezone(JST).date())
    rows = db.execute(q.order_by(Product.product_code, Proposal.target_date))
    return [ApprovedOrderOut(product_code=prod.product_code, product_name=prod.name, target_date=x.target_date,
                             proposed_qty=x.proposed_qty, order_unit=prod.order_unit, status=x.status,
                             approved_by_name=name, approved_at=x.approved_at) for x, prod, name in rows]
