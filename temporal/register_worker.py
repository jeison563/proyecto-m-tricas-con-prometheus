# temporal/register_worker.py
import logging

from temporalio.service import RPCError
from temporalio.worker import Worker

from activitys.activity_comparations import comparation
from activitys.activity_gemini import analisis_gemini
from activitys.activity_psutil import _psutil
from activitys.guardar_analisis_sql import upsert_analisis
from activitys.guardar_metricas_sql import upsert_metrics_data
from activitys.mantenimiento_db import mantenimiento_db
from core.config import TASK_QUEUE, WORKFLOW_CONCURRENCY
from temporal.cliente_temporal_connet import TemporalClientFactory
from temporal.workflows import MiWorkflow


class Registry_worker:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None

    async def create_worker(self):
        try:
            self.client = await TemporalClientFactory.client_conn(with_metrics=True)
            worker = Worker(
                self.client,
                task_queue=TASK_QUEUE,
                workflows=[MiWorkflow],
                activities=[
                    _psutil,
                    comparation,
                    upsert_metrics_data,
                    analisis_gemini,
                    upsert_analisis,
                    mantenimiento_db
                ],
                max_concurrent_activities=WORKFLOW_CONCURRENCY,
            )
            self.logger.info("Worker escuchando la cola %s", TASK_QUEUE)
            await worker.run()

        except ValueError as e:
            self.logger.error(
                "Configuración inválida del worker (¿falta @activity.defn o @workflow.defn?): %s", e
            )
            raise
        except RPCError as e:
            self.logger.error("Worker perdió conexión con Temporal: %s", e)
            raise
        except Exception:
            self.logger.exception("error inesperado en el worker")
            raise
