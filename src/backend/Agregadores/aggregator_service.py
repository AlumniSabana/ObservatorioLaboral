"""
Agregadores que NUTREN la tabla `vacantes_google` (mercado Colombia).

En vez de crear tablas nuevas, estos adaptadores traen vacantes de otras fuentes
y las insertan en la MISMA tabla `vacantes_google`, manteniendo la comparabilidad
(mismo esquema) y evitando duplicar lo que ya trajo Google Jobs.

Fuentes:
  - Careerjet -> API pública gratuita con índice de Colombia (locale es_CO).
    Implementación COMPLETA; solo requiere un Affiliate ID.
  - Talent.com / WhatJobs -> programas de "publisher": el endpoint y los nombres
    de campos exactos dependen de tu cuenta. El adaptador queda listo pero DEBES
    confirmar/ajustar la request con la documentación que te den al registrarte.
    Sin su credencial configurada, simplemente se omiten.

Deduplicación (lo más importante): los agregadores re-indexan las mismas bolsas
que Google Jobs, así que ANTES de insertar comparamos contra lo que ya existe en
la tabla mediante una "clave" normalizada (título + empresa + ciudad). Si ya
existe, NO se inserta. Así la tabla crece sin inflarse con duplicados.

Orquestación:
  procesar_colombia(borrar) -> corre Google Jobs (SerpApi) + los agregadores,
  todo hacia vacantes_google. Es lo que llama /scrape?fuente=google_jobs.
"""

import re
import html
import hashlib
import unicodedata
from typing import List, Dict, Any, Set

import requests

from config import (
    CAREERJET_AFFILIATE_ID,
    CAREERJET_LOCALE,
    TALENT_PUBLISHER_ID,
    WHATJOBS_PUBLISHER_ID,
    PROGRAMAS_KEYWORDS,
)

# Careerjet exige user_ip y user_agent en cada petición (los usa para analítica
# antifraude del programa de afiliados). En un proceso batch no hay un usuario
# final real, así que enviamos valores genéricos del servidor.
_CAREERJET_USER_AGENT = "ObservatorioLaboral-AlumniSabana/1.0"
_CAREERJET_USER_IP = "190.0.0.1"  # IP genérica de Colombia (placeholder)
# Careerjet RECHAZA la petición si no llega un header Referer (error "Undeclared
# referrer"). Debe ser la URL del sitio que llama la API.
_CAREERJET_REFERER = "https://www.unisabana.edu.co/"
# La API pública de Careerjet sirve por HTTP (el puerto 443/HTTPS rechaza la conexión).
_CAREERJET_URL = "http://public.api.careerjet.net/search"
# Reutilizamos el cliente, la tabla y utilidades de Google Jobs (sin duplicar).
from GoogleJobs.google_jobs_service import (
    supabase,
    TABLA,
    fetch_google_jobs_from_db,
    borrar_vacantes_google,
    procesar_vacantes_google,
)


# ---------------------------------------------------------------------------
# Normalización y deduplicación
# ---------------------------------------------------------------------------

