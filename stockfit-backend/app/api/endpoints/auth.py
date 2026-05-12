import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.schemas.user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
    VerifyResetCodeRequest,
)
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


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MessageResponse:
    return auth_service.forgot_password(db, body)


@router.post("/verify-reset-code", response_model=MessageResponse)
def verify_reset_code(
    body: VerifyResetCodeRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MessageResponse:
    return auth_service.verify_reset_code(db, body)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MessageResponse:
    return auth_service.reset_password(db, body)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> MessageResponse:
    return auth_service.change_password(db, user_id, body)


@router.patch("/me", response_model=UserResponse)
def update_user(
    body: UpdateUserRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> UserResponse:
    return auth_service.update_user(db, user_id, body)
