#routes/auth.py
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.seguridad import (
    DUMMY_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from data_base.sql_create_tables import User, get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class RegistroIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=201)
async def register(datos: RegistroIn, db: AsyncSession = Depends(get_db)):
    email = datos.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado")

    # argon2 es intencionalmente lento (consume CPU): se ejecuta en un hilo
    password_hash = await asyncio.to_thread(hash_password, datos.password)
    user = User(email=email, password_hash=password_hash, rol="user")
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:          # dos registros simultáneos con el mismo correo
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado")
    return {"id": user.id, "email": user.email}


@router.post("/login", response_model=TokenOut)
async def login(datos: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == datos.email.lower()))
    password_hash = user.password_hash if user else DUMMY_HASH
    ok = await asyncio.to_thread(verify_password, password_hash, datos.password)
    if user is None or not ok or not user.activo:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return TokenOut(access_token=create_access_token(user.id, user.rol))


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "rol": user.rol}
