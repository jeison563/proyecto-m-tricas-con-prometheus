#activitys/activity_comparations.py
from temporalio import activity

from core.config import MAX_PERCENT


@activity.defn
async def comparation(data_system: dict) -> dict:
    recursos = ("cpu_percent", "memory_percent", "disk_percent")
    alertas = [
        f"{r}={data_system[r]}%" for r in recursos if data_system[r] >= MAX_PERCENT
    ]
    return {"alerta": bool(alertas), "alertas": alertas}
