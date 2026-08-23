"""
Servicio de Google Jobs (vía SerpApi) para vacantes en Colombia.

A diferencia de Adzuna, Google Jobs tiene su PROPIA tabla en Supabase
(`vacantes_google`, ver src/backend/migrations/001_vacantes_google.sql) para
poder guardar TODOS los campos que la API entrega, sin forzar columnas en NULL.

Este módulo hace dos cosas:
  1. Recolección: _buscar_pagina_google() (1 página = 1 búsqueda SerpApi) +
     guardar_vacante_google() + procesar_vacantes_google(), que reparte el
     presupuesto de búsquedas entre todas las keywords (en español, ver
     PROGRAMAS_KEYWORDS_CO) con estrategia round-robin para maximizar vacantes.
  2. Analíticas propias de Google Jobs: get_analytics_google(), con la forma de
     datos adecuada a los campos que SÍ trae esta fuente (ciudades, plataforma de
     origen, modalidad, etc.). NO incluye salario/categoría porque Google Jobs no
     los entrega de forma estructurada.

Reutiliza de adzuna_service el cliente de Supabase y la normalización de títulos.
"""

import re
import requests
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any
from collections import Counter

from config import SERPAPI_KEY, PROGRAMAS_KEYWORDS_CO, SERPAPI_MAX_BUSQUEDAS, es_pertinente
# Reutilizamos el cliente de Supabase, el normalizador de títulos y los helpers
# de filtrado/seniority ya existentes (viven en adzuna_service por historia).
from Adzuna.adzuna_service import (
    supabase,
    normalize_title,
    clasificar_seniority,
    _distinct_labels,
    _seniorities_presentes,
)

SERPAPI_URL = "https://serpapi.com/search.json"
TABLA = "vacantes_google"

# Mapeo de los tipos de jornada que entrega Google Jobs a etiquetas legibles y
# consistentes. Google los entrega en inglés aunque pidamos hl=es.
_SCHEDULE_MAP = {
    "full-time": "Tiempo completo",
    "full time": "Tiempo completo",
    "part-time": "Medio tiempo",
    "part time": "Medio tiempo",
    "contractor": "Contratista",
    "contract": "Contratista",
    "internship": "Pasantía",
    "temporary": "Temporal",
}


# ---------------------------------------------------------------------------
# Helpers de parseo (extraen/normalizan campos del JSON crudo de SerpApi)
# ---------------------------------------------------------------------------

def _map_schedule_type(detected_extensions: Dict[str, Any]) -> str:
    schedule = (detected_extensions or {}).get("schedule_type")
    if not schedule:
        return None
    # Si no está en el mapa, devolvemos el texto original tal cual.
    return _SCHEDULE_MAP.get(schedule.strip().lower(), schedule.strip())


def _extract_city(location: str) -> str:
    """De 'Bogotá, Colombia' devuelve 'Bogotá'. Si no hay coma, devuelve el texto."""
    if not location:
        return None
    return location.split(",")[0].strip()


def _clean_via(via: str) -> str:
    """De 'via LinkedIn' / 'a través de LinkedIn' devuelve solo 'LinkedIn'."""
    if not via:
        return None
    texto = via.strip()
    for prefijo in ("via ", "a través de ", "através de ", "vía "):
        if texto.lower().startswith(prefijo):
            return texto[len(prefijo):].strip()
    return texto


def _extract_highlights(job: Dict[str, Any]) -> Dict[str, str]:
    """Convierte job_highlights en tres bloques de texto: requisitos, funciones y beneficios.

    Google Jobs agrupa puntos clave bajo títulos como "Qualifications",
    "Responsibilities", "Benefits" (o sus equivalentes en español). Hacemos un
    match flexible por el título para tolerar ambos idiomas.
    """
    out = {"qualifications": None, "responsibilities": None, "benefits": None}
    for bloque in job.get("job_highlights", []) or []:
        titulo = (bloque.get("title") or "").strip().lower()
        items = bloque.get("items") or []
        if not items:
            continue
        texto = "\n".join(items)
        if "alific" in titulo or "requisit" in titulo:          # Qualifications / Cualificaciones / Requisitos
            out["qualifications"] = texto
        elif "esponsabil" in titulo or "function" in titulo or "funcion" in titulo:
            out["responsibilities"] = texto
        elif "enefi" in titulo:                                  # Benefits / Beneficios
            out["benefits"] = texto
    return out


