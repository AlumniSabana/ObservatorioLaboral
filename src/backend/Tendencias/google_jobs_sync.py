"""
Puente Google Jobs -> módulo de Tendencias.

Google Jobs guarda sus vacantes en su propia tabla (`vacantes_google`, con los
campos que esa API entrega). El módulo de Tendencias/Skills, en cambio, lee de
`vacantes_historicas`. Este módulo copia de una a otra, adaptando lo que hace
falta:

  1. FECHA. Google Jobs no da fecha de publicación absoluta, sino un texto
     relativo ("hace 3 días"). Se convierte restando el intervalo a la fecha de
     recolección (ver GoogleJobs.google_jobs_service.fecha_de_posted_at).

  2. SKILLS OBSERVADAS. Es lo que Google Jobs aporta y Adzuna no puede: su
     `description` viene completa (~2.100 caracteres de media, frente a los 500
     truncados de Adzuna), así que las skills se extraen del texto REAL con el
     diccionario (ver Tendencias.skills_extractor). Medido sobre una muestra:
     9 de cada 10 vacantes producen skills, frente a ~1 de cada 7 en Adzuna.

  3. ID. `vacantes_historicas.id` es bigint (era el id numérico de Adzuna) y
     Google Jobs usa un `job_id` de texto largo, así que se guarda un hash
     estable de 62 bits y el job_id original queda en `ref_externa`.

LIMITACIONES (asumidas y visibles en la UI):
  - Sin SECTOR: Google Jobs no entrega categoría estructurada, así que la
    dimensión 'sector' queda vacía para esta fuente; funcionan 'cargo' y 'skill'.
  - Sin VOLUMEN real: no hay un `count` equivalente al de Adzuna, así que no se
    puede post-estratificar y cada vacante pesa 1.
  - Sin ARCHIVO histórico: Google Jobs solo indexa vacantes recientes (se midió:
    ninguna de más de ~7 días), así que un scrape aporta UN punto temporal. El
    histórico se acumula scrape a scrape, y las tendencias de esta fuente solo
    aparecerán cuando haya ≥3 meses distintos (MIN_PERIODOS).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any, Dict, List

from Adzuna.adzuna_service import supabase
from GoogleJobs.google_jobs_service import TABLA as TABLA_GOOGLE, fecha_de_posted_at
from Tendencias.historical_collector import TABLA_HIST
from Tendencias.skills_extractor import extraer_skills

FUENTE = "google_jobs"
PAIS = "co"


def columnas_extra_disponibles() -> Dict[str, bool]:
    """¿Están aplicadas las columnas de la migración 004?

    Permite funcionar en MODO REDUCIDO si la migración aún no se ha ejecutado:
    sin `skills` se pierde la dimensión 'skill' (skills observadas), pero el resto
    —Google Jobs como fuente, tendencias por cargo, histórico temporal— funciona
    igual con las columnas que ya existen. Al aplicar la migración basta volver a
    sincronizar para añadir las skills.
    """
    disponibles = {"skills": False, "ref_externa": False}
    for col in disponibles:
        try:
            supabase.table(TABLA_HIST).select(col).limit(1).execute()
            disponibles[col] = True
        except Exception:
            disponibles[col] = False
    return disponibles


def _id_estable(job_id: str) -> int:
    """Hash determinista de 62 bits para usar el job_id (texto) como PK bigint.

    Determinista para que reejecutar la sincronización actualice la misma fila en
    vez de duplicarla. 62 bits caben de sobra en un bigint y quedan muy por encima
    del rango de los ids reales de Adzuna (~10 dígitos), así que no colisionan.
    """
    h = hashlib.sha256(job_id.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") >> 2


def _leer_google() -> List[Dict[str, Any]]:
    filas: List[Dict[str, Any]] = []
    start, page = 0, 1000
    while True:
        r = (
            supabase.table(TABLA_GOOGLE)
            .select("job_id,title,company,description,qualifications,responsibilities,"
                    "posted_at,schedule_type,keyword,programa_relacionado,recolectado_en")
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


def _texto_para_skills(fila: Dict[str, Any]) -> str:
    """Junta los campos con contenido útil para extraer skills.

    `qualifications` (requisitos) es donde Google Jobs concentra las herramientas
    y competencias pedidas, así que aporta tanto como la descripción completa.
    """
    partes = [
        fila.get("description") or "",
        fila.get("qualifications") or "",
        fila.get("responsibilities") or "",
    ]
    return "\n".join(p for p in partes if p)


def sincronizar(referencia: date | None = None) -> Dict[str, Any]:
    """Copia `vacantes_google` -> `vacantes_historicas` con fecha y skills.

    `referencia` es la fecha desde la que se interpreta el "hace N días". Por
    defecto se usa `recolectado_en` de cada fila (cuándo se recolectó); si falta,
    hoy. Es idempotente: reejecutar actualiza las mismas filas (upsert por id).
    """
    filas = _leer_google()
    if not filas:
        return {"status": "sin_datos_google", "sincronizadas": 0}

    extra = columnas_extra_disponibles()
    hoy = referencia or datetime.now(timezone.utc).date()
    salida: List[Dict[str, Any]] = []
    sin_fecha = 0
    con_skills = 0

    for f in filas:
        job_id = f.get("job_id")
        if not job_id:
            continue

        # La fecha relativa se interpreta desde el día en que se recolectó.
        ref = hoy
        if f.get("recolectado_en"):
            try:
                ref = datetime.fromisoformat(
                    str(f["recolectado_en"]).replace("Z", "+00:00")
                ).date()
            except Exception:
                ref = hoy

        fecha = fecha_de_posted_at(f.get("posted_at"), ref)
        if not fecha:
            # Sin dato interpretable asumimos que se publicó el día del scrape:
            # es la cota más conservadora y evita perder la vacante.
            fecha = ref.isoformat()
            sin_fecha += 1

        skills = sorted(extraer_skills(_texto_para_skills(f), idioma="es"))
        if skills:
            con_skills += 1

        registro = {
            "id": _id_estable(job_id),
            "title": f.get("title"),
            "company": f.get("company"),
            # Google Jobs no entrega sector: la dimensión 'sector' queda vacía.
            "category": None,
            "contract_time": f.get("schedule_type"),
            "created_at": fecha,
            "fuente": FUENTE,
            "pais": PAIS,
            "keyword": f.get("keyword"),
            "programa_relacionado": f.get("programa_relacionado"),
        }
        # Solo si la migración 004 está aplicada (si no, modo reducido sin skills).
        if extra["skills"]:
            registro["skills"] = skills or None
        if extra["ref_externa"]:
            registro["ref_externa"] = job_id

        salida.append(registro)

    guardadas = 0
    for i in range(0, len(salida), 500):
        lote = salida[i : i + 500]
        try:
            supabase.table(TABLA_HIST).upsert(lote, on_conflict="id").execute()
            guardadas += len(lote)
        except Exception as e:
            print(f"   [!] Error guardando lote de Google Jobs: {e}")

    return {
        "status": "completed",
        "leidas_google": len(filas),
        "sincronizadas": guardadas,
        "sin_fecha_interpretable": sin_fecha,
        "con_skills": con_skills if extra["skills"] else 0,
        # Si falta la migración 004 se sincroniza igual, pero sin la dimensión
        # 'skill'. Volver a ejecutar tras aplicarla añade las skills.
        "modo": "completo" if extra["skills"] else "reducido_sin_skills",
        "migracion_004_aplicada": extra["skills"],
    }
