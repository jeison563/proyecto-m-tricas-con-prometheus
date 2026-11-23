#core/config.py
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parent.parent / ".env")   # raíz del repo, no core/


def get_env(name: str, default: str | None = None) -> str:

    value = os.getenv(name, default)

    if value is None or value == "":
        raise RuntimeError(f"Falta la variable de entorno requerida: {name}")

    return value


SQL_ECHO = get_env("SQL_ECHO", "False").lower() == "true"

MAX_WORKERS = int(get_env("MAX_WORKERS"))

MAX_OVERFLOWS = int(get_env("MAX_OVERFLOWS"))

TASK_QUEUE = get_env("TASK_QUEUE")

WORKFLOW_CONCURRENCY = int(get_env("WORKFLOW_CONCURRENCY"))

TEMPORAL_HOST = get_env("TEMPORAL_HOST")

TEMPORAL_NAMESPACE = get_env("TEMPORAL_NAMESPACE")

MAX_PERCENT = int(get_env("MAX_PERCENT"))

GEMINI_API_KEY = get_env("GEMINI_API_KEY")

GEMINI_MODEL = get_env("GEMINI_MODEL", "gemini-2.5-flash")  # verifica que siga disponible

# --- Base de datos -------------------------------------------------------------
# POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB son las mismas que usa docker-compose.
POSTGRES_USER = get_env("POSTGRES_USER")

POSTGRES_PASSWORD = get_env("POSTGRES_PASSWORD")

POSTGRES_DB = get_env("POSTGRES_DB")

POSTGRES_HOST = get_env("POSTGRES_HOST", "db")

POSTGRES_PORT = int(get_env("POSTGRES_PORT", "5432"))

# URL.create codifica los caracteres especiales de la contraseña (@ : / # % ...);
# con un f-string una contraseña así rompería la URL de conexión.
DB_URL = URL.create(
    "postgresql+asyncpg",
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=POSTGRES_DB,
).render_as_string(hide_password=False)

PROMETHEUS_URL = get_env("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")

# añade al final de core/config.py
JWT_SECRET = get_env("JWT_SECRET")

JWT_ALGORITHM = "HS256"

JWT_EXPIRE_MINUTES = int(get_env("JWT_EXPIRE_MINUTES", "60"))

HOST_ID = int(get_env("HOST_ID"))   # id del host (tabla hosts) que mide este worker

RAW_RETENTION_DAYS = int(get_env("RAW_RETENTION_DAYS", "7"))

AVG_RETENTION_DAYS = int(get_env("AVG_RETENTION_DAYS", "365"))

PARTITIONS_AHEAD_DAYS = int(get_env("PARTITIONS_AHEAD_DAYS", "7"))

ROLLUP_LOOKBACK_HOURS = int(get_env("ROLLUP_LOOKBACK_HOURS", "24"))
