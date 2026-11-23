# app/life_span.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.shutdown_completo import shutdown
from routes import alertas, auth, historial, hosts, work
# PENDIENTE: routes/temporal_id.py NO fue incluido en el proyecto recibido, por eso su
# import estaba rompiendo el arranque de la API (ModuleNotFoundError). Cuando aportes
# ese archivo, descomenta esta línea y la de include_router de más abajo.
# from routes import temporal_id
from temporal.cliente_temporal_connet import TemporalClientFactory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        try:
            app.state.temporal = await TemporalClientFactory.client_conn()
        except Exception:
            logger.exception("error al conectar temporal")
            raise
        yield
    finally:
        await shutdown(getattr(app.state, "temporal", None))


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
Instrumentator().instrument(app).expose(app)

app.include_router(auth.router)
app.include_router(hosts.router)
app.include_router(historial.router)
app.include_router(work.router)
app.include_router(alertas.router)
# app.include_router(temporal_id.router)   # PENDIENTE: ver nota del import
