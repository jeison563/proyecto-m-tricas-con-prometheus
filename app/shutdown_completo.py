# app/shutdown_completo.py
import logging

from data_base.engine_sql import close_engine
from temporal.cliente_temporal_connet import TemporalClientFactory

logger = logging.getLogger(__name__)


async def shutdown(client=None):
    try:
        await TemporalClientFactory.close(client)
    except Exception:
        logger.exception("error al cerrar temporal")

    try:
        await close_engine()
    except Exception:
        logger.exception("error al cerrar motor de SQL")

