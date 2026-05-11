from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QuestionOptionSchema(BaseModel):
    label: str | None = None
    value: str | None = None
    weight: float | None = None


class QuestionSchema(BaseModel):
    question_id: UUID
    question_string: str
    question_type: str
    question_id_cfa: str
    question_options: list[QuestionOptionSchema]
    created_at: datetime


class SelectedOptionSchema(BaseModel):
    label: str | None = None
    value: str | None = None
    weight: float | None = None


class QuestionAnswerRequest(BaseModel):
    question_id: UUID
    question_string: str
    question_type: str
    question_id_cfa: str
    selected_option: SelectedOptionSchema


class RiskAssessmentRequest(BaseModel):
    responses: Annotated[list[QuestionAnswerRequest], Field(min_length=1)]

    @field_validator("responses")
    @classmethod
    def no_duplicate_questions(
        cls, v: list[QuestionAnswerRequest]
    ) -> list[QuestionAnswerRequest]:
        seen: set[str] = set()
        for item in v:
            qid = str(item.question_id)
            if qid in seen:
                raise ValueError(f"Duplicate response for question_id '{qid}'.")
            seen.add(qid)
        return v


class QuestionnaireSchema(BaseModel):
    questionnaire_id: UUID
    assessed_risk: str | None
    created_at: datetime


class QuestionnaireResponseItemSchema(BaseModel):
    question_id: UUID
    question_string: str
    question_type: str
    question_id_cfa: str
    question_category: str
    selected_option: dict


class QuestionnaireDetailSchema(BaseModel):
    questionnaire_id: UUID
    assessed_risk: str | None
    created_at: datetime
    responses: list[QuestionnaireResponseItemSchema]


class RiskAssessmentResponse(BaseModel):
    questionnaire_id: UUID | None = None
    assessed_risk: str | None = None
    portfolio_tier: str | None = None
    signal: str
    message: str
    risk_need_tier: str
    risk_capacity_tier: str
    behavioral_risk_tier: str
    required_rate_of_return: float
