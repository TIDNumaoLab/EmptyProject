"""CSV取込の実行と取込履歴の記録。"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.db.models import Department, ImportLog, Product
from smdx_api.imports.formats import Kind
from smdx_api.imports.parse import ParseContext, parse_csv
from smdx_api.imports.save import save_rows

# 取込履歴に残すエラー行の上限(件数は skipped_count に全件残る)。部門を間違えたファイルなどで履歴が肥大しないようにする
MAX_STORED_ERRORS = 100
FILE_NAME_MAX = 255


def build_context(db: Session, department: Department | None) -> ParseContext:
    products = {
        code: (pid, dept)
        for code, pid, dept in db.execute(
            select(Product.product_code, Product.id, Department.code).join(Department, Product.department_id == Department.id)
        )
    }
    return ParseContext(
        products=products,
        department_code=department.code if department is not None else None,
        known_departments=set(db.scalars(select(Department.code))),
    )


def run_import(
    db: Session,
    kind: Kind,
    file_name: str,
    data: bytes,
    department: Department | None,
    user_id: int | None,
    now: datetime,
) -> ImportLog:
    """CSV を検証して保存し、取込履歴を残す。ファイル全体が読めなければ FileFormatError(履歴は残さない)。

    imported_count はファイルの有効な行数、skipped_count はスキップした行数。エラー行は先頭の MAX_STORED_ERRORS 件だけ残す。
    """
    result = parse_csv(kind, data, build_context(db, department))
    save_rows(db, kind, result.rows)
    log = ImportLog(
        kind=kind,
        department_id=department.id if department is not None else None,
        file_name=file_name[:FILE_NAME_MAX],
        imported_count=len(result.rows),
        skipped_count=len(result.errors),
        errors=[{"row": e.row, "reason": e.reason} for e in result.errors[:MAX_STORED_ERRORS]],
        imported_by=user_id,
        finished_at=now,
    )
    db.add(log)
    db.flush()
    return log
