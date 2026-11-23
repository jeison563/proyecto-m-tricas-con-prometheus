# tests/estres_recursos.py
"""
Sube CPU, memoria y disco al porcentaje indicado (50 % por defecto) y lo mantiene estable.
NO es un test de pytest (no empieza por test_): es un script que se ejecuta a mano.

Debe correr DENTRO del contenedor del worker (el worker mide lo que ve su contenedor):

  docker compose cp tests/estres_recursos.py worker:/tmp/estres_recursos.py
  docker compose exec worker python /tmp/estres_recursos.py --segundos 120

Opciones:
  --cpu 50 --mem 50 --disco 50   porcentaje objetivo de cada recurso
  --segundos 120                 cuánto mantenerlos (se cuenta cuando ya están en su objetivo)
  --disco-max-gb 20              tope de escritura en disco, por seguridad

Si ya estás por encima del objetivo en algún recurso, ese recurso no se toca.
El archivo de disco se borra al terminar o con Ctrl+C (si matas el proceso a la fuerza, borra /tmp/estres_disco.bin).
"""
import argparse
import multiprocessing as mp
import os
import time

import psutil

ARCHIVO = "/tmp/estres_disco.bin"
MB = 1024 * 1024


def _quemar(intensidad, parar):
    try:
        os.nice(10)                       # prioridad baja: el consumo se ve, pero no ahoga al resto
    except (AttributeError, OSError):
        pass
    while not parar.is_set():
        carga = intensidad.value
        fin = time.perf_counter() + 0.1 * carga
        while time.perf_counter() < fin:
            pass
        time.sleep(0.1 * (1 - carga))


def _disco(objetivo, tope_gb):
    """Escribe en bloques de 256 MB hasta que el disco '/' llegue al objetivo (o al tope)."""
    uso = psutil.disk_usage("/")
    base = uso.used + uso.free                       # psutil calcula el % sobre usado + libre
    faltan = max(0, objetivo / 100 * base - uso.used)
    print(f"Disco: total {base / 2**30:.0f} GB, usado {uso.percent:.0f}% -> faltan {faltan / 2**30:.1f} GB para el {objetivo}%")
    if faltan > tope_gb * 2**30:
        print(f"  AVISO: supera el tope de seguridad ({tope_gb} GB): se escribirá solo hasta el tope. "
              f"Sube --disco-max-gb si de verdad quieres llegar al {objetivo}%.")
    escrito, bloque = 0, bytes(256 * MB)
    try:
        with open(ARCHIVO, "wb") as f:
            while psutil.disk_usage("/").percent < objetivo and escrito < tope_gb * 2**30:
                f.write(bloque)
                f.flush()
                os.fsync(f.fileno())
                escrito += len(bloque)
                if (escrito // len(bloque)) % 8 == 0:
                    print(f"  escritos {escrito / 2**30:.1f} GB | disco {psutil.disk_usage('/').percent:.1f}%")
    except OSError as e:
        print(f"  No se pudo seguir escribiendo en disco: {e}")
    print(f"Disco en {psutil.disk_usage('/').percent:.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, default=50)
    ap.add_argument("--mem", type=int, default=50)
    ap.add_argument("--disco", type=int, default=50)
    ap.add_argument("--segundos", type=int, default=120)
    ap.add_argument("--disco-max-gb", type=int, default=20)
    a = ap.parse_args()

    intensidad, parar = mp.Value("d", a.cpu / 100), mp.Event()
    procesos = [mp.Process(target=_quemar, args=(intensidad, parar), daemon=True)
                for _ in range(os.cpu_count() or 1)]
    bloques = []
    try:
        for p in procesos:
            p.start()
        print(f"Objetivo: CPU {a.cpu}% | RAM {a.mem}% | Disco {a.disco}%  ({len(procesos)} núcleos)")

        while psutil.virtual_memory().percent < a.mem:                      # memoria
            bloques.append(bytearray(b"\xaa") * (50 * MB))                  # se escribe: ocupa RAM real
        print(f"Memoria en {psutil.virtual_memory().percent:.1f}%")

        _disco(a.disco, a.disco_max_gb)                                     # disco

        print(f"Manteniendo durante {a.segundos}s (Ctrl+C para terminar)")
        fin = time.time() + a.segundos
        while time.time() < fin:
            cpu = psutil.cpu_percent(interval=1)
            intensidad.value = min(1.0, max(0.0, intensidad.value + (a.cpu - cpu) / 200))   # ajusta hacia el objetivo
            mem = psutil.virtual_memory().percent
            if mem < a.mem - 2:
                bloques.append(bytearray(b"\xaa") * (50 * MB))
            elif mem > a.mem + 2 and bloques:
                bloques.pop()
            print(f"  CPU {cpu:5.1f}% | RAM {mem:5.1f}% | Disco {psutil.disk_usage('/').percent:5.1f}%")
    except KeyboardInterrupt:
        print("Interrumpido")
    finally:
        parar.set()
        bloques.clear()
        if os.path.exists(ARCHIVO):
            os.remove(ARCHIVO)
        print("Listo: CPU, memoria y disco liberados")


if __name__ == "__main__":
    main()