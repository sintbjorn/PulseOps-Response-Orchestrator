from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.models import ResponsePolicy
from app.schemas.api import PolicySimulationRequest, PolicySimulationResponse, ResponsePolicyRead
from app.services.policy_engine import simulate_policy

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


@router.post("/simulate", response_model=PolicySimulationResponse)
def simulate(
    request: PolicySimulationRequest,
    db: Session = Depends(get_db),
) -> PolicySimulationResponse:
    return simulate_policy(db, request)


@router.get("", response_model=list[ResponsePolicyRead])
def list_policies(db: Session = Depends(get_db)) -> list[ResponsePolicy]:
    return list(
        db.scalars(
            select(ResponsePolicy).order_by(ResponsePolicy.priority.desc(), ResponsePolicy.id.asc())
        ).all()
    )
