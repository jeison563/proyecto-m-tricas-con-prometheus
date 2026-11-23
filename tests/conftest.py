# tests/conftest.py  (config.py exige estas variables al importar)
import os

for k, v in {
    "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p", "POSTGRES_DB": "test",
    "POSTGRES_HOST": "localhost",
    "JWT_SECRET": "x" * 48, "HOST_ID": "1",
    "MAX_WORKERS": "5", "MAX_OVERFLOWS": "5", "TASK_QUEUE": "test",
    "WORKFLOW_CONCURRENCY": "2", "TEMPORAL_HOST": "localhost:7233",
    "TEMPORAL_NAMESPACE": "default", "MAX_PERCENT": "90",
    "GEMINI_API_KEY": "x", "API_KEY": "x",
}.items():
    os.environ.setdefault(k, v)
