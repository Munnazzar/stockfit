import json
import psycopg2.extensions
import pprint
from fastapi import HTTPException, status

from app.schemas.assessment import (
    QuestionnaireDetailSchema,
    QuestionnaireResponseItemSchema,
    QuestionnaireSchema,
    QuestionOptionSchema,
    QuestionSchema,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from app.services.RiskTierCalculation.risk_profile_calculator import evaluate_user_risk_profile

_TIER_TO_DB = {"HIGH": "High", "MODERATE": "Moderate", "LOW": "Low"}


def get_user_questionnaires(
    db: psycopg2.extensions.connection,
    user_id: str,
) -> list[QuestionnaireSchema]:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT questionnaire_id, assessed_risk, created_at
            FROM questionnaires
            WHERE fk_user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    return [
        QuestionnaireSchema(
            questionnaire_id=row["questionnaire_id"],
            assessed_risk=row["assessed_risk"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def get_questionnaire_detail(
    db: psycopg2.extensions.connection,
    user_id: str,
    questionnaire_id: str,
) -> QuestionnaireDetailSchema:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT questionnaire_id, assessed_risk, created_at
            FROM questionnaires
            WHERE questionnaire_id = %s AND fk_user_id = %s
            """,
            (questionnaire_id, user_id),
        )
        q_row = cur.fetchone()

        if not q_row:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found or does not belong to the current user.",
            )

        cur.execute(
            """
            SELECT
                q.question_id,
                q.question_string,
                q.question_type,
                q.question_id_cfa,
                q.question_category,
                qr.question_response
            FROM question_responses qr
            JOIN questions q ON q.question_id = qr.fk_question_id
            WHERE qr.fk_questionnaire_id = %s
            ORDER BY q.question_id_cfa
            """,
            (questionnaire_id,),
        )
        response_rows = cur.fetchall()

    return QuestionnaireDetailSchema(
        questionnaire_id=q_row["questionnaire_id"],
        assessed_risk=q_row["assessed_risk"],
        created_at=q_row["created_at"],
        responses=[
            QuestionnaireResponseItemSchema(
                question_id=row["question_id"],
                question_string=row["question_string"],
                question_type=row["question_type"],
                question_id_cfa=row["question_id_cfa"],
                question_category=row["question_category"],
                selected_option=row["question_response"],
            )
            for row in response_rows
        ],
    )


def get_questions(db: psycopg2.extensions.connection) -> list[QuestionSchema]:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT question_id, question_string, question_type,
                   question_id_cfa, question_options, created_at
            FROM questions
            ORDER BY question_id_cfa
            """
        )
        rows = cur.fetchall()
    pprint.pprint(rows)
    return [
        QuestionSchema(
            question_id=row["question_id"],
            question_string=row["question_string"],
            question_type=row["question_type"],
            question_id_cfa=row["question_id_cfa"],
            question_options=[
                QuestionOptionSchema(
                    label=opt.get("label"),
                    value=opt.get("value"),
                    weight = opt.get("weight"),
                )
                for opt in row["question_options"]
            ],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def _valid_responses(options: list[dict]) -> set[str]:
    """Return all accepted response strings for a question's options.

    Each option can be value-only  {"value": "X"}
    or text+value                  {"text": "Label", "value": "X"}.
    A submitted response is valid if it matches:
      - the value alone  → "X"
      - the text alone   → "Label"
      - text + value     → "Label - X"
    """
    valid: set[str] = set()
    for opt in options:
        value = opt.get("value")
        text = opt.get("text")
        if value is not None:
            valid.add(str(value))
        if text:
            valid.add(text)
            if value is not None:
                valid.add(f"{text} - {value}")
    return valid


def submit_risk_assessment(
    db: psycopg2.extensions.connection,
    user_id: str,
    data: RiskAssessmentRequest,
) -> RiskAssessmentResponse:
    with db.cursor() as cur:
        cur.execute("SELECT question_id, question_options FROM questions")
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No questions exist in the database.",
        )

    db_questions: dict[str, list[dict]] = {
        str(row["question_id"]): row["question_options"] for row in rows
    }

    submitted_ids = {str(r.question_id) for r in data.responses}
    missing = set(db_questions.keys()) - submitted_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Responses are missing for {len(missing)} question(s).",
        )

    extra = submitted_ids - set(db_questions.keys())
    if extra:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Responses contain {len(extra)} unrecognized question_id(s).",
        )

    for response in data.responses:
        if response.question_type == "number_input":
            continue
        valid = _valid_responses(db_questions[str(response.question_id)])
        value = response.selected_option.value
        if value not in valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"'{value}' is not a valid option for '{response.question_id_cfa}'. "
                    f"Valid options: {sorted(valid)}"
                ),
            )

    opts = {r.question_id_cfa: r.selected_option for r in data.responses}

    opts["investment_time_horizon_years"].value= float(opts["investment_time_horizon_years"].value)/12
    
    def _num(key: str) -> float:
        return float(opts[key].value)

    def _score(key: str) -> int:
        return int(opts[key].weight)

    def _bool(key: str) -> bool:
        opt = opts[key]
        if opt.weight is not None:
            return bool(opt.weight)
        return opt.value.strip().lower() == "yes"

    profile = evaluate_user_risk_profile(
        target_future_value=_num("target_future_value"),
        current_portfolio_value=_num("current_portfolio_value"),
        investment_time_horizon_years=float(_num("investment_time_horizon_years")),
        annual_net_cash_flow=_num("annual_net_cash_flow"),
        tolerance_time_horizon_years=float(_num("investment_time_horizon_years")),
        expects_high_withdrawal_rate=_bool("expects_high_withdrawal_rate"),
        has_stable_external_income=_bool("has_stable_external_income"),
        willingness_to_take_risk=_score("willingness_to_take_risk"),
        safety_vs_return_preference=_score("safety_vs_return_preference"),
        financial_knowledge_level=_score("financial_knowledge_level"),
        investment_experience_level=_score("investment_experience_level"),
        market_risk_perception=_score("market_risk_perception"),
        reaction_to_losses_score=_score("reaction_to_losses_score"),
    )

    if profile["portfolio_tier"] is None:
        return RiskAssessmentResponse(
            portfolio_tier=None,
            signal=profile["signal"],
            message=profile["message"],
            risk_need_tier=profile["risk_need_tier"],
            risk_capacity_tier=profile["risk_capacity_tier"],
            behavioral_risk_tier=profile["behavioral_risk_tier"],
            required_rate_of_return=profile["required_rate_of_return"],
        )

    assessed_risk = _TIER_TO_DB[profile["portfolio_tier"]]

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO questionnaires (fk_user_id, assessed_risk)
            VALUES (%s, %s)
            RETURNING questionnaire_id
            """,
            (user_id, assessed_risk),
        )
        questionnaire_id = cur.fetchone()["questionnaire_id"]

        cur.executemany(
            """
            INSERT INTO question_responses (fk_questionnaire_id, fk_question_id, question_response)
            VALUES (%s, %s, %s)
            """,
            [
                (
                    str(questionnaire_id),
                    str(r.question_id),
                    json.dumps({"value": r.selected_option.value} if r.question_type == "number_input" else r.selected_option.model_dump()),
                )
                for r in data.responses
            ],
        )

        cur.execute(
            """
            UPDATE users
            SET risk_tolerance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (assessed_risk, user_id),
        )

    return RiskAssessmentResponse(
        questionnaire_id=questionnaire_id,
        assessed_risk=assessed_risk,
        portfolio_tier=profile["portfolio_tier"],
        signal=profile["signal"],
        message=profile["message"],
        risk_need_tier=profile["risk_need_tier"],
        risk_capacity_tier=profile["risk_capacity_tier"],
        behavioral_risk_tier=profile["behavioral_risk_tier"],
        required_rate_of_return=profile["required_rate_of_return"],
    )
