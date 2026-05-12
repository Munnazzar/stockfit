import calendar
import json
import random
from datetime import date, timedelta

import numpy as np
import psycopg2.extensions
from fastapi import HTTPException, status

from app.services.GeneticAlgorithm.constants import GENE_UPPER_BOUND, POP_SIZE
from app.services.GeneticAlgorithm.genetic_algorithm import run_ga_forward
from app.schemas.portfolio import (
    CreatePortfolioRequest,
    PortfolioResponse,
    PortfolioStockSchema,
)


_TIME_HORIZON_CFA = "investment_time_horizon_years"


def _add_months(base_date: date, months: int) -> date:
    year = base_date.year + (base_date.month - 1 + months) // 12
    month = (base_date.month - 1 + months) % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _parse_numeric_response(raw_response: str) -> float:
    try:
        payload = json.loads(raw_response)
    except (TypeError, json.JSONDecodeError):
        payload = raw_response

    if isinstance(payload, dict):
        payload = payload.get("value")

    try:
        return float(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid investment time horizon response value.",
        ) from exc


def _get_prediction_window(horizon_months: float) -> tuple[date, date, int]:
    today = date.today()
    if horizon_months < 6:
        anchor_date = _add_months(
            today - timedelta(days=2),
            int(horizon_months) - 6,
        )
        lookback_years = 4
    else:
        anchor_date = _add_months(today, -6)
        lookback_years = 3

    start_date = _add_months(anchor_date, -(lookback_years * 12))
    return start_date, anchor_date, lookback_years


def _get_master_prediction_returns_array(
    db: psycopg2.extensions.connection,
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> "object":
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Missing pandas dependency required to build master predictions matrix.",
        ) from exc

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT date, symbol, predictionreturn
            FROM masterpredictions
            WHERE symbol = ANY(%s)
              AND date BETWEEN %s AND %s
            ORDER BY date, symbol
            """,
            (symbols, start_date, end_date),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No master prediction return data found for the requested symbols and range.",
        )

    df = pd.DataFrame(rows)
    df["predictionreturn"] = df["predictionreturn"].astype(float)

    missing = set(symbols) - set(df["symbol"].unique())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Missing master prediction data for symbols: {sorted(missing)}",
        )

    returns_df = df.pivot(
        index="date",
        columns="symbol",
        values="predictionreturn",
    ).sort_index()
    returns_df = returns_df.reindex(columns=symbols)
    returns_df = returns_df.dropna(how="any")
    if returns_df.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Not enough master prediction data to build the returns matrix.",
        )

    return returns_df.to_numpy()


def _get_predicted_returns_array(
    db: psycopg2.extensions.connection,
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> "object":
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Missing pandas dependency required to compute returns from predicted close data.",
        ) from exc

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT date, symbol, close
            FROM stock_predicted_close
            WHERE symbol = ANY(%s)
              AND date BETWEEN %s AND %s
            ORDER BY date, symbol
            """,
            (symbols, start_date, end_date),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No predicted close data found for the requested symbols and range.",
        )

    df = pd.DataFrame(rows)
    df["close"] = df["close"].astype(float)

    missing = set(symbols) - set(df["symbol"].unique())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Missing predicted close data for symbols: {sorted(missing)}",
        )

    prices_df = df.pivot(
        index="date",
        columns="symbol",
        values="close",
    ).sort_index()
    prices_df = prices_df.reindex(columns=symbols)
    returns_df = prices_df.pct_change().dropna(how="any")
    if returns_df.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Not enough predicted close data to compute returns.",
        )

    return returns_df.to_numpy()


def _random_allocations(symbols: list[str]) -> list[tuple[str, float]]:
    weights = [random.random() for _ in symbols]
    total = sum(weights)
    percentages = [round(w / total * 100, 2) for w in weights]
    # Absorb rounding error into the largest bucket so total == 100.00 exactly
    diff = round(100.0 - sum(percentages), 2)
    percentages[percentages.index(max(percentages))] += diff
    return list(zip(symbols, percentages))


def _weights_to_allocations(weight_dict: dict[str, float]) -> list[tuple[str, float]]:
    if not weight_dict:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GA did not return any portfolio weights.",
        )

    sorted_items = sorted(weight_dict.items(), key=lambda item: item[1], reverse=True)
    symbols = [symbol for symbol, _ in sorted_items]
    percentages = [round(float(weight) * 100, 2) for _, weight in sorted_items]

    diff = round(100.0 - sum(percentages), 2)
    percentages[percentages.index(max(percentages))] += diff
    return [(symbol, float(pct)) for symbol, pct in zip(symbols, percentages)]


