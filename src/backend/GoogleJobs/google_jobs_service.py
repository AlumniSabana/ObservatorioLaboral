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

import requests
from typing import List, Dict, Any
from collections import Counter

from config import SERPAPI_KEY, PROGRAMAS_KEYWORDS_CO, SERPAPI_MAX_BUSQUEDAS
# Reutilizamos el cliente de Supabase y el normalizador de títulos ya existentes
from Adzuna.adzuna_service import supabase, normalize_title

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

    Devuelve la tupla (results, next_token): la lista de vacantes de esa página y
    el token para la siguiente página (None si ya no hay más). La orquestación
    (procesar_vacantes_google) decide cuántas páginas pedir según el presupuesto.
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
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            print(f"   ❌ SerpApi error para '{keyword}': {data['error']}")
            return [], None
        results = data.get("jobs_results", [])
        token = (
            data.get("serpapi_pagination", {}).get("next_page_token")
            or data.get("next_page_token")
        )
        return results, token
    except Exception as e:
        print(f"   ❌ Error buscando '{keyword}' en Google Jobs: {str(e)}")
        return [], None


def guardar_vacante_google(job: Dict[str, Any], programa: str, keyword: str) -> bool:
    """Transforma una vacante cruda de Google Jobs y la guarda en `vacantes_google`."""
    try:
        job_id = job.get("job_id")
        if not job_id:
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

    # Cada ronda pide UNA página a cada keyword que siga activa (round-robin).
    while busquedas < presupuesto and any(u["activa"] for u in unidades):
        ronda += 1
        for u in unidades:
            if busquedas >= presupuesto:
                break
            if not u["activa"]:
                continue

            print(f"   🔍 [R{ronda}] '{u['keyword']}'  ({busquedas + 1}/{presupuesto})")
            results, token = _buscar_pagina_google(u["keyword"], u["token"])
            busquedas += 1

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

    return {
        "status": "completed",
        "busquedas_usadas": busquedas,
        "total_vacantes": total_vacantes,
        "total_guardadas": total_guardadas,
        "programas_procesados": len(PROGRAMAS_KEYWORDS_CO),
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


def get_analytics_google() -> Dict[str, Any]:
    """Genera las analíticas específicas de Google Jobs (Colombia).

    Solo incluye dimensiones que esta fuente sí provee: cargos, empresas,
    ciudades, plataforma de origen, modalidad y programa. (Sin salario ni
    categoría/sector, que Google Jobs no entrega estructurados.)
    """
    jobs = fetch_google_jobs_from_db()

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
        }

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
    }


if __name__ == "__main__":
    procesar_vacantes_google()
