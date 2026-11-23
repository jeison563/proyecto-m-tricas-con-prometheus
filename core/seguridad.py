#core/seguridad.py
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from data_base.sql_create_tables import User, get_db

_ph = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)

# Hash falso: se verifica cuando el email no existe, para que el tiempo de respuesta
# no delate qué correos están registrados.
DUMMY_HASH = _ph.hash("contraseña-falsa-para-igualar-tiempos")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, rol: str) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _no_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise _no_autenticado()
    try:
        payload = jwt.decode(
            creds.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],        # nunca aceptes el algoritmo que dice el token
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise _no_autenticado()

    user = await db.get(User, user_id)
    if user is None or not user.activo:
        raise _no_autenticado()
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.rol != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol admin")
    return user
