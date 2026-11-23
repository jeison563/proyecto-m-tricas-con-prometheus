# tests/test_workflow.py
from temporalio import activity
from temporalio.client import WorkflowExecutionStatus
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporal.workflows import MiWorkflow

DATOS = {"cpu_percent": 99, "memory_percent": 10, "memory_available": 1,
         "disk_percent": 10, "disk_used": 1}

async def test_workflow_sobrevive_si_gemini_falla():
    llamadas = {"psutil": 0}

    @activity.defn(name="_psutil")
    async def psutil_mock() -> dict:
        llamadas["psutil"] += 1
        return DATOS

    @activity.defn(name="comparation")
    async def comparation_mock(d: dict) -> dict:
        return {"alerta": True, "alertas": ["cpu_percent=99%"]}

    @activity.defn(name="upsert_metrics_data")
    async def upsert_m(d: dict): ...

    @activity.defn(name="publicar_metricas")
    async def publicar(d: dict): ...

    @activity.defn(name="analisis_gemini")
    async def gemini_falla(d: dict):
        raise RuntimeError("Gemini caído")

    @activity.defn(name="upsert_analisis")
    async def upsert_a(d: dict): ...

    # El workflow llama primero a "mantenimiento_db": sin este mock la activity no estaría
    # registrada y el test pasaba solo porque el workflow ignora el fallo.
    @activity.defn(name="mantenimiento_db")
    async def mantenimiento_mock() -> dict:
        return {}

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue="t", workflows=[MiWorkflow],
                          activities=[psutil_mock, comparation_mock, upsert_m,
                                      publicar, gemini_falla, upsert_a, mantenimiento_mock]):
            handle = await env.client.start_workflow(
                MiWorkflow.run, id="wf-test", task_queue="t")
            await env.sleep(60)   # el tiempo avanza "saltando" las esperas
            assert llamadas["psutil"] >= 3
            assert (await handle.describe()).status == WorkflowExecutionStatus.RUNNING
            await handle.terminate()
