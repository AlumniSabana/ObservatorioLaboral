"""
Recolección de datos desde la consola local (sin el botón "Actualizar histórico").

Ejecuta el mismo orquestador que `POST /tendencias/recolectar`
(Tendencias/actualizacion.py: Adzuna, Google Jobs, LinkedIn y recálculo), pero
sin pasar por el navegador: una corrida de 20+ minutos no depende de que la
pestaña siga abierta ni del timeout de una petición HTTP.

    python actualizar_local.py                       # todas las fuentes
    python actualizar_local.py --fuentes linkedin    # solo algunas
    python actualizar_local.py --meses 24 --presupuesto 250
    # LinkedIn con huella mínima, solo algunos países:
    python actualizar_local.py --fuentes linkedin --paises mx ar --keywords 1 --paginas 2 --pausa 5

Respeta las mismas reglas de seguridad del orquestador (cupo SerpApi, 429 de
LinkedIn, LINKEDIN_HABILITADO). Escribe en la base real de Supabase.
"""

import argparse
import functools
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--fuentes", nargs="+", choices=("adzuna", "google_jobs", "linkedin"), help="limita la corrida (por defecto, todas)")
p.add_argument("--meses", type=int, default=24)
p.add_argument("--presupuesto", type=int, default=250, help="llamadas de Adzuna POR mercado")
p.add_argument("--keywords", type=int, default=1, help="keywords por programa (LinkedIn y Adzuna)")
p.add_argument("--paises", nargs="+", help="solo LinkedIn: códigos de PAISES_LATAM (co mx ar cl pe)")
p.add_argument("--paginas", type=int, help="solo LinkedIn: páginas por keyword (por defecto LINKEDIN_MAX_PAGINAS)")
p.add_argument("--pausa", type=float, help="solo LinkedIn: segundos entre peticiones")
a = p.parse_args()

# config lee la pausa al importarse: hay que fijarla antes del import.
if a.pausa:
    os.environ["LINKEDIN_PAUSA_SEG"] = str(a.pausa)

from Tendencias import actualizacion  # noqa: E402
from Tendencias.actualizacion import FUENTES_VALIDAS, actualizar_todo  # noqa: E402

if a.paises or a.paginas:
    # Restringe la corrida de LinkedIn sin tocar el orquestador (los países no
    # incluidos salen como "omitida" en el resumen).
    actualizacion.DEPENDENCIAS["linkedin_recolectar"] = functools.partial(
        actualizacion.DEPENDENCIAS["linkedin_recolectar"], paises=a.paises, max_paginas=a.paginas)

resumen = actualizar_todo(meses=a.meses, presupuesto=a.presupuesto, keywords_por_programa=a.keywords, fuentes=a.fuentes)

print("\n=== RESUMEN ===")
print(f"status: {resumen['status']} · duración: {resumen.get('duracion_seg')} s")
for f in resumen["fuentes"]:
    print(f"  {f['label']:<28} {f['estado']:<12} filas={f['filas']} llamadas={f['llamadas']} "
          f"{f['duracion_seg']}s {f['error'] or ''}")
print("recálculo:", json.dumps(resumen.get("recalculo"), ensure_ascii=False)[:300])
sys.exit(0 if resumen["status"] != "error" else 1)
