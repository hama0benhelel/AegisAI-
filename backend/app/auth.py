import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from app.db import connect, set_tenant

router = APIRouter()
bearer = HTTPBearer(auto_error=False)
hasher = PasswordHasher()

SECRET = os.environ["JWT_SECRET"]
if len(SECRET) < 64:
    raise RuntimeError("JWT_SECRET must contain at least 64 characters.")

ISSUER = "aegisai"
AUDIENCE = "aegisai-api"
TOKEN_SECONDS = 900
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


def unauthorized():
    return HTTPException(
        status_code=401,
        detail="Identifiants ou token invalides",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/auth/login", tags=["Authentication"])
def login(body: LoginInput, response: Response):
    email = body.email.strip().lower()

    with connect() as conn:
        user = conn.execute(
            "SELECT * FROM bws_ai.lookup_login(%s)",
            (email,),
        ).fetchone()

    # Also hash-check unknown accounts to reduce timing differences.
    stored_hash = user["password_hash"] if user else DUMMY_HASH

    try:
        hasher.verify(stored_hash, body.password)
    except (VerificationError, InvalidHashError):
        raise unauthorized() from None

    if user is None or not user["is_active"]:
        raise unauthorized()

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "tenant_id": str(user["tenant_id"]),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + timedelta(seconds=TOKEN_SECONDS),
        },
        SECRET,
        algorithm="HS256",
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_SECONDS,
    }


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()

    try:
        claims = jwt.decode(
            credentials.credentials,
            SECRET,
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "require": [
                    "sub", "tenant_id", "iss", "aud", "iat", "exp"
                ]
            },
        )
        user_id = UUID(claims["sub"])
        tenant_id = UUID(claims["tenant_id"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise unauthorized() from None

    with connect() as conn:
        set_tenant(conn, tenant_id)
        user = conn.execute(
            """
            SELECT id, tenant_id, email, role, is_active
            FROM bws_ai.users
            WHERE id = %s AND tenant_id = %s
            """,
            (user_id, tenant_id),
        ).fetchone()

    if user is None or not user["is_active"]:
        raise unauthorized()

    # The role is read from the DB, not trusted from a client field.
    return user


@router.get("/auth/me", tags=["Authentication"])
def me(user=Depends(current_user)):
    return user


@router.get("/readings", tags=["IoT"])
def readings(
    tenant_id: UUID | None = None,
    user=Depends(current_user),
):
    if tenant_id is not None and tenant_id != user["tenant_id"]:
        raise HTTPException(403, "Accès à un autre tenant interdit")

    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        rows = conn.execute(
            """
            SELECT id, sensor_id, resource, value, unit, measured_at
            FROM bws_ai.readings
            WHERE tenant_id = %s
            ORDER BY measured_at DESC, id
            LIMIT 100
            """,
            (user["tenant_id"],),
        ).fetchall()

    return {"items": rows}
