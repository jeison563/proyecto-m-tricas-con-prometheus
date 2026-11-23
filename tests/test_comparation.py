# tests/test_comparation.py
from activitys.activity_comparations import comparation

async def test_sin_alerta():
    r = await comparation({"cpu_percent": 10, "memory_percent": 20, "disk_percent": 30})
    assert r == {"alerta": False, "alertas": []}

async def test_con_alerta():
    r = await comparation({"cpu_percent": 95, "memory_percent": 20, "disk_percent": 30})
    assert r["alerta"] is True
    assert r["alertas"] == ["cpu_percent=95%"]
