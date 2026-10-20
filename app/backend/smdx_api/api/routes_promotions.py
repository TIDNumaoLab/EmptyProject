"""特売・チラシ(F-06)。閲覧は全員、登録・更新・削除は商品の部門で権限を判定する。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.api.deps import FORBIDDEN, NOT_FOUND, current_user, get_db
from smdx_api.auth.permissions import Principal, can_access_department
from smdx_api.clock import get_now
from smdx_api.db.models import Department, Product, Promotion, User
from smdx_api.schemas.promotions import PromotionIn, PromotionOut, PromotionPatch
from smdx_api.settings.service import EVENTS_CHANGED_KEY, touch_internal

router = APIRouter(prefix="/api")

END_BEFORE_START = "終了日は開始日以降にしてください"


def _product(db: Session, code: str) -> Product:
    p = db.scalar(select(Product).where(Product.product_code == code))
    if p is None:
        raise HTTPException(status_code=422, detail=f"未登録の商品コードです: {code}")
    return p


def _check_access(p: Principal, product: Product) -> None:
    if not can_access_department(p, product.department.code):
        raise HTTPException(status_code=403, detail=FORBIDDEN)


def _out(db: Session, promo: Promotion) -> PromotionOut:
    product = db.get(Product, promo.product_id)
    user = db.get(User, promo.created_by) if promo.created_by else None
    return PromotionOut(
        id=promo.id,
        product_code=product.product_code,
        product_name=product.name,
        department_code=product.department.code,
        start_date=promo.start_date,
        end_date=promo.end_date,
        description=promo.description,
        created_by_name=user.name if user else None,
    )


def _get(db: Session, promotion_id: int) -> Promotion:
    promo = db.get(Promotion, promotion_id)
    if promo is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return promo


@router.get("/promotions", response_model=list[PromotionOut])
def list_promotions(
    date_from: date | None = None,
    date_to: date | None = None,
    department_code: str | None = None,
    _: Principal = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = (
        select(Promotion)
        .join(Product, Promotion.product_id == Product.id)
        .join(Department, Product.department_id == Department.id)
        .order_by(Promotion.start_date, Product.product_code, Promotion.id)
    )
    # 期間が重なるもの
    if date_from is not None:
        q = q.where(Promotion.end_date >= date_from)
    if date_to is not None:
        q = q.where(Promotion.start_date <= date_to)
    if department_code:
        q = q.where(Department.code == department_code)
    return [_out(db, promo) for promo in db.scalars(q)]


@router.post("/promotions", response_model=PromotionOut)
def create_promotion(
    body: PromotionIn, p: Principal = Depends(current_user), db: Session = Depends(get_db), now: datetime = Depends(get_now)
):
    product = _product(db, body.product_code)
    _check_access(p, product)
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail=END_BEFORE_START)
    promo = Promotion(product_id=product.id, start_date=body.start_date, end_date=body.end_date,
                      description=body.description, created_by=p.user_id)
    db.add(promo)
    touch_internal(db, EVENTS_CHANGED_KEY, now)
    db.commit()
    return _out(db, promo)


@router.patch("/promotions/{promotion_id}", response_model=PromotionOut)
def update_promotion(
    promotion_id: int,
    body: PromotionPatch,
    p: Principal = Depends(current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    promo = _get(db, promotion_id)
    _check_access(p, db.get(Product, promo.product_id))
    if body.product_code is not None:
        product = _product(db, body.product_code)
        _check_access(p, product)
        promo.product_id = product.id
    for field in ("start_date", "end_date", "description"):
        value = getattr(body, field)
        if value is not None:
            setattr(promo, field, value)
    if promo.end_date < promo.start_date:
        db.rollback()
        raise HTTPException(status_code=422, detail=END_BEFORE_START)
    touch_internal(db, EVENTS_CHANGED_KEY, now)
    db.commit()
    return _out(db, promo)


@router.delete("/promotions/{promotion_id}", status_code=204)
def delete_promotion(
    promotion_id: int, p: Principal = Depends(current_user), db: Session = Depends(get_db), now: datetime = Depends(get_now)
) -> Response:
    promo = _get(db, promotion_id)
    _check_access(p, db.get(Product, promo.product_id))
    db.delete(promo)
    touch_internal(db, EVENTS_CHANGED_KEY, now)
    db.commit()
    return Response(status_code=204)
