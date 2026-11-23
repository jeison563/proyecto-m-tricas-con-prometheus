# metricas/gauges.py
from prometheus_client import Gauge

_L = ["host"]

cpu = Gauge("cpu_percent", "Uso de CPU (%)", _L)
memory = Gauge("memory_percent", "Uso de memoria (%)", _L)
memory_available = Gauge("memory_available", "Memoria disponible (bytes)", _L)
disco = Gauge("disk_percent", "Uso de disco (%)", _L)
disk_used = Gauge("disk_used", "Disco utilizado (bytes)", _L)
ultima_lectura = Gauge("ultima_lectura_unix", "Timestamp de la última lectura", _L)
