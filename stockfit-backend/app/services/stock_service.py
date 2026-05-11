import psycopg2.extensions
from fastapi import HTTPException, status

from app.schemas.stock import OHLCVCandle, StockOHLCVResponse, TimeHorizon

# (interval_sql, granularity_label, n_days)
# n_days=1 means plain daily rows — no GROUP BY needed
_HORIZON_CONFIG: dict[str, tuple[str, str, int]] = {
    "3d":  ("5 days",   "1d", 1),
    "30d": ("30 days",  "1d", 1),
    "3m":  ("3 months", "2d", 2),
    "6m":  ("6 months", "3d", 3),
    "1y":  ("1 year",   "5d", 5),
    "5y":  ("5 years",  "7d", 7),
}

_DAILY_SQL = """
    SELECT date, open, high, low, close, volume
    FROM stock_ohlcv
    WHERE symbol = %s
      AND date >= CURRENT_DATE - INTERVAL '{interval}'
    ORDER BY date
"""

# Groups rows into N-day calendar buckets using Unix-epoch floor division.
# The bucket label is the first calendar day of each N-day window.
_NDAY_SQL = """
    SELECT
        TO_TIMESTAMP(
            FLOOR(EXTRACT(EPOCH FROM date) / (86400 * {n})) * 86400 * {n}
        )::date                                             AS date,
        (ARRAY_AGG(open  ORDER BY date ASC))[1]            AS open,
        MAX(high)                                           AS high,
        MIN(low)                                            AS low,
        (ARRAY_AGG(close ORDER BY date DESC))[1]           AS close,
        SUM(volume)::bigint                                 AS volume
    FROM stock_ohlcv
    WHERE symbol = %s
      AND date >= CURRENT_DATE - INTERVAL '{interval}'
    GROUP BY FLOOR(EXTRACT(EPOCH FROM date) / (86400 * {n}))
    ORDER BY date
"""


def get_stock_ohlcv(
    db: psycopg2.extensions.connection,
    symbol: str,
    time_horizon: TimeHorizon,
) -> StockOHLCVResponse:
    symbol = symbol.upper()
    interval, granularity, n_days = _HORIZON_CONFIG[time_horizon]

    sql = (
        _DAILY_SQL.format(interval=interval)
        if n_days == 1
        else _NDAY_SQL.format(interval=interval, n=n_days)
    )

    with db.cursor() as cur:
        cur.execute(sql, (symbol,))
        rows = cur.fetchall()

        cur.execute(
            "SELECT stock_name FROM kse30_stocks WHERE symbol = %s",
            (symbol,),
        )
        name_row = cur.fetchone()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No OHLCV data found for symbol '{symbol}'.",
        )

    return StockOHLCVResponse(
        symbol=symbol,
        stock_name=name_row["stock_name"] if name_row else None,
        time_horizon=time_horizon,
        granularity=granularity,
        candles=[
            OHLCVCandle(
                date=row["date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ],
    )
