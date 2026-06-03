from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import ExecutionRead, IncidentInput
from app.services.executor import execute_incident

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/pulsewatch/incidents", response_model=ExecutionRead)
def pulsewatch_incident_webhook(
    incident: IncidentInput,
    db: Session = Depends(get_db),
):
    return execute_incident(db, incident)
