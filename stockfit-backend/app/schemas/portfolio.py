from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioStockSchema(BaseModel):
    symbol: str
    stock_name: str | None
    allocation_percentage: float


class CreatePortfolioRequest(BaseModel):
    questionnaire_id: UUID
    symbols: Annotated[list[str], Field(min_length=1, max_length=30)]


class PortfolioResponse(BaseModel):
    portfolio_id: UUID
    questionnaire_id: UUID
    assessed_risk: str | None
    created_at: datetime
    allocations: list[PortfolioStockSchema]
