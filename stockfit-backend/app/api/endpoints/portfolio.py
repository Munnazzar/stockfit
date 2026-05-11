import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.schemas.portfolio import CreatePortfolioRequest, PortfolioResponse
from app.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.post("", response_model=PortfolioResponse, status_code=201)
def create_portfolio(
    body: CreatePortfolioRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> PortfolioResponse:
    return portfolio_service.create_portfolio(db, user_id, body)


@router.get("", response_model=list[PortfolioResponse])
def get_user_portfolios(
    db: psycopg2.extensions.connection = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[PortfolioResponse]:
    return portfolio_service.get_user_portfolios(db, user_id)
