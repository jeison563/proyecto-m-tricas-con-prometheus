# activitys/guardar_metricas_sql.py
import logging
from temporalio import activity
from data_base.sql_create_tables import insert_metrics_data
from core.config import HOST_ID

logger = logging.getLogger(__name__)


@activity.defn
async def upsert_metrics_data(data: dict):
    metrics = data.get("metrics")
    if not metrics:
        raise ValueError("métricas vacías")
    await insert_metrics_data({**metrics, "host_id": HOST_ID})
    logger.info("metricas insertadas correctamente")
