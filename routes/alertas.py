# routes/alertas.py
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/alerts")
async def recibir_alertas(payload: dict):
    for alerta in payload.get("alerts", []):
        nombre = alerta.get("labels", {}).get("alertname", "desconocida")
        severidad = alerta.get("labels", {}).get("severity", "?")
        resumen = alerta.get("annotations", {}).get("summary", "")
        logger.warning("[%s] %s (%s): %s", alerta.get("status"), nombre, severidad, resumen)
    return {"ok": True}
