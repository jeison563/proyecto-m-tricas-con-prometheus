#routes/hosts.py
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.seguridad import get_current_user
from data_base.sql_create_tables import Host, User, get_db

router = APIRouter(prefix="/hosts", tags=["hosts"])


class HostIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class HostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime


async def host_del_usuario(
    host_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Host:
    """Devuelve el host SOLO si pertenece al usuario autenticado.
    Si es de otro, responde 404 (no 403) para no revelar que existe."""
    host = await db.scalar(select(Host).where(Host.id == host_id, Host.owner_id == user.id))
    if host is None:
        raise HTTPException(status_code=404, detail="Host no encontrado")
    return host


@router.post("", response_model=HostOut, status_code=201)
async def crear_host(
    datos: HostIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    host = Host(owner_id=user.id, name=datos.name.strip())
    db.add(host)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ya tienes un host con ese nombre")
    await db.refresh(host)          # carga created_at (lo puso la base de datos)
    return host


@router.get("", response_model=list[HostOut])
async def listar_hosts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resultado = await db.scalars(
        select(Host).where(Host.owner_id == user.id).order_by(Host.id)
    )
    return resultado.all()


@router.delete("/{host_id}", status_code=204)
async def borrar_host(
    host: Host = Depends(host_del_usuario),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(host)   # ON DELETE CASCADE borra sus métricas (puede tardar si son muchas)
    await db.commit()
