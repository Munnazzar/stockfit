import psycopg2.extensions
from fastapi import APIRouter, Depends, Query

from app.db.database import get_db
from app.schemas.stock import StockOHLCVResponse, TimeHorizon
from app.services import stock_service

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/{symbol}/ohlcv", response_model=StockOHLCVResponse)
def get_stock_ohlcv(
    symbol: str,
    time_horizon: TimeHorizon = Query(..., description="3d | 30d | 3m | 6m | 1y | 5y"),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> StockOHLCVResponse:
    return stock_service.get_stock_ohlcv(db, symbol, time_horizon)