# Unidades de tiempo que usa Google Jobs en `posted_at`, en días.
_UNIDADES_DIAS = {
    "minuto": 0, "minutos": 0, "minute": 0, "minutes": 0,
    "hora": 0, "horas": 0, "hour": 0, "hours": 0,
    "día": 1, "dia": 1, "días": 1, "dias": 1, "day": 1, "days": 1,
    "semana": 7, "semanas": 7, "week": 7, "weeks": 7,
    "mes": 30, "meses": 30, "month": 30, "months": 30,
    "año": 365, "años": 365, "ano": 365, "anos": 365, "year": 365, "years": 365,
}

_RE_POSTED = re.compile(r"(\d+)\s*\+?\s*([a-zA-Zñáéíóú]+)")


def fecha_de_posted_at(posted_at: str, referencia: date | None = None) -> str | None:
    """Convierte el `posted_at` RELATIVO de Google Jobs en una fecha absoluta ISO.

    Google Jobs no entrega fecha de publicación: da textos como "hace 3 días",
    "hace 2 semanas" o "30+ days ago" (en el idioma de la consulta, aquí español).
    Las tendencias necesitan una fecha real, así que se resta el intervalo a la
    fecha de recolección.

        "hace 3 días"  + referencia 2026-07-22  ->  "2026-07-19"

    Precisión: es aproximada por diseño (un "hace 1 mes" se toma como 30 días) y
    las horas/minutos se redondean al mismo día. Suficiente para agrupar por MES,
    que es el grano de las tendencias. Devuelve None si no se puede interpretar,
    y en ese caso quien llama decide (normalmente usar la fecha de recolección).
    """
    if not posted_at or not isinstance(posted_at, str):
        return None

    m = _RE_POSTED.search(posted_at.lower())
    if not m:
        return None

    cantidad = int(m.group(1))
    unidad = m.group(2)
    if unidad not in _UNIDADES_DIAS:
        return None

    ref = referencia or datetime.now(timezone.utc).date()
    return (ref - timedelta(days=cantidad * _UNIDADES_DIAS[unidad])).isoformat()


def _extract_apply_link(job: Dict[str, Any]) -> str:
    apply_options = job.get("apply_options") or []
    if apply_options and apply_options[0].get("link"):
        return apply_options[0]["link"]
    related_links = job.get("related_links") or []
    if related_links and related_links[0].get("link"):
        return related_links[0]["link"]
    return job.get("share_link")


# ---------------------------------------------------------------------------
# Recolección
# ---------------------------------------------------------------------------

def borrar_vacantes_google():
    """Borra todas las vacantes de la tabla de Google Jobs (recolección limpia)."""
    try:
        response = supabase.table(TABLA).delete().neq("job_id", "").execute()
        count = len(response.data) if response.data else 0
        print(f"🗑️ Se eliminaron {count} registros anteriores de Google Jobs.")
        return True
    except Exception as e:
        print(f"❌ Error al borrar vacantes de Google Jobs: {str(e)}")
        return False


