import psycopg2.extensions
from fastapi import HTTPException, status
import pandas as pd

from app.schemas.recommendations import (
    StockRecommendationSchema,
    StockRecommendationsRequest,
    StockRecommendationsResponse,
)

_TIER_RANGES = {
    "high": (1, 10),
    "moderate": (9, 22),
    "low": (20, 30),
}

def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily simple returns from closing prices.
        r_t = (close_t - close_{t-1}) / close_{t-1}
    Returns:
        DataFrame shape (T-1, N).
    """
    returns = prices.pct_change().dropna()
    print(f"\n  Returns matrix : {returns.shape[0]} days × {returns.shape[1]} assets")
    return returns
def get_stock_recommendations(
    db: psycopg2.extensions.connection,
    data: StockRecommendationsRequest,
) -> StockRecommendationsResponse:
    rank_min, rank_max = _TIER_RANGES[data.risk_tier]

    with db.cursor() as cur:
        cur.execute(
            """
            WITH latest_180 AS (
                SELECT
                    symbol,
                    expected_volatility_180d,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM garch_volatility_predictions
                WHERE expected_volatility_180d IS NOT NULL
            ),
            symbol_avg AS (
                SELECT
                    symbol,
                    AVG(expected_volatility_180d) AS avg_volatility
                FROM latest_180
                WHERE rn <= 180
                GROUP BY symbol
            ),
            symbol_ranked AS (
                SELECT
                    symbol,
                    avg_volatility,
                    ROW_NUMBER() OVER (ORDER BY avg_volatility DESC) AS volatility_rank
                FROM symbol_avg
            )
            SELECT sr.symbol, k.stock_name, sr.avg_volatility, sr.volatility_rank
            FROM symbol_ranked sr
            LEFT JOIN kse30_stocks k ON k.symbol = sr.symbol
            WHERE sr.volatility_rank BETWEEN %s AND %s
            ORDER BY sr.volatility_rank
            """,
            (rank_min, rank_max),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No volatility predictions found in the database.",
        )

    return StockRecommendationsResponse(
        risk_tier=data.risk_tier,
        stocks=[
            StockRecommendationSchema(
                symbol=row["symbol"],
                stock_name=row["stock_name"],
                avg_volatility=float(row["avg_volatility"]),
                volatility_rank=row["volatility_rank"],
            )
            for row in rows
        ],
    )
