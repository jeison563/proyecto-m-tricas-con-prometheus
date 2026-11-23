# routes/historial.py
import math
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import PROMETHEUS_URL
from data_base.sql_create_tables import Host, Metrics1m, get_db
from routes.hosts import host_del_usuario

# Rutas por host (/hosts/{host_id}/historial y /hosts/{host_id}/promedios): son las que
# consume frontend/app.js, y solo responden si el host pertenece al usuario autenticado.
router = APIRouter(prefix="/hosts", tags=["historial"])

METRICAS = ("cpu_percent", "memory_percent", "memory_available", "disk_percent", "disk_used")
_UNIDADES = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_MAX_PUNTOS = 10000  # Prometheus rechaza más de 11.000 por serie


class PromedioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    minuto: datetime
    muestras: int
    cpu_avg: float
    cpu_max: int
    memory_avg: float
    memory_max: int
    disk_avg: float
    disk_max: int
    memory_available_min: int
    disk_used_max: int


@router.get("/{host_id}/historial")
async def obtener_historial(
    host: Host = Depends(host_del_usuario),
    minutos: int = Query(default=60, ge=1, le=10080),
    paso: str = Query(default="15s", pattern=r"^\d+[smhd]$"),
):
    ahora = datetime.now(timezone.utc)
    inicio = ahora - timedelta(minutes=minutos)

    paso_seg = int(paso[:-1]) * _UNIDADES[paso[-1]]
    paso_seg = max(paso_seg, math.ceil(minutos * 60 / _MAX_PUNTOS), 1)

    # host.id es un entero que ya validó la base de datos: es seguro incrustarlo en la consulta
    consulta = '{__name__=~"' + "|".join(METRICAS) + f'",job="worker-app",host="{host.id}"' + "}"
    params = {
        "query": consulta,
        "start": inicio.timestamp(),
        "end": ahora.timestamp(),
        "step": f"{paso_seg}s",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)
            response.raise_for_status()
            resultado = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="No fue posible consultar Prometheus") from exc

    if resultado.get("status") != "success":
        raise HTTPException(status_code=502, detail="Prometheus no pudo ejecutar la consulta")

    return {
        "desde": inicio.isoformat(),
        "hasta": ahora.isoformat(),
        "minutos": minutos,
        "paso": f"{paso_seg}s",
        "metricas": resultado["data"]["result"],
    }


@router.get("/{host_id}/promedios", response_model=list[PromedioOut])
async def obtener_promedios(
    host: Host = Depends(host_del_usuario),
    horas: int = Query(default=1, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    filas = await db.scalars(
        select(Metrics1m)
        .where(Metrics1m.host_id == host.id, Metrics1m.minuto >= desde)
        .order_by(Metrics1m.minuto)
    )
    return filas.all()
