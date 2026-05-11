from typing import Literal

from pydantic import BaseModel


class StockRecommendationSchema(BaseModel):
    symbol: str
    stock_name: str | None
    avg_volatility: float
    volatility_rank: int


class StockRecommendationsRequest(BaseModel):
    risk_tier: Literal["high", "moderate", "low"]


class StockRecommendationsResponse(BaseModel):
    risk_tier: str
    stocks: list[StockRecommendationSchema]