def _strip_accents(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _norm(texto: str) -> str:
    """Normaliza un texto para comparar: sin acentos, minúsculas, sin puntuación."""
    if not texto:
        return ""
    texto = _strip_accents(texto).lower()
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _clave_dedup(title: str, company: str, city: str) -> str:
    """Clave de deduplicación: misma vacante si coinciden cargo + empresa + ciudad."""
    return f"{_norm(title)}|{_norm(company)}|{_norm(city)}"


def _job_id(source: str, clave: str) -> str:
    """ID estable para la columna PK `job_id` (texto). Determinista por fuente+clave."""
    return f"{source}:{hashlib.sha1(clave.encode('utf-8')).hexdigest()[:16]}"


def _ciudad(location: str) -> str:
    """De 'Bogotá, Colombia' devuelve 'Bogotá'."""
    if not location:
        return None
    return location.split(",")[0].strip()


def _strip_html(texto: str) -> str:
    """Quita etiquetas HTML y normaliza espacios (los snippets suelen traer HTML)."""
    if not texto:
        return None
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def _cargar_claves_existentes() -> Set[str]:
    """Lee las vacantes ya guardadas y arma el conjunto de claves de dedup."""
    claves = set()
    for job in fetch_google_jobs_from_db():
        claves.add(_clave_dedup(job.get("title"), job.get("company"), job.get("city")))
    print(f"🔑 {len(claves)} vacantes existentes cargadas para deduplicación.")
    return claves


def _guardar(vacante: Dict[str, Any], source: str, programa: str, keyword: str, claves: Set[str]) -> bool:
    """Inserta una vacante normalizada en vacantes_google si no es duplicada.

    `vacante` es un dict ya mapeado al esquema común (ver adaptadores). Devuelve
    True si se guardó (era nueva), False si se omitió (duplicada o sin título).
    """
    title = vacante.get("title")
    if not title:
        return False

    clave = _clave_dedup(title, vacante.get("company"), vacante.get("city"))
    if clave in claves:
        return False  # ya existe (Google Jobs u otro agregador): no duplicamos

    row = {
        "job_id": _job_id(source, clave),
        "title": title,
        "company": vacante.get("company"),
        "location": vacante.get("location"),
        "city": vacante.get("city"),
        # `via` = bolsa de origen (para comparar con Google Jobs); si no se conoce,
        # usamos el nombre del agregador.
        "via": vacante.get("via") or source,
        "schedule_type": vacante.get("schedule_type"),
        "work_from_home": None,
        "posted_at": vacante.get("posted_at"),
        "salary_raw": vacante.get("salary_raw"),
        "description": vacante.get("description"),
        "qualifications": None,
        "responsibilities": None,
        "benefits": None,
        "apply_link": vacante.get("apply_link"),
        "thumbnail": None,
        "extensions": None,
        "keyword": keyword,
        "programa_relacionado": programa,
    }

    try:
        supabase.table(TABLA).upsert(row, on_conflict="job_id").execute()
        claves.add(clave)
        return True
    except Exception as e:
        print(f"   ❌ Error guardando '{title}': {e}")
        return False


# ---------------------------------------------------------------------------
# Adaptadores por fuente: devuelven listas de vacantes ya mapeadas al esquema común
# ---------------------------------------------------------------------------

def buscar_careerjet(keyword: str, location: str = "Colombia") -> List[Dict[str, Any]]:
    """Busca en Careerjet (API pública gratuita). Sin Affiliate ID, se omite.

    Careerjet sí tiene índice colombiano: se apunta con
    `locale_code = es_CO` (configurable vía CAREERJET_LOCALE). Devuelve la bolsa
    de origen en `site` (ej. computrabajo.com.co), útil para comparar con Google Jobs.
    """
    if not CAREERJET_AFFILIATE_ID:
        return []
    try:
        params = {
            "locale_code": CAREERJET_LOCALE,   # es_CO = Colombia
            "keywords": keyword,
            "location": location,
            "affid": CAREERJET_AFFILIATE_ID,
            "user_ip": _CAREERJET_USER_IP,
            "user_agent": _CAREERJET_USER_AGENT,
            "pagesize": 50,
            "sort": "date",
        }
        # El header Referer es OBLIGATORIO para Careerjet (si no, devuelve error).
        resp = requests.get(
            _CAREERJET_URL, params=params, headers={"Referer": _CAREERJET_REFERER}, timeout=30
        )
        if resp.status_code != 200:
            print(f"   ❌ Careerjet HTTP {resp.status_code} para '{keyword}' (¿Affiliate ID válido?)")
            return []
        data = resp.json()
        if data.get("type") == "ERROR":
            print(f"   ❌ Careerjet API error para '{keyword}': {data.get('error')}")
            return []
        # type puede ser "JOBS" o "LOCATIONS" (cuando la ubicación es ambigua).
        if data.get("type") != "JOBS":
            return []
        resultados = []
        for j in data.get("jobs", []):
            loc = j.get("locations")
            resultados.append({
                "title": j.get("title"),
                "company": j.get("company"),
                "location": loc,
                "city": _ciudad(loc),
                "via": j.get("site"),  # bolsa de origen, ej. "computrabajo.com.co"
                "schedule_type": None,  # Careerjet no lo entrega de forma estructurada
                "salary_raw": j.get("salary"),
                "description": _strip_html(j.get("description")),
                "apply_link": j.get("url"),
                "posted_at": j.get("date"),
            })
        return resultados
    except Exception as e:
        print(f"   ❌ Careerjet error '{keyword}': {e}")
        return []


def buscar_whatjobs(keyword: str, location: str = "Colombia") -> List[Dict[str, Any]]:
    """Busca en WhatJobs (programa de publisher).

    ⚠️ El endpoint/parámetros/campos exactos son específicos de tu cuenta de
    publisher; ajústalos según la documentación que te entreguen. Sin
    WHATJOBS_PUBLISHER_ID configurado, se omite.
    """
    if not WHATJOBS_PUBLISHER_ID:
        return []
    try:
        # TODO(publisher): confirmar URL y nombres de parámetros con tu cuenta.
        url = "https://api.whatjobs.com/api/v1/jobs.php"
        params = {
            "publisher": WHATJOBS_PUBLISHER_ID,
            "keyword": keyword,
            "location": location,
            "countrycode": "co",
            "format": "json",
            "limit": 50,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs") or data.get("results") or []
        resultados = []
        for j in jobs:
            loc = j.get("location")
            resultados.append({
                "title": j.get("title") or j.get("jobTitle"),
                "company": j.get("company") or j.get("companyName"),
                "location": loc,
                "city": _ciudad(loc) or j.get("city"),
                "via": j.get("site") or j.get("source") or "WhatJobs",
                "schedule_type": j.get("type") or j.get("jobEmploymentType"),
                "salary_raw": j.get("salary"),
                "description": _strip_html(j.get("description") or j.get("snippet")),
                "apply_link": j.get("url") or j.get("link"),
                "posted_at": j.get("age") or j.get("date"),
            })
        return resultados
    except Exception as e:
        print(f"   ❌ WhatJobs error '{keyword}': {e}")
        return []


def buscar_talent(keyword: str, location: str = "Colombia") -> List[Dict[str, Any]]:
    """Busca en Talent.com (programa de publisher).

    ⚠️ Talent.com entrega vacantes a publishers mediante un feed cuyo endpoint y
    formato dependen de tu cuenta. Ajusta URL, parámetros y nombres de campos con
    tu onboarding de publisher. Sin TALENT_PUBLISHER_ID configurado, se omite.
    """
    if not TALENT_PUBLISHER_ID:
        return []
    try:
        # TODO(publisher): confirmar URL y nombres de parámetros con tu cuenta.
        url = "https://api.talent.com/jobs"
        params = {
            "publisher": TALENT_PUBLISHER_ID,
            "k": keyword,
            "l": location,
            "countrycode": "co",
            "format": "json",
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs") or data.get("results") or []
        resultados = []
        for j in jobs:
            loc = j.get("location")
            resultados.append({
                "title": j.get("title"),
                "company": j.get("company"),
                "location": loc,
                "city": _ciudad(loc),
                "via": j.get("source") or "Talent.com",
                "schedule_type": j.get("type"),
                "salary_raw": j.get("salary"),
                "description": _strip_html(j.get("description") or j.get("snippet")),
                "apply_link": j.get("url") or j.get("link"),
                "posted_at": j.get("date") or j.get("postdate"),
            })
        return resultados
    except Exception as e:
        print(f"   ❌ Talent.com error '{keyword}': {e}")
        return []


# Registro de fuentes: (nombre, función, credencial). Se omiten las que no tengan credencial.
_FUENTES = [
    ("careerjet", buscar_careerjet, CAREERJET_AFFILIATE_ID),
    ("talent", buscar_talent, TALENT_PUBLISHER_ID),
    ("whatjobs", buscar_whatjobs, WHATJOBS_PUBLISHER_ID),
]


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def procesar_agregadores(claves: Set[str] = None) -> Dict[str, Any]:
    """Recorre programas/keywords en cada agregador configurado y guarda lo nuevo.

    Deduplica contra `claves` (las vacantes ya existentes); si no se pasa, las carga.
    """
    if claves is None:
        claves = _cargar_claves_existentes()

    activos = [(nombre, fn) for (nombre, fn, cred) in _FUENTES if cred]
    if not activos:
        print("ℹ️ Ningún agregador configurado (faltan keys/credenciales). Se omite.")
        return {"status": "sin_agregadores", "guardadas": 0, "por_fuente": {}}

    resumen = {}
    total_guardadas = 0
    for nombre, fn in activos:
        print(f"\n=== Agregador: {nombre} ===")
        encontradas = 0
        guardadas = 0
        for programa, keywords in PROGRAMAS_KEYWORDS.items():
            for kw in keywords:
                vacantes = fn(kw)
                encontradas += len(vacantes)
                for v in vacantes:
                    if _guardar(v, nombre, programa, kw, claves):
                        guardadas += 1
        resumen[nombre] = {"encontradas": encontradas, "guardadas_nuevas": guardadas}
        total_guardadas += guardadas
        print(f"  ✅ {nombre}: {encontradas} encontradas | {guardadas} nuevas (tras dedup)")

    return {"status": "completed", "por_fuente": resumen, "guardadas": total_guardadas}


def procesar_colombia(borrar: bool = False) -> Dict[str, Any]:
    """Recolección completa del mercado Colombia hacia vacantes_google:
    Google Jobs (SerpApi) + agregadores (Careerjet/Talent/WhatJobs), deduplicado.
    """
    print("🚀 Recolección Colombia: Google Jobs + agregadores...\n")

    # Si se pide borrar, se vacía la tabla UNA sola vez aquí (no en cada paso).
    # if borrar:
        # borrar_vacantes_google()

    # 1) Google Jobs (SerpApi). borrar=False porque ya borramos arriba.
    resultado_google = procesar_vacantes_google(borrar=False)

    # 2) Agregadores, deduplicando contra lo que Google Jobs acaba de dejar.
    resultado_agg = procesar_agregadores()

    return {
        "status": "completed",
        "google_jobs": resultado_google,
        "agregadores": resultado_agg,
    }


if __name__ == "__main__":
    procesar_colombia()
