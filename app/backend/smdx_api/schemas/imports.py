"""取込 API の入出力。"""
from pydantic import BaseModel

from smdx_api.imports.formats import Kind
from smdx_api.schemas.common import JstDatetime


class RowErrorOut(BaseModel):
    row: int
    reason: str


class ImportLogOut(BaseModel):
    id: int
    kind: Kind
    department_code: str | None
    file_name: str
    imported_count: int
    skipped_count: int
    errors: list[RowErrorOut]
    imported_by_name: str | None
    finished_at: JstDatetime
