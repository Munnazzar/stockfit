from datetime import datetime, timedelta, timezone

import psycopg2.extensions
from fastapi import HTTPException, status
from jose import jwt
import bcrypt

from app.core.config import get_settings
from app.schemas.user import LoginRequest, SignupRequest, TokenResponse


def _hash_password(password: str) -> str:
    # bcrypt requires bytes, so we encode the string
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    
    # Decode back to a string
    return hashed_password.decode('utf-8')


def _verify_password(plain: str, hashed: str) -> bool:
    # Both the plain password and the stored hash need to be bytes for the check
    password_bytes = plain.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def _create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def signup(db: psycopg2.extensions.connection, data: SignupRequest) -> TokenResponse:
    with db.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE email = %s", (data.email,))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        password_hash = _hash_password(data.password)
        cur.execute(
            """
            INSERT INTO users (email, password_hash, first_name, last_name, risk_tolerance)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id
            """,
            (data.email, password_hash, data.first_name, data.last_name, data.risk_tolerance),
        )
        row = cur.fetchone()

    token = _create_access_token(str(row["user_id"]))
    return TokenResponse(access_token=token)


def login(db: psycopg2.extensions.connection, data: LoginRequest) -> TokenResponse:
    with db.cursor() as cur:
        cur.execute(
            "SELECT user_id, password_hash FROM users WHERE email = %s", (data.email,)
        )
        row = cur.fetchone()

    if not row or not _verify_password(data.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = _create_access_token(str(row["user_id"]))
    return TokenResponse(access_token=token)