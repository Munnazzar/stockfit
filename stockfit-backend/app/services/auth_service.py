import random
import smtplib
import string
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import psycopg2.extensions
from fastapi import HTTPException, status
from jose import jwt
import bcrypt

from app.core.config import get_settings
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
            INSERT INTO users (email, password_hash, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id, email, first_name, last_name, created_at
            """,
            (data.email, password_hash, data.first_name, data.last_name),
        )
        row = cur.fetchone()

    token = _create_access_token(str(row["user_id"]))
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=row["user_id"],
            email=row["email"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            created_at=row["created_at"],
        ),
    )


def login(db: psycopg2.extensions.connection, data: LoginRequest) -> TokenResponse:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, email, first_name, last_name, created_at, password_hash
            FROM users WHERE email = %s
            """,
            (data.email,),
        )
        row = cur.fetchone()

    if not row or not _verify_password(data.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = _create_access_token(str(row["user_id"]))
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=row["user_id"],
            email=row["email"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            created_at=row["created_at"],
        ),
    )


def _generate_reset_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_reset_email(to_email: str, code: str) -> None:
    settings = get_settings()
    body = (
        f"Your StockFit password reset code is: {code}\n\n"
        f"This code expires in {settings.reset_code_expire_minutes} minutes.\n"
        "If you did not request a password reset, ignore this email."
    )
    msg = MIMEText(body)
    msg["Subject"] = "StockFit — Password Reset Code"
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"] = to_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, to_email, msg.as_string())


def forgot_password(db: psycopg2.extensions.connection, data: ForgotPasswordRequest) -> MessageResponse:
    with db.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE email = %s", (data.email,))
        row = cur.fetchone()

    # Always return success to prevent email enumeration
    if not row:
        return MessageResponse(message="If that email exists, a reset code has been sent.")

    code = _generate_reset_code()
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.reset_code_expire_minutes)

    with db.cursor() as cur:
        # Invalidate any existing unused codes for this user
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE fk_user_id = %s AND used = FALSE",
            (row["user_id"],),
        )
        cur.execute(
            """
            INSERT INTO password_reset_tokens (fk_user_id, code, expires_at)
            VALUES (%s, %s, %s)
            """,
            (row["user_id"], code, expires_at),
        )

    _send_reset_email(data.email, code)
    return MessageResponse(message="If that email exists, a reset code has been sent.")


def verify_reset_code(db: psycopg2.extensions.connection, data: VerifyResetCodeRequest) -> MessageResponse:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT prt.token_id
            FROM password_reset_tokens prt
            JOIN users u ON u.user_id = prt.fk_user_id
            WHERE u.email = %s
              AND prt.code = %s
              AND prt.used = FALSE
              AND prt.expires_at > NOW()
            """,
            (data.email, data.code),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    return MessageResponse(message="Code is valid.")


def reset_password(db: psycopg2.extensions.connection, data: ResetPasswordRequest) -> MessageResponse:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT prt.token_id, u.user_id
            FROM password_reset_tokens prt
            JOIN users u ON u.user_id = prt.fk_user_id
            WHERE u.email = %s
              AND prt.code = %s
              AND prt.used = FALSE
              AND prt.expires_at > NOW()
            """,
            (data.email, data.code),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    new_hash = _hash_password(data.new_password)

    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE user_id = %s",
            (new_hash, row["user_id"]),
        )
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE token_id = %s",
            (row["token_id"],),
        )

    return MessageResponse(message="Password updated successfully.")


def change_password(
    db: psycopg2.extensions.connection,
    user_id: str,
    data: ChangePasswordRequest,
) -> MessageResponse:
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()

    if not row or not _verify_password(data.current_password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    new_hash = _hash_password(data.new_password)

    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE user_id = %s",
            (new_hash, user_id),
        )

    return MessageResponse(message="Password changed successfully.")


def update_user(
    db: psycopg2.extensions.connection,
    user_id: str,
    data: UpdateUserRequest,
) -> UserResponse:
    fields = {k: v for k, v in data.model_dump().items() if v is not None}

    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    if "email" in fields:
        with db.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE email = %s AND user_id != %s",
                (fields["email"], user_id),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists.",
                )

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    values = list(fields.values()) + [user_id]

    with db.cursor() as cur:
        cur.execute(
            f"""
            UPDATE users
            SET {set_clause}, updated_at = NOW()
            WHERE user_id = %s
            RETURNING user_id, email, first_name, last_name, created_at
            """,
            values,
        )
        row = cur.fetchone()

    return UserResponse(
        user_id=row["user_id"],
        email=row["email"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        created_at=row["created_at"],
    )