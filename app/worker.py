# app/worker.py
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from prometheus_client import start_http_server

from app.shutdown_completo import shutdown
from temporal.register_worker import Registry_worker

logger = logging.getLogger(__name__)

METRICS_PORT = 9465


async def main():
    start_http_server(METRICS_PORT)
    logger.info("Métricas del worker publicadas en el puerto %d", METRICS_PORT)

    registry = Registry_worker()
    try:
        await registry.create_worker()
    finally:
        await shutdown(registry.client)


if __name__ == "__main__":
    asyncio.run(main())
