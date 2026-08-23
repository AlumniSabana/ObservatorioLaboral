"""
Puente LinkedIn -> módulo de Tendencias.

Mismo patrón que `google_jobs_sync.py`: LinkedIn guarda en su propia tabla
(`vacantes_linkedin`) y Tendencias/Skills lee de `vacantes_historicas`. Este
módulo copia de una a otra.

LIMITACIÓN REAL (a diferencia de Google Jobs): el recolector de LinkedIn solo
lee las TARJETAS de resultado (título, empresa, ubicación, fecha) — nunca llama
al endpoint de detalle, así que `description`/`seniority` llegan vacíos en el
100% de las filas (verificado: 0 de 760). Sin texto no hay de dónde extraer
skills, así que esta fuente aporta la dimensión 'cargo' únicamente. No se
inventa una extracción sobre el título solo: sería en su mayoría ruido.

Tampoco hay SECTOR: LinkedIn no entrega una categoría estructurada en la
tarjeta (a diferencia de Adzuna). `category` queda None, igual que en Google
Jobs.

ID: `vacantes_historicas.id` es bigint; el `job_id` de LinkedIn es texto largo,
así que se aplica el mismo hash estable de 62 bits que usa Google Jobs (mismo
espacio de ids, sin colisión entre fuentes porque el hash incluye la fuente).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List

from Adzuna.adzuna_service import supabase
from Tendencias.google_jobs_sync import _id_estable  # reutiliza el mismo hash
from LinkedIn.linkedin_service import TABLA as TABLA_LINKEDIN
from Tendencias.historical_collector import TABLA_HIST

FUENTE = "linkedin"
# NO se reutiliza "co": `leer_observaciones()` combina países IGNORANDO fuente a
# propósito ("cada país lo cubre una sola fuente") y Colombia ya la cubre Google
# Jobs. Si LinkedIn escribiera también bajo pais='co', sus filas y las de Google
# Jobs compartirían el mismo balde en la lectura multi-país: la comparación
# "cada país pesa igual" contaría a Colombia dos veces (una por fuente) frente a
# una sola vez para el resto de mercados, sesgando cualquier combinación que
# incluya 'co'. Se usa un código de país propio: mismo patrón que ya existe
# (cada (fuente, país) es un mercado independiente), solo que este no coincide
# con ningún ISO real a propósito, para no fingir ser la MISMA Colombia que ya
# mide Google Jobs.
PAIS = "co_li"


def _leer_linkedin() -> List[Dict[str, Any]]:
    filas: List[Dict[str, Any]] = []
    start, page = 0, 1000
    while True:
        r = (
            supabase.table(TABLA_LINKEDIN)
            .select("job_id,title,company,fecha_publicacion,posted_at,"
                    "keyword,programa_relacionado,recolectado_en")
            .order("job_id")
            .range(start, start + page - 1)
            .execute()
        )
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < page:
            break
        start += page
    return filas


def sincronizar(referencia: date | None = None) -> Dict[str, Any]:
    """Copia `vacantes_linkedin` -> `vacantes_historicas`. Idempotente (upsert por id).

    A diferencia de Google Jobs, `fecha_publicacion` ya viene absoluta desde la
    recolección (LinkedIn expone `datetime` en la tarjeta, o se convierte ahí
    mismo desde el relativo) — no hay que reinterpretar nada aquí.
    """
    filas = _leer_linkedin()
    if not filas:
        return {"status": "sin_datos_linkedin", "sincronizadas": 0}

    hoy = referencia or datetime.now(timezone.utc).date()
    salida: List[Dict[str, Any]] = []
    sin_fecha = 0

    for f in filas:
        job_id = f.get("job_id")
        if not job_id:
            continue

        fecha = f.get("fecha_publicacion")
        if not fecha:
            # Sin fecha interpretable, se asume el día de recolección (cota
            # conservadora, igual criterio que Google Jobs).
            fecha = (f.get("recolectado_en") or hoy.isoformat())[:10]
            sin_fecha += 1

        salida.append({
            # Hash con prefijo de fuente: mismo job_id numérico no puede
            # colisionar entre LinkedIn y Google Jobs (ids de ambas son texto
            # largo pero de dominios distintos, por claridad igual se prefija).
            "id": _id_estable(f"linkedin:{job_id}"),
            "title": f.get("title"),
            "company": f.get("company"),
            # LinkedIn no entrega sector estructurado: dimensión 'sector' vacía.
            "category": None,
            "created_at": fecha,
            "fuente": FUENTE,
            "pais": PAIS,
            "keyword": f.get("keyword"),
            "programa_relacionado": f.get("programa_relacionado"),
            "ref_externa": job_id,
            # Sin description no hay texto del que extraer skills honestamente.
            "skills": None,
        })

    guardadas = 0
    for i in range(0, len(salida), 500):
        lote = salida[i:i + 500]
        try:
            supabase.table(TABLA_HIST).upsert(lote, on_conflict="id").execute()
            guardadas += len(lote)
        except Exception as e:
            print(f"   [!] Error guardando lote de LinkedIn: {e}")

    return {
        "status": "completed",
        "leidas_linkedin": len(filas),
        "sincronizadas": guardadas,
        "sin_fecha_interpretable": sin_fecha,
        "nota": "Solo dimensión 'cargo': LinkedIn no aporta sector ni skills (sin texto de descripción).",
    }