def create_portfolio(
    db: psycopg2.extensions.connection,
    user_id: str,
    data: CreatePortfolioRequest,
) -> PortfolioResponse:
    questionnaire_id = str(data.questionnaire_id)

    with db.cursor() as cur:
        # Verify the questionnaire belongs to this user
        cur.execute(
            """
            SELECT q.questionnaire_id,
                   q.assessed_risk,
                   (
                       SELECT qr.question_response
                       FROM question_responses qr
                       JOIN questions qs ON qs.question_id = qr.fk_question_id
                       WHERE qr.fk_questionnaire_id = q.questionnaire_id
                         AND qs.question_id_cfa = %s
                       LIMIT 1
                   ) AS time_horizon_response
            FROM questionnaires q
            WHERE q.questionnaire_id = %s AND q.fk_user_id = %s
            """,
            (_TIME_HORIZON_CFA, questionnaire_id, user_id),
        )
        q_row = cur.fetchone()

    if not q_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found or does not belong to the current user.",
        )

    if not q_row.get("time_horizon_response"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investment time horizon response not found for questionnaire.",
        )

    symbols = [s.upper() for s in data.symbols]

    try:
        horizon_months = _parse_numeric_response(q_row["time_horizon_response"])
        master_start_date, master_end_date, _lookback_years = _get_prediction_window(
            horizon_months
        )
        returns_start_date = _add_months(date.today(), -48)
        returns_end_date = date.today()
        apply_blue_chip = horizon_months > 6

        _master_predictions = _get_master_prediction_returns_array(
            db,
            symbols,
            start_date=master_start_date,
            end_date=master_end_date,
        )
        _predicted_returns = _get_predicted_returns_array(
            db,
            symbols,
            start_date=returns_start_date,
            end_date=returns_end_date,
        )

        seed = None
        initial_population = np.random.default_rng(seed).uniform(
            0,
            GENE_UPPER_BOUND,
            size=(POP_SIZE, len(symbols)),
        )
        best_result, _best_per_gen, _mean_per_gen = run_ga_forward(
            initial_population=initial_population,
            asset_names=symbols,
            returns=_predicted_returns,
            master_outputs=_master_predictions,
            apply_blue_chip=apply_blue_chip,
        )

        allocations = _weights_to_allocations(best_result.get("weight_dict", {}))
    except Exception:
        allocations = _random_allocations(symbols)

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO portfolios (fk_user_id, fk_questionnaire_id)
            VALUES (%s, %s)
            RETURNING portfolio_id, created_at
            """,
            (user_id, questionnaire_id),
        )
        portfolio_row = cur.fetchone()
        portfolio_id = portfolio_row["portfolio_id"]
        created_at = portfolio_row["created_at"]

        cur.executemany(
            """
            INSERT INTO portfolio_stock_allocations (fk_portfolio_id, symbol, allocation_percentage)
            VALUES (%s, %s, %s)
            """,
            [(str(portfolio_id), symbol, pct) for symbol, pct in allocations],
        )

        # Fetch stock names in one query
        symbols_list = [s for s, _ in allocations]
        cur.execute(
            "SELECT symbol, stock_name FROM kse30_stocks WHERE symbol = ANY(%s)",
            (symbols_list,),
        )
        name_map: dict[str, str] = {row["symbol"]: row["stock_name"] for row in cur.fetchall()}

    return PortfolioResponse(
        portfolio_id=portfolio_id,
        questionnaire_id=data.questionnaire_id,
        assessed_risk=q_row["assessed_risk"],
        created_at=created_at,
        allocations=[
            PortfolioStockSchema(
                symbol=symbol,
                stock_name=name_map.get(symbol),
                allocation_percentage=pct,
            )
            for symbol, pct in allocations
        ],
    )


def get_user_portfolios(
    db: psycopg2.extensions.connection,
    user_id: str,
) -> list[PortfolioResponse]:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT p.portfolio_id, p.fk_questionnaire_id, p.created_at,
                   q.assessed_risk
            FROM portfolios p
            JOIN questionnaires q ON q.questionnaire_id = p.fk_questionnaire_id
            WHERE p.fk_user_id = %s
            ORDER BY p.created_at DESC
            """,
            (user_id,),
        )
        portfolio_rows = cur.fetchall()

        if not portfolio_rows:
            return []

        portfolio_ids = [str(row["portfolio_id"]) for row in portfolio_rows]

        cur.execute(
            """
            SELECT psa.fk_portfolio_id, psa.symbol, psa.allocation_percentage,
                   k.stock_name
            FROM portfolio_stock_allocations psa
            LEFT JOIN kse30_stocks k ON k.symbol = psa.symbol
            WHERE psa.fk_portfolio_id = ANY(%s::uuid[])
            """,
            (portfolio_ids,),
        )
        allocation_rows = cur.fetchall()

    # Group allocations by portfolio_id
    alloc_map: dict[str, list[PortfolioStockSchema]] = {}
    for row in allocation_rows:
        pid = str(row["fk_portfolio_id"])
        alloc_map.setdefault(pid, []).append(
            PortfolioStockSchema(
                symbol=row["symbol"],
                stock_name=row["stock_name"],
                allocation_percentage=float(row["allocation_percentage"]),
            )
        )

    return [
        PortfolioResponse(
            portfolio_id=row["portfolio_id"],
            questionnaire_id=row["fk_questionnaire_id"],
            assessed_risk=row["assessed_risk"],
            created_at=row["created_at"],
            allocations=alloc_map.get(str(row["portfolio_id"]), []),
        )
        for row in portfolio_rows
    ]