def _buscar_pagina_google(keyword: str, next_page_token: str = None, location: str = "Colombia"):
    """Hace UNA sola petición a Google Jobs (= 1 búsqueda de SerpApi).

    Devuelve (results, next_token, agotado):
      - results/next_token: la página de resultados y el token de la siguiente
        (None si ya no hay más).
      - agotado=True SOLO cuando SerpApi responde 429. Verificado contra
        `GET https://serpapi.com/account.json`: el 429 de este plan es CUPO
        MENSUAL agotado (renueva en una fecha fija), no un límite por segundo —
        así que no tiene sentido pausar y reintentar la MISMA keyword: TODA
        petición volverá a fallar hasta la renovación. Antes esto se trataba
        igual que "esta keyword no tiene más resultados" y la desactivaba una
        por una, agotando el presupuesto restante en peticiones que no podían
        funcionar. Ahora se distingue para que la orquestación aborte la
        corrida entera de inmediato, igual que ya hace LinkedIn con su 429.
    """
    params = {
        "engine": "google_jobs",
        "q": keyword,
        "location": location,
        "gl": "co",
        "hl": "es",
        "api_key": SERPAPI_KEY,
    }
    if next_page_token:
        params["next_page_token"] = next_page_token

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=30)
        if response.status_code == 429:
            print(f"   ⛔ SerpApi 429 en '{keyword}': cupo agotado. Se aborta la corrida.")
            return [], None, True
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            print(f"   ❌ SerpApi error para '{keyword}': {data['error']}")
            return [], None, False
        results = data.get("jobs_results", [])
        token = (
            data.get("serpapi_pagination", {}).get("next_page_token")
            or data.get("next_page_token")
        )
        return results, token, False
    except Exception as e:
        print(f"   ❌ Error buscando '{keyword}' en Google Jobs: {str(e)}")
        return [], None, False


def guardar_vacante_google(job: Dict[str, Any], programa: str, keyword: str) -> bool:
    """Transforma una vacante cruda de Google Jobs y la guarda en `vacantes_google`."""
    try:
        job_id = job.get("job_id")
        if not job_id:
            return False

        # Google resuelve la búsqueda por full-text match y el programa se estampa
        # con la keyword pedida, sin mirar el título: descarta lo que no puede
        # pertenecer a ese programa (ver EXCLUSIONES_PROGRAMA en config.py).
        if not es_pertinente(programa, job.get("title")):
            return False

        detected = job.get("detected_extensions", {}) or {}
        location = job.get("location")
        highlights = _extract_highlights(job)

        row = {
            "job_id": job_id,
            "title": job.get("title"),
            "company": job.get("company_name"),
            "location": location,
            "city": _extract_city(location),
            "via": _clean_via(job.get("via")),
            "schedule_type": _map_schedule_type(detected),
            "work_from_home": bool(detected.get("work_from_home", False)),
            "posted_at": detected.get("posted_at"),
            "salary_raw": detected.get("salary"),
            "description": job.get("description"),
            "qualifications": highlights["qualifications"],
            "responsibilities": highlights["responsibilities"],
            "benefits": highlights["benefits"],
            "apply_link": _extract_apply_link(job),
            "thumbnail": job.get("thumbnail"),
            "extensions": job.get("extensions"),
            "keyword": keyword,
            "programa_relacionado": programa,
        }

        # upsert por job_id: si la vacante ya existe, la actualiza en vez de duplicar.
        supabase.table(TABLA).upsert(row, on_conflict="job_id").execute()
        return True

    except Exception as e:
        print(f"   ❌ Error guardando vacante '{job.get('title', 'Sin título')}': {str(e)}")
        return False


