import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.db.database import get_db
from app.schemas.user import LoginRequest, SignupRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(
    body: SignupRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
) -> TokenResponse:
    return auth_service.signup(db, body)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
) -> TokenResponse:
    return auth_service.login(db, body)
