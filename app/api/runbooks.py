from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.models import Runbook, RunbookVersion
from app.schemas.api import RunbookRead, RunbookVersionRead

router = APIRouter(prefix="/api/v1/runbooks", tags=["runbooks"])


@router.get("", response_model=list[RunbookRead])
def list_runbooks(db: Session = Depends(get_db)) -> list[Runbook]:
    return list(db.scalars(select(Runbook).order_by(Runbook.name.asc())).all())


@router.get("/{runbook_id}/versions", response_model=list[RunbookVersionRead])
def list_runbook_versions(
    runbook_id: int,
    db: Session = Depends(get_db),
) -> list[RunbookVersion]:
    runbook = db.get(Runbook, runbook_id)
    if runbook is None:
        raise HTTPException(status_code=404, detail="runbook not found")
    return list(
        db.scalars(
            select(RunbookVersion)
            .where(RunbookVersion.runbook_id == runbook_id)
            .order_by(RunbookVersion.version.desc())
        ).all()
    )