def procesar_vacantes_google(borrar: bool = False):
    """Recolecta vacantes de Google Jobs (Colombia) MAXIMIZANDO dentro del presupuesto.

    Estrategia round-robin (amplitud primero): se reparte el presupuesto de
    búsquedas (SERPAPI_MAX_BUSQUEDAS) entre TODAS las keywords. Primero se pide la
    página 1 de cada keyword, luego la página 2 de las que aún tengan resultados,
    y así sucesivamente hasta agotar el presupuesto. Así:
      - todos los programas quedan cubiertos antes de profundizar en cualquiera,
      - se maximiza la diversidad (cada keyword aporta vacantes distintas),
      - nunca se exceden las búsquedas disponibles de SerpApi.
    """
    print("🚀 Iniciando recolección de vacantes desde Google Jobs (Colombia)...\n")

    if not SERPAPI_KEY:
        return {
            "status": "error",
            "message": "SERPAPI_KEY no configurada o inválida. Revisa la variable de entorno.",
        }

    if borrar:
        borrar_vacantes_google()

    # Una "unidad" = un (programa, keyword) con su propio estado de paginación.
    unidades = [
        {"programa": programa, "keyword": kw, "token": None, "activa": True}
        for programa, keywords in PROGRAMAS_KEYWORDS_CO.items()
        for kw in keywords
    ]

    presupuesto = SERPAPI_MAX_BUSQUEDAS
    busquedas = 0
    total_vacantes = 0
    total_guardadas = 0
    ronda = 0

    print(f"📋 {len(unidades)} keywords | presupuesto: {presupuesto} búsquedas SerpApi\n")

    agotado = False

    # Cada ronda pide UNA página a cada keyword que siga activa (round-robin).
    while busquedas < presupuesto and any(u["activa"] for u in unidades) and not agotado:
        ronda += 1
        for u in unidades:
            if busquedas >= presupuesto:
                break
            if not u["activa"]:
                continue

            print(f"   🔍 [R{ronda}] '{u['keyword']}'  ({busquedas + 1}/{presupuesto})")
            results, token, sin_cupo = _buscar_pagina_google(u["keyword"], u["token"])
            busquedas += 1

            # Cupo agotado: NO es que esta keyword se haya quedado sin resultados
            # (todas fallarían igual). Se aborta la corrida entera de inmediato en
            # vez de recorrer el resto de unidades reintentando algo que no puede
            # funcionar hasta la renovación mensual.
            if sin_cupo:
                agotado = True
                break

            total_vacantes += len(results)
            for vacante in results:
                if guardar_vacante_google(vacante, u["programa"], u["keyword"]):
                    total_guardadas += 1

            # La keyword se "agota" si no hubo resultados o no hay más páginas.
            u["token"] = token
            if not results or not token:
                u["activa"] = False

    print(f"\n🎉 === RESUMEN FINAL (Google Jobs) ===")
    print(f"   Búsquedas SerpApi usadas: {busquedas} / {presupuesto}")
    print(f"   Total vacantes encontradas: {total_vacantes}")
    print(f"   Total vacantes guardadas (nuevas/actualizadas): {total_guardadas}")
    print(f"   Programas procesados: {len(PROGRAMAS_KEYWORDS_CO)}")
    if agotado:
        print("   ⛔ Corrida abortada: cupo mensual de SerpApi agotado.")

    return {
        "status": "completed",
        "busquedas_usadas": busquedas,
        "total_vacantes": total_vacantes,
        "total_guardadas": total_guardadas,
        "programas_procesados": len(PROGRAMAS_KEYWORDS_CO),
        "abortado_por_cupo_serpapi": agotado,
    }


# ---------------------------------------------------------------------------
# Lectura y analíticas
# ---------------------------------------------------------------------------

def fetch_google_jobs_from_db() -> List[Dict[str, Any]]:
    """Trae todas las vacantes de Google Jobs desde Supabase (con paginación)."""
    all_jobs = []
    page_size = 1000
    start = 0

    try:
        while True:
            response = supabase.table(TABLA)\
                .select("*")\
                .order("job_id")\
                .range(start, start + page_size - 1)\
                .execute()

            if not response.data:
                break

            all_jobs.extend(response.data)
            if len(response.data) < page_size:
                break
            start += page_size

        print(f"✅ Total de vacantes Google Jobs obtenidas: {len(all_jobs)}")
        return all_jobs
    except Exception as e:
        print(f"Error leyendo vacantes_google: {str(e)}")
        return []


def _top_counts(jobs, campo, top_n=15, etiqueta_vacia="No especificado"):
    """Cuenta valores de un campo y devuelve los más frecuentes como lista de dicts."""
    counter = Counter()
    for job in jobs:
        valor = job.get(campo) or etiqueta_vacia
        counter[valor] += 1
    return counter.most_common(top_n)


