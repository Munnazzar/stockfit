import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.schemas.assessment import QuestionnaireSchema, QuestionSchema, RiskAssessmentRequest, RiskAssessmentResponse
from app.services import assessment_service

router = APIRouter(prefix="/assessment", tags=["Assessment"])


@router.get("/questions", response_model=list[QuestionSchema])
def get_questions(
    db: psycopg2.extensions.connection = Depends(get_db),
) -> list[QuestionSchema]:
    return assessment_service.get_questions(db)


@router.get("/questionnaires", response_model=list[QuestionnaireSchema])
def get_user_questionnaires(
    db: psycopg2.extensions.connection = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[QuestionnaireSchema]:
    return assessment_service.get_user_questionnaires(db, user_id)


@router.post("/risk", response_model=RiskAssessmentResponse, status_code=201)
def submit_risk_assessment(
    body: RiskAssessmentRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RiskAssessmentResponse:
    return assessment_service.submit_risk_assessment(db, user_id, body)
