#data_base/mantenimiento.py
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from core.config import (
    AVG_RETENTION_DAYS,
    PARTITIONS_AHEAD_DAYS,
    RAW_RETENTION_DAYS,
    ROLLUP_LOOKBACK_HOURS,
)
from data_base.engine_sql import creation_engine

logger = logging.getLogger(__name__)

PREFIJO = "metrics_p"          # metrics_p20261025

SQL_ROLLUP = text(
    """
    INSERT INTO metrics_1m (
        host_id, minuto, muestras,
        cpu_avg, cpu_max, memory_avg, memory_max, disk_avg, disk_max,
        memory_available_min, disk_used_max
    )
    SELECT
        host_id,
        date_trunc('minute', created_at) AS minuto,
        count(*),
        avg(cpu_percent),    max(cpu_percent),
        avg(memory_percent), max(memory_percent),
        avg(disk_percent),   max(disk_percent),
        min(memory_available), max(disk_used)
    FROM metrics
    WHERE created_at >= :desde
      AND created_at <  date_trunc('minute', now())
    GROUP BY host_id, date_trunc('minute', created_at)
    ON CONFLICT (host_id, minuto) DO UPDATE SET
        muestras             = EXCLUDED.muestras,
        cpu_avg              = EXCLUDED.cpu_avg,
        cpu_max              = EXCLUDED.cpu_max,
        memory_avg           = EXCLUDED.memory_avg,
        memory_max           = EXCLUDED.memory_max,
        disk_avg             = EXCLUDED.disk_avg,
        disk_max             = EXCLUDED.disk_max,
        memory_available_min = EXCLUDED.memory_available_min,
        disk_used_max        = EXCLUDED.disk_used_max
    """
)

SQL_HIJAS = text(
    """
    SELECT c.relname
    FROM pg_inherits i
    JOIN pg_class c ON c.oid = i.inhrelid
    WHERE i.inhparent = 'metrics'::regclass
    """
)


def _hoy_utc() -> date:
    return datetime.now(timezone.utc).date()


async def crear_particiones() -> list[str]:
    """Asegura que existan las particiones de hoy y de los próximos N días."""
    hoy = _hoy_utc()
    aseguradas = []
    async with creation_engine.engine().begin() as conn:
        for i in range(PARTITIONS_AHEAD_DAYS + 1):
            dia = hoy + timedelta(days=i)
            sig = dia + timedelta(days=1)
            nombre = f"{PREFIJO}{dia:%Y%m%d}"
            await conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {nombre} PARTITION OF metrics "
                    f"FOR VALUES FROM ('{dia} 00:00:00+00') TO ('{sig} 00:00:00+00')"
                )
            )
            aseguradas.append(nombre)
    return aseguradas


async def rollup_1m() -> int:
    """Resume a 1 fila/minuto/host los últimos ROLLUP_LOOKBACK_HOURS. Es idempotente."""
    desde = datetime.now(timezone.utc) - timedelta(hours=ROLLUP_LOOKBACK_HOURS)
    desde = desde.replace(second=0, microsecond=0)   # empieza en un minuto COMPLETO
    async with creation_engine.engine().begin() as conn:
        resultado = await conn.execute(SQL_ROLLUP, {"desde": desde})
    return resultado.rowcount


async def eliminar_particiones_viejas() -> list[str]:
    """Borra (DROP) las particiones diarias con más de RAW_RETENTION_DAYS días."""
    limite = _hoy_utc() - timedelta(days=RAW_RETENTION_DAYS)
    eliminadas = []
    async with creation_engine.engine().begin() as conn:
        filas = await conn.execute(SQL_HIJAS)
        for (nombre,) in filas.all():
            if not nombre.startswith(PREFIJO):
                continue
            sufijo = nombre[len(PREFIJO):]
            if len(sufijo) != 8 or not sufijo.isdigit():
                continue
            try:
                dia = datetime.strptime(sufijo, "%Y%m%d").date()
            except ValueError:
                continue
            if dia < limite:
                # nombre validado arriba: solo prefijo fijo + 8 dígitos
                await conn.execute(text(f"DROP TABLE IF EXISTS {nombre}"))
                eliminadas.append(nombre)
    return eliminadas


async def purgar_promedios() -> int:
    limite = datetime.now(timezone.utc) - timedelta(days=AVG_RETENTION_DAYS)
    async with creation_engine.engine().begin() as conn:
        resultado = await conn.execute(
            text("DELETE FROM metrics_1m WHERE minuto < :limite"), {"limite": limite}
        )
    return resultado.rowcount


async def mantenimiento() -> dict:
    # Orden importante: 1) crear lo que hará falta, 2) resumir, 3) borrar lo viejo
    aseguradas = await crear_particiones()
    resumidas = await rollup_1m()
    eliminadas = await eliminar_particiones_viejas()
    purgados = await purgar_promedios()
    resultado = {
        "particiones_aseguradas": len(aseguradas),
        "filas_resumidas": resumidas,
        "particiones_eliminadas": eliminadas,
        "promedios_purgados": purgados,
    }
    logger.info("mantenimiento BD: %s", resultado)
    return resultado
