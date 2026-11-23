# activitys/guardar_analisis_sql.py
import logging

from temporalio import activity

from core.config import HOST_ID
from data_base.sql_create_tables import insert_metrics_analisis

logger = logging.getLogger(__name__)


@activity.defn
async def upsert_analisis(data: dict):
    if "metrics" not in data or "analisis_alerta" not in data:
        raise ValueError("faltan 'metrics' o 'analisis_alerta'")
    await insert_metrics_analisis(
        {"host_id": HOST_ID, "metricas": data["metrics"], "analisis": data["analisis_alerta"]}
    )
    logger.info("metricas de análisis insertadas correctamente")
