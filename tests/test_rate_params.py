# tests/test_rate_params.py
import pytest
from pydantic import ValidationError
from metricas.metrica_entrada import RateParams

def test_valido():
    RateParams(cpu_percent=10, memory_percent=20, memory_available=1,
               disk_percent=30, disk_used=1)

def test_fuera_de_rango():
    with pytest.raises(ValidationError):
        RateParams(cpu_percent=150, memory_percent=20, memory_available=1,
                   disk_percent=30, disk_used=1)
