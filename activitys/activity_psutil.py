# activitys/activity_psutil.py
import asyncio
import time

import psutil
from temporalio import activity

from core.config import HOST_ID
from metricas.gauges import cpu, disco, disk_used, memory, memory_available, ultima_lectura

_HOST = str(HOST_ID)


def _leer_metricas() -> dict:
    cpu_pct = psutil.cpu_percent(interval=1)
    memoria = psutil.virtual_memory()
    disco_uso = psutil.disk_usage("/")
    return {
        "cpu_percent": round(cpu_pct),
        "memory_percent": round(memoria.percent),
        "memory_available": int(memoria.available),
        "disk_percent": round(disco_uso.percent),
        "disk_used": int(disco_uso.used),
    }


@activity.defn
async def _psutil() -> dict:
    datos = await asyncio.to_thread(_leer_metricas)

    cpu.labels(host=_HOST).set(datos["cpu_percent"])
    memory.labels(host=_HOST).set(datos["memory_percent"])
    memory_available.labels(host=_HOST).set(datos["memory_available"])
    disco.labels(host=_HOST).set(datos["disk_percent"])
    disk_used.labels(host=_HOST).set(datos["disk_used"])
    ultima_lectura.labels(host=_HOST).set(time.time())

    return datos
