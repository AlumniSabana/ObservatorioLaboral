"""
Google Jobs API Service (vía SerpApi) para recolección de vacantes en Colombia.

Reutiliza el cliente de Supabase y la tabla `vacantes` del servicio de Adzuna,
guardando los registros con fuente='google_jobs' para poder filtrarlos por
separado en la interfaz de análisis de mercado.
"""

import hashlib
import requests
from typing import List, Dict, Any

from config import SERPAPI_KEY, PROGRAMAS_KEYWORDS
# Reutilizamos el cliente de Supabase y el borrado por fuente ya existentes
from Adzuna.adzuna_service import supabase, borrar_vacantes_por_fuente

SERPAPI_URL = "https://serpapi.com/search.json"

# Mapeo de los tipos de jornada que entrega Google Jobs a los mismos valores
# que usa Adzuna (para que las gráficas de "Modalidades de trabajo" coincidan)
_SCHEDULE_MAP = {
    "full-time": "full_time",
    "full time": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "contractor": "contract",
    "contract": "contract",
    "internship": "internship",
    "temporary": "temporary",
}


def _google_job_id_to_int(job_id: str) -> int:
    """Convierte el job_id (cadena larga de Google) en un entero estable.

    La columna `id` de la tabla es numérica (bigint), por lo que derivamos un
    entero determinista del job_id mediante un hash. Esto permite que el
    upsert deduplique correctamente las mismas vacantes en recolecciones
    sucesivas. 15 dígitos hexadecimales caben holgadamente en un bigint.
    """
    digest = hashlib.sha1(job_id.encode("utf-8")).hexdigest()[:15]
    return int(digest, 16)


def _map_schedule_type(detected_extensions: Dict[str, Any]) -> str:
    schedule = (detected_extensions or {}).get("schedule_type")
    if not schedule:
        return None
    return _SCHEDULE_MAP.get(schedule.strip().lower())


def _extract_redirect_url(job: Dict[str, Any]) -> str:
    apply_options = job.get("apply_options") or []
    if apply_options and apply_options[0].get("link"):
        return apply_options[0]["link"]
    related_links = job.get("related_links") or []
    if related_links and related_links[0].get("link"):
        return related_links[0]["link"]
    return job.get("share_link")


def buscar_vacantes_google(keyword: str, num_pages: int = 3, location: str = "Colombia") -> List[Dict[str, Any]]:
    """Busca vacantes en Google Jobs (vía SerpApi) para una keyword dada."""
    if not SERPAPI_KEY:
        print("   ❌ SERPAPI_KEY no configurada; se omite la búsqueda en Google Jobs.")
        return []

    all_results = []
    next_page_token = None

    for page in range(1, num_pages + 1):
        try:
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

            print(f"   🔍 [Google Jobs] Consultando '{keyword}' - Página {page}...")

            response = requests.get(SERPAPI_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                print(f"   ❌ SerpApi error para '{keyword}': {data['error']}")
                break

            results = data.get("jobs_results", [])
            all_results.extend(results)
            print(f"   ✅ Encontrados {len(results)} resultados")

            # Token de paginación de Google Jobs
            next_page_token = (
                data.get("serpapi_pagination", {}).get("next_page_token")
                or data.get("next_page_token")
            )
            if not results or not next_page_token:
                break

        except Exception as e:
            print(f"   ❌ Error buscando '{keyword}' página {page} en Google Jobs: {str(e)}")
            break

    return all_results


def guardar_vacante_google(job: Dict[str, Any], programa: str) -> bool:
    """Guarda o actualiza una vacante de Google Jobs en Supabase."""
    try:
        job_id = job.get("job_id")
        if not job_id:
            return False

        detected_extensions = job.get("detected_extensions", {})

        row = {
            "id": _google_job_id_to_int(job_id),
            "title": job.get("title"),
            "company": job.get("company_name"),
            "location": job.get("location"),
            "country": "Colombia",
            "latitude": None,
            "longitude": None,
            "description": job.get("description"),
            "category": None,
            "contract_time": _map_schedule_type(detected_extensions),
            "salary_min": None,
            "salary_max": None,
            "salary_is_predicted": False,
            "redirect_url": _extract_redirect_url(job),
            "created_at": None,
            "fuente": "google_jobs",
            "programa_relacionado": programa,
        }

        supabase.table("vacantes").upsert(row, on_conflict="id").execute()
        return True

    except Exception as e:
        print(f"   ❌ Error guardando vacante '{job.get('title', 'Sin título')}': {str(e)}")
        return False


def procesar_vacantes_google(borrar: bool = False):
    """Procesa todas las vacantes de Google Jobs (Colombia) usando las keywords de cada programa."""
    print("🚀 Iniciando recolección de vacantes desde Google Jobs (Colombia)...\n")

    if not SERPAPI_KEY:
        return {
            "status": "error",
            "message": "SERPAPI_KEY no configurada. Agrega la variable de entorno para recolectar de Google Jobs.",
        }

    if borrar:
        borrar_vacantes_por_fuente("google_jobs")

    total_vacantes = 0
    total_guardadas = 0

    for programa, keywords in PROGRAMAS_KEYWORDS.items():
        print(f"\n=== Procesando {programa} (Google Jobs) ===")
        vacantes_programa = 0

        for keyword in keywords:
            print(f"  🔑 Keyword: '{keyword}'")
            vacantes = buscar_vacantes_google(keyword, num_pages=3)

            vacantes_programa += len(vacantes)
            total_vacantes += len(vacantes)

            guardadas = 0
            for vacante in vacantes:
                if guardar_vacante_google(vacante, programa):
                    guardadas += 1
                    total_guardadas += 1

            print(f"     → {len(vacantes)} encontradas | {guardadas} guardadas")

        print(f"  ✅ Total para {programa}: {vacantes_programa} vacantes procesadas")

    print(f"\n🎉 === RESUMEN FINAL (Google Jobs) ===")
    print(f"   Total vacantes encontradas: {total_vacantes}")
    print(f"   Total vacantes guardadas: {total_guardadas}")
    print(f"   Programas procesados: {len(PROGRAMAS_KEYWORDS)}")

    return {
        "status": "completed",
        "total_vacantes": total_vacantes,
        "total_guardadas": total_guardadas,
        "programas_procesados": len(PROGRAMAS_KEYWORDS),
    }


if __name__ == "__main__":
    procesar_vacantes_google()
