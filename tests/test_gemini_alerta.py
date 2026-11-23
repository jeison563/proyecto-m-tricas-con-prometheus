# tests/test_gemini_alerta.py
"""
Prueba el flujo  alerta -> Gemini -> guardar análisis.

  A) Unitarias de analisis_gemini()  (Gemini simulado, sin red)         -> siempre se ejecutan
  B) Del workflow completo           (activities simuladas)              -> siempre se ejecutan
  C) Gemini REAL (usa tu API key y el modelo del .env)                   -> solo con:  pytest -m gemini -s
"""
import os
import pathlib
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values
from temporalio import activity
from temporalio.client import WorkflowExecutionStatus
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from activitys import activity_gemini
from activitys.activity_gemini import analisis_gemini
from temporal.workflows import MiWorkflow

RAIZ = pathlib.Path(__file__).resolve().parent.parent

METRICAS_ALTAS = {"cpu_percent": 97, "memory_percent": 40, "memory_available": 4_000_000_000,
                  "disk_percent": 55, "disk_used": 10_000_000_000}

ANALISIS_OK = {
    "estado_general": "critico", "recurso_mas_utilizado": "cpu",
    "metricas": {
        "cpu": {"porcentaje": 97, "estado": "critico", "analisis": "x"},
        "ram": {"porcentaje": 40, "estado": "normal", "analisis": "x"},
        "disco": {"porcentaje": 55, "estado": "normal", "analisis": "x"},
    },
    "recomendacion": "x", "datos_insuficientes": False,
}


# ============================================================================
# A) analisis_gemini() con un cliente de Gemini simulado
# ============================================================================
def _cliente_falso(texto=None, error=None):
    async def generate_content(**kwargs):
        if error:
            raise error
        return SimpleNamespace(text=texto)
    return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))


async def test_devuelve_el_json_de_gemini(monkeypatch):
    import json
    monkeypatch.setattr(activity_gemini, "client", _cliente_falso(json.dumps(ANALISIS_OK)))
    assert await analisis_gemini({"metrics": METRICAS_ALTAS}) == ANALISIS_OK


async def test_metricas_vacias_es_valueerror():
    with pytest.raises(ValueError):          # ValueError = no reintentar
        await analisis_gemini({"metrics": {}})


@pytest.mark.parametrize("texto", ["", None, "esto no es json", "[1, 2, 3]"])
async def test_respuesta_invalida_es_runtimeerror(monkeypatch, texto):
    monkeypatch.setattr(activity_gemini, "client", _cliente_falso(texto))
    with pytest.raises(RuntimeError):        # RuntimeError = reintentable
        await analisis_gemini({"metrics": METRICAS_ALTAS})


async def test_error_de_la_api_es_runtimeerror(monkeypatch):
    from google.genai import errors
    err = errors.APIError(404, {"error": {"message": "modelo no existe"}})
    monkeypatch.setattr(activity_gemini, "client", _cliente_falso(error=err))
    with pytest.raises(RuntimeError, match="Error de Gemini"):
        await analisis_gemini({"metrics": METRICAS_ALTAS})


# ============================================================================
# B) Workflow: ¿cuándo se llama a Gemini y cuándo se guarda el análisis?
# ============================================================================
@pytest.fixture
async def entorno():
    """Con internet usa time-skipping (rápido). Sin internet, define TEMPORAL_DEV_SERVER=/ruta/al/cli temporal."""
    ruta = os.environ.get("TEMPORAL_DEV_SERVER")
    if ruta:
        env, saltando = await WorkflowEnvironment.start_local(dev_server_existing_path=ruta), False
    else:
        env, saltando = await WorkflowEnvironment.start_time_skipping(), True
    yield env, saltando
    await env.shutdown()


def _actividades(alerta, llamadas_gemini, guardados, gemini_falla=False):
    @activity.defn(name="mantenimiento_db")
    async def mantenimiento() -> dict:
        return {}

    @activity.defn(name="_psutil")
    async def psutil_mock() -> dict:
        return METRICAS_ALTAS

    @activity.defn(name="comparation")
    async def comparation_mock(d: dict) -> dict:
        return {"alerta": alerta, "alertas": ["cpu_percent=97%"] if alerta else []}

    @activity.defn(name="upsert_metrics_data")
    async def upsert_m(d: dict): ...

    @activity.defn(name="analisis_gemini")
    async def gemini_mock(d: dict):
        llamadas_gemini.append(d)
        if gemini_falla:
            raise RuntimeError("Gemini caído")
        return ANALISIS_OK

    @activity.defn(name="upsert_analisis")
    async def upsert_a(d: dict):
        guardados.append(d)

    return [mantenimiento, psutil_mock, comparation_mock, upsert_m, gemini_mock, upsert_a]


async def _ejecutar(env, nombre, actividades, segundos):
    async with Worker(env.client, task_queue=nombre, workflows=[MiWorkflow], activities=actividades):
        handle = await env.client.start_workflow(MiWorkflow.run, id=nombre, task_queue=nombre)
        await env.sleep(segundos)
        estado = (await handle.describe()).status
        await handle.terminate()
        return estado


async def test_con_alerta_se_llama_a_gemini_y_se_guarda(entorno):
    env, _ = entorno
    gemini, guardados = [], []
    estado = await _ejecutar(env, "t-alerta", _actividades(True, gemini, guardados), 12)
    assert len(gemini) == 1
    assert gemini[0]["metrics"] == METRICAS_ALTAS and gemini[0]["alertas"] == ["cpu_percent=97%"]
    assert len(guardados) == 1
    assert guardados[0]["metrics"] == METRICAS_ALTAS and guardados[0]["analisis_alerta"] == ANALISIS_OK
    assert estado == WorkflowExecutionStatus.RUNNING


async def test_sin_alerta_no_se_llama_a_gemini_ni_se_guarda(entorno):
    env, _ = entorno
    gemini, guardados = [], []
    await _ejecutar(env, "t-sin-alerta", _actividades(False, gemini, guardados), 12)
    assert gemini == [] and guardados == []


async def test_si_gemini_falla_no_se_guarda_y_el_workflow_sigue(entorno):
    env, _ = entorno
    gemini, guardados = [], []
    estado = await _ejecutar(env, "t-falla", _actividades(True, gemini, guardados, gemini_falla=True), 15)
    assert len(gemini) >= 1                  # lo intentó (con reintentos)
    assert guardados == []                   # y no guardó nada
    assert estado == WorkflowExecutionStatus.RUNNING


async def test_enfriamiento_de_5_minutos(entorno):
    env, saltando = entorno
    if not saltando:
        pytest.skip("necesita time-skipping (5 minutos reales no son prácticos)")
    gemini, guardados = [], []
    async with Worker(env.client, task_queue="t-cd", workflows=[MiWorkflow],
                      activities=_actividades(True, gemini, guardados)):
        handle = await env.client.start_workflow(MiWorkflow.run, id="t-cd", task_queue="t-cd")
        await env.sleep(120)
        assert len(gemini) == 1              # alerta sostenida 2 min: solo un análisis
        await env.sleep(300)
        assert len(gemini) == 2              # pasados 5 min, uno nuevo
        await handle.terminate()


# ============================================================================
# C) Gemini REAL  ->  pytest -m gemini -s
# ============================================================================
def _credenciales():
    clave = os.environ.get("GEMINI_API_KEY")
    if clave in (None, "", "x") or clave.startswith("CAMBIAR"):     # "x" la pone conftest
        clave = dotenv_values(RAIZ / ".env").get("GEMINI_API_KEY", "")
    return clave


@pytest.mark.gemini
async def test_gemini_real_responde_con_el_formato_esperado(monkeypatch):
    from google import genai
    clave = _credenciales()
    if not clave or clave.startswith("CAMBIAR"):
        pytest.skip("Pon tu GEMINI_API_KEY real en el .env (o expórtala) para esta prueba")

    monkeypatch.setattr(activity_gemini, "client", genai.Client(api_key=clave))
    print(f"\nModelo: {activity_gemini.GEMINI_MODEL}")

    resultado = await analisis_gemini({"metrics": METRICAS_ALTAS})   # si el modelo no existe, falla aquí con el motivo
    print(resultado)

    assert resultado["estado_general"] in {"normal", "advertencia", "critico"}
    assert resultado["recurso_mas_utilizado"] in {"cpu", "ram", "disco", "desconocido"}
    assert set(resultado["metricas"]) == {"cpu", "ram", "disco"}
    assert isinstance(resultado["recomendacion"], str) and isinstance(resultado["datos_insuficientes"], bool)
    assert resultado["estado_general"] == "critico"      # cpu=97 >= 90
    assert resultado["recurso_mas_utilizado"] == "cpu"
