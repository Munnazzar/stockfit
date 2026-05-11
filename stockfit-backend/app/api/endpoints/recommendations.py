import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.db.database import get_db
from app.schemas.recommendations import StockRecommendationsRequest, StockRecommendationsResponse
from app.services import recommendations_service

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.post("/stocks", response_model=StockRecommendationsResponse)
def get_stock_recommendations(
    body: StockRecommendationsRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
) -> StockRecommendationsResponse:
    return recommendations_service.get_stock_recommendations(db, body)
