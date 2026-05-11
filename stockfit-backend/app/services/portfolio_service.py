import random

import psycopg2.extensions
from fastapi import HTTPException, status

from app.schemas.portfolio import (
    CreatePortfolioRequest,
    PortfolioResponse,
    PortfolioStockSchema,
)


def _random_allocations(symbols: list[str]) -> list[tuple[str, float]]:
    weights = [random.random() for _ in symbols]
    total = sum(weights)
    percentages = [round(w / total * 100, 2) for w in weights]
    # Absorb rounding error into the largest bucket so total == 100.00 exactly
    diff = round(100.0 - sum(percentages), 2)
    percentages[percentages.index(max(percentages))] += diff
    return list(zip(symbols, percentages))


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
            SELECT questionnaire_id, assessed_risk
            FROM questionnaires
            WHERE questionnaire_id = %s AND fk_user_id = %s
            """,
            (questionnaire_id, user_id),
        )
        q_row = cur.fetchone()

    if not q_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found or does not belong to the current user.",
        )

    #TODO: Rand here, change with genetic
    allocations = _random_allocations([s.upper() for s in data.symbols])

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
