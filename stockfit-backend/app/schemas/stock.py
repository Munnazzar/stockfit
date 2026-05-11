from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

TimeHorizon = Literal["3d", "30d", "3m", "6m", "1y", "5y"]


class OHLCVCandle(BaseModel):
    date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None


class StockOHLCVResponse(BaseModel):
    symbol: str
    stock_name: str | None
    time_horizon: str
    granularity: str  # e.g. "1d", "2d", "3d", "5d", "7d"
    candles: list[OHLCVCandle]
