#temporal/cliente_temporal_connet.py
import logging

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.runtime import PrometheusConfig, Runtime, TelemetryConfig
from temporalio.service import RPCError

from core.config import TEMPORAL_HOST, TEMPORAL_NAMESPACE

logger = logging.getLogger(__name__)

# Puerto donde el worker publica las métricas internas del SDK de Temporal
# (prometheus.yml las recoge en worker:9464).
SDK_METRICS_BIND = "0.0.0.0:9464"

_runtime_con_metricas: Runtime | None = None


def _get_runtime_con_metricas() -> Runtime:
    """Un único Runtime por proceso: crear dos intentaría abrir dos veces el puerto 9464."""
    global _runtime_con_metricas
    if _runtime_con_metricas is None:
        _runtime_con_metricas = Runtime(
            telemetry=TelemetryConfig(
                # counters_total_suffix=True para que los contadores se llamen
                # *_total, como esperan las reglas de prometheus/alert_rules.yml
                metrics=PrometheusConfig(bind_address=SDK_METRICS_BIND, counters_total_suffix=True)
            )
        )
    return _runtime_con_metricas


class TemporalClientFactory:
    @staticmethod
    async def client_conn(with_metrics: bool = False) -> Client:
        """Conecta con Temporal. with_metrics=True (worker) publica las métricas del SDK."""
        runtime = _get_runtime_con_metricas() if with_metrics else None
        try:
            client = await Client.connect(
                TEMPORAL_HOST,
                data_converter=pydantic_data_converter,
                runtime=runtime,
                namespace=TEMPORAL_NAMESPACE,
            )
        except RPCError as e:
            logger.error("Temporal rechazó la conexión: %s", e)
            raise
        except ValueError as e:
            logger.error("TEMPORAL_HOST mal configurado: %s", e)
            raise
        except (ConnectionRefusedError, OSError) as e:
            logger.error("No se pudo alcanzar el host de Temporal: %s", e)
            raise
        except TimeoutError as e:
            logger.error("Timeout al conectar con Temporal: %s", e)
            raise
        except Exception:
            logger.exception("error inesperado al conectar con el cliente")
            raise

        logger.info("Cliente conectado a Temporal en %s", TEMPORAL_HOST)
        return client

    @staticmethod
    async def close(client: Client | None) -> None:
        if client is None:
            return
        try:
            # Las versiones actuales de temporalio no tienen Client.close(); se mantiene
            # la comprobación por si una versión futura lo añade.
            if hasattr(client, "close"):
                await client.close()
        except Exception:
            logger.exception("error al cerrar cliente temporal")
            raise
