# temporal/workflows.py
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

ITERACIONES_POR_EJECUCION = 500           # ~7.500 eventos, muy por debajo del límite
INTERVALO = timedelta(seconds=5)
ENFRIAMIENTO_GEMINI = timedelta(minutes=5)

RETRY = RetryPolicy(maximum_attempts=3, non_retryable_error_types=["ValueError"])


@workflow.defn
class MiWorkflow:
    async def _ejecutar(self, nombre: str, arg=None, timeout=timedelta(minutes=1)):
        """Ejecuta una activity; si falla, lo registra y devuelve None (no mata el monitor)."""
        try:
            if arg is None:
                return await workflow.execute_activity(
                    nombre, start_to_close_timeout=timeout, retry_policy=RETRY
                )
            return await workflow.execute_activity(
                nombre, arg, start_to_close_timeout=timeout, retry_policy=RETRY
            )
        except ActivityError:
            workflow.logger.exception("Falló la activity %s", nombre)
            return None

    @workflow.run
    async def run(self) -> None:
        ultimo_analisis = None

        await self._ejecutar("mantenimiento_db", timeout=timedelta(minutes=5))

        for _ in range(ITERACIONES_POR_EJECUCION):
            metrics_system = await self._ejecutar("_psutil", timeout=timedelta(seconds=30))
            if metrics_system is None:
                await workflow.sleep(INTERVALO)
                continue

            comparacion = await self._ejecutar("comparation", metrics_system)

            await self._ejecutar("upsert_metrics_data", {"metrics": metrics_system})

            if comparacion and comparacion["alerta"]:
                ahora = workflow.now()
                if ultimo_analisis is None or ahora - ultimo_analisis >= ENFRIAMIENTO_GEMINI:
                    analysis = await self._ejecutar(
                        "analisis_gemini",
                        {"metrics": metrics_system, "alertas": comparacion["alertas"]},
                        timeout=timedelta(minutes=2),
                    )
                    ultimo_analisis = ahora
                    if analysis is not None:
                        await self._ejecutar(
                            "upsert_analisis",
                            {"metrics": metrics_system, "analisis_alerta": analysis},
                        )

            await workflow.sleep(INTERVALO)

        # Reinicia el historial y sigue monitoreando
        workflow.continue_as_new()
