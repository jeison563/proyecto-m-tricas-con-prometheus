# activitys/activity_gemini.py
import json
import logging

from google import genai
from google.genai import errors, types
from temporalio import activity

from core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)

PROMPT = """
Actúa como un ingeniero especializado en monitorización de sistemas, análisis de rendimiento y Python.
        Tu tarea es analizar las métricas de rendimiento de una máquina que recibirás mediante un diccionario de Python en formato JSON.

        Las métricas pueden incluir:

        * `cpu_percent`: porcentaje de utilización de CPU.
        * `memory_percent`: porcentaje de utilización de RAM.
        * `memory_available`: memoria RAM disponible en bytes.
        * `disk_percent`: porcentaje de espacio ocupado en disco.
        * `disk_used`: espacio utilizado en disco en bytes.
        
        **Reglas de análisis:**
        
        1. Evalúa individualmente CPU, RAM y disco.
        2. Considera que un recurso presenta un nivel de alerta cuando su porcentaje es igual o superior al 90 %.
        3. Clasifica cada recurso como:

        * `normal`: menos del 70 %.
        * `advertencia`: desde el 70 % hasta menos del 90 %.
        * `critico`: igual o superior al 90 %.
        4. Identifica qué recurso presenta mayor utilización.
        5. Explica brevemente los posibles efectos de los valores observados sobre el rendimiento del sistema.
        6. No declares que la máquina está saturada basándote únicamente en un promedio general. Analiza cada recurso por separado.
        7. Si faltan métricas, hay valores inválidos o los datos son insuficientes, indícalo sin inventar valores.
        8. No inventes información sobre procesos, temperatura, carga de CPU, swap o latencia de disco si no se proporcionan esos datos.
        9. Devuelve exclusivamente un objeto JSON válido, sin Markdown ni texto fuera del JSON.

        **Formato de respuesta obligatorio:**
        {
        "estado_general": "normal | advertencia | critico",
        "recurso_mas_utilizado": "cpu | ram | disco | desconocido",
        "metricas": {
        "cpu": {
        "porcentaje": 0,
        "estado": "normal | advertencia | critico",
        "analisis": ""
        },
        "ram": {
        "porcentaje": 0,
        "estado": "normal | advertencia | critico",
        "analisis": ""
        },
        "disco": {
        "porcentaje": 0,
        "estado": "normal | advertencia | critico",
        "analisis": ""
        }
        },
        "recomendacion": "",
        "datos_insuficientes": false
        }
        
        El campo `estado_general` debe reflejar el estado más grave entre los recursos evaluados. Si alguno está en estado crítico, el estado general será crítico. Si ninguno está crítico, pero alguno está en advertencia, será advertencia. De lo contrario, será normal.
        
        Analiza las siguientes métricas:
        """


@activity.defn
async def analisis_gemini(data: dict) -> dict:
    data_metric = data.get("metrics")
    if not data_metric:
        raise ValueError("datos de metricas vacios")

    contents = PROMPT + "\n" + json.dumps(data_metric, ensure_ascii=False)

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except errors.APIError as e:
        raise RuntimeError(f"Error de Gemini: {e}") from e

    if not response.text:
        raise RuntimeError("Gemini no devolvió texto")

    try:
        respuesta = json.loads(response.text)
    except json.JSONDecodeError as e:
        # RuntimeError (reintentable): un JSON malformado del modelo suele ser puntual
        raise RuntimeError("Gemini devolvió un JSON inválido") from e

    if not isinstance(respuesta, dict):
        raise RuntimeError("Gemini devolvió un formato inválido")

    return respuesta
