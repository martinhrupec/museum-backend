"""Gunicorn konfiguracija — Prometheus multiprocess mode.

Gunicorn ima vise workera (svaki je poseban Python proces). prometheus_client
drzi brojace u memoriji procesa, pa bi Prometheus scrape hvatao samo jednog
worker-a. Multiprocess mode rjesava to tako da workeri pisu metrike u shared
file-based direktorij, a kod scrapea se agregiraju iz svih procesa.
"""

import os
import shutil


def on_starting(server):
    mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not mp_dir:
        return
    if os.path.isdir(mp_dir):
        shutil.rmtree(mp_dir)
    os.makedirs(mp_dir, exist_ok=True)


def child_exit(server, worker):
    # Bez ovoga metric fileovi umrlih worker-a ostaju na disku i duplaju
    # counter-e nakon restarta workera (npr. zbog --max-requests).
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)