def _pasa_filtros_google(job: Dict[str, Any], f: Dict[str, Any]) -> bool:
    """True si la vacante de Google Jobs cumple TODOS los filtros activos."""
    if f.get("seniority") and clasificar_seniority(job.get("title")) != f["seniority"]:
        return False
    if f.get("programa") and (job.get("programa_relacionado") or "No especificado") != f["programa"]:
        return False
    if f.get("city") and (job.get("city") or "No especificado") != f["city"]:
        return False
    if f.get("schedule_type") and (job.get("schedule_type") or "No especificado") != f["schedule_type"]:
        return False
    if f.get("remote") is not None and bool(job.get("work_from_home")) != f["remote"]:
        return False
    return True


def get_vacantes_por_cargo_google(cargo: str, filtros: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Vacantes de Google Jobs cuyo título NORMALIZADO coincide con `cargo`.

    Equivalente a get_vacantes_por_cargo pero sobre `vacantes_google`. Devuelve
    título real, empresa y enlace de postulación (`apply_link`).
    """
    jobs = fetch_google_jobs_from_db()
    resultado = []
    for job in jobs:
        if not _pasa_filtros_google(job, filtros or {}):
            continue
        if normalize_title(job.get("title")) != cargo:
            continue
        resultado.append({
            "title": job.get("title") or "Sin título",
            "company": job.get("company") or "Sin empresa",
            "link": job.get("apply_link"),
        })
    resultado.sort(key=lambda v: v["company"].lower())
    return resultado


def get_analytics_google(filtros: Dict[str, Any] = None) -> Dict[str, Any]:
    """Genera las analíticas específicas de Google Jobs (Colombia).

    Solo incluye dimensiones que esta fuente sí provee: cargos, empresas,
    ciudades, plataforma de origen, modalidad y programa. (Sin salario ni
    categoría/sector, que Google Jobs no entrega estructurados.)

    `filtros` (opcional) filtra las vacantes antes de agregar. Claves admitidas:
    seniority, programa, city, schedule_type, remote (bool). Las opciones de cada
    filtro se devuelven en `filter_options` (calculadas sobre el total sin filtrar).
    """
    jobs = fetch_google_jobs_from_db()

    _empty_options = {"seniorities": [], "programas": [], "cities": [], "schedule_types": []}
    if not jobs:
        return {
            "total_jobs": 0,
            "remote_count": 0,
            "job_titles": [],
            "companies": [],
            "contract_types": [],
            "cities": [],
            "sources": [],
            "programas": [],
            "filter_options": _empty_options,
        }

    # Opciones de filtro sobre TODAS las vacantes (antes de filtrar).
    filter_options = {
        "seniorities": _seniorities_presentes(jobs),
        "programas": _distinct_labels(jobs, "programa_relacionado", "No especificado"),
        "cities": _distinct_labels(jobs, "city", "No especificado"),
        "schedule_types": _distinct_labels(jobs, "schedule_type", "No especificado"),
    }

    jobs = [job for job in jobs if _pasa_filtros_google(job, filtros or {})]

    # Cargos más demandados (usando la misma normalización que Adzuna para agrupar)
    title_counter = Counter()
    for job in jobs:
        title_counter[normalize_title(job.get("title", "Sin título"))] += 1
    top_titles = title_counter.most_common(20)

    remote_count = sum(1 for job in jobs if job.get("work_from_home"))

    return {
        "total_jobs": len(jobs),
        "remote_count": remote_count,
        "job_titles": [{"title": t, "count": c} for t, c in top_titles],
        "companies": [{"company": v, "count": c} for v, c in _top_counts(jobs, "company")],
        "contract_types": [{"type": v, "count": c} for v, c in _top_counts(jobs, "schedule_type")],
        "cities": [{"city": v, "count": c} for v, c in _top_counts(jobs, "city")],
        "sources": [{"source": v, "count": c} for v, c in _top_counts(jobs, "via")],
        "programas": [{"programa": v, "count": c} for v, c in _top_counts(jobs, "programa_relacionado")],
        "filter_options": filter_options,
    }


if __name__ == "__main__":
    procesar_vacantes_google()
