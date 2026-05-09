import json
import psycopg2.extensions
import pprint
from fastapi import HTTPException, status

from app.schemas.assessment import (
    QuestionOptionSchema,
    QuestionSchema,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
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

    # TODO: implement proper scoring algorithm
    assessed_risk = "Moderate"

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
    )
