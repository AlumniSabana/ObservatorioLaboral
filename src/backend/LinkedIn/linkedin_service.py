"""
linkedin_service.py — recolección de OFERTAS DE EMPLEO públicas de LinkedIn.

╔══════════════════════════════════════════════════════════════════════════════╗
║  ESTA RECOLECCIÓN ESTÁ DESACTIVADA POR DEFECTO Y NO DEBE ACTIVARSE SIN QUE   ║
║  LA UNIVERSIDAD LO APRUEBE POR ESCRITO.                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

POR QUÉ EL INTERRUPTOR
----------------------
LinkedIn sirve ofertas a visitantes anónimos por endpoints públicos (`jobs-guest`),
sin login ni API key. Situación legal, en dos capas:

  1. Datos personales (la capa GRAVE) -> NO APLICA aquí, a propósito.
     Este módulo recolecta ÚNICAMENTE ofertas de empleo publicadas por empresas.
     NUNCA perfiles de personas, candidatos ni reclutadores. Por eso queda fuera
     del alcance de la Ley 1581 de 2012 (habeas data) y del GDPR.

  2. Términos de Uso de LinkedIn (capa CONTRACTUAL) -> sigue vigente.
     Sus ToS prohíben el acceso automatizado, sin importar el volumen. No es
     delito (hiQ v. LinkedIn: raspar datos públicos no viola la CFAA), pero sí es
     un incumplimiento contractual por el que LinkedIn puede actuar —de hecho
     ganó hiQ por esa vía—. A frecuencia trimestral y sin fines comerciales el
     riesgo práctico es mínimo, pero la decisión NO es técnica: es institucional.

Por eso el código existe pero está inerte: `config.LINKEDIN_HABILITADO` es False
salvo que alguien lo ponga en true en `.env` DESPUÉS de la aprobación.

DISEÑO DE HUELLA MÍNIMA (no tocar sin motivo)
---------------------------------------------
  - Tope bajo de páginas por keyword (LINKEDIN_MAX_PAGINAS, 3 por defecto; el
    límite de LinkedIn ronda 10 por IP: nos quedamos muy por debajo).
  - Pausa entre peticiones (LINKEDIN_PAUSA_SEG).
  - Si LinkedIn responde 429 (throttling), se ABORTA la corrida entera. No se
    reintenta, no se rota IP, no se usan proxies: si pide parar, se para.
  - Cadencia prevista: TRIMESTRAL. No programar cron diario.

Uso previsto (una vez aprobado):
    python -m LinkedIn.linkedin_service        # corrida manual trimestral
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from Adzuna.adzuna_service import supabase
from GoogleJobs.google_jobs_service import fecha_de_posted_at
from config import (
    LINKEDIN_HABILITADO,
    LINKEDIN_MAX_PAGINAS,
    LINKEDIN_PAUSA_SEG,
    PROGRAMAS_KEYWORDS_CO,
    es_pertinente,
)

TABLA = "vacantes_linkedin"

# Endpoints públicos que LinkedIn sirve a visitantes anónimos (no requieren auth).
_URL_BUSQUEDA = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_URL_DETALLE = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

# Identificarse honestamente: no se suplanta un navegador para evadir controles.
_HEADERS = {
    "User-Agent": (
        "ObservatorioLaboralUniSabana/1.0 (proyecto académico; contacto: alumni@unisabana.edu.co)"
    ),
    "Accept": "text/html",
}

_PAIS = "co"
_LOCATION = "Colombia"
_TIMEOUT = 30


class LinkedInDesactivado(RuntimeError):
    """Se intentó recolectar sin la aprobación institucional (flag en false)."""


def _verificar_habilitado() -> None:
    """Puerta de entrada: sin aprobación explícita, no se hace ninguna petición."""
    if not LINKEDIN_HABILITADO:
        raise LinkedInDesactivado(
            "La recolección de LinkedIn está DESACTIVADA. Requiere aprobación de la "
            "Universidad (va contra los Términos de Uso de LinkedIn como asunto "
            "contractual). Una vez aprobada, poner LINKEDIN_HABILITADO=true en "
            "src/backend/.env. Ver el encabezado de LinkedIn/linkedin_service.py."
        )


def _extraer_job_id(tarjeta) -> str | None:
    """Id de la oferta desde la tarjeta HTML (varios formatos según el layout)."""
    contenedor = tarjeta.find("div", {"data-entity-urn": True})
    if contenedor:
        urn = contenedor.get("data-entity-urn", "")
        if ":" in urn:
            return urn.rsplit(":", 1)[-1]
    enlace = tarjeta.find("a", href=True)
    if enlace:
        m = re.search(r"-(\d+)\?", enlace["href"]) or re.search(r"/view/[^/]*?(\d+)", enlace["href"])
        if m:
            return m.group(1)
    return None


def _texto(nodo) -> str | None:
    return nodo.get_text(strip=True) if nodo else None


def _parsear_tarjetas(html: str, keyword: str, programa: str,
                      referencia: date | None = None) -> List[Dict[str, Any]]:
    """Convierte el HTML de resultados en filas listas para la BD."""
    sopa = BeautifulSoup(html, "html.parser")
    filas: List[Dict[str, Any]] = []

    for tarjeta in sopa.find_all("li"):
        job_id = _extraer_job_id(tarjeta)
        if not job_id:
            continue

        titulo = _texto(tarjeta.find("h3"))
        # LinkedIn busca por full-text y el programa se estampa con la keyword,
        # sin mirar el título: descarta lo que no puede pertenecer a ese programa
        # (ver EXCLUSIONES_PROGRAMA en config.py).
        if not es_pertinente(programa, titulo):
            continue
        empresa = _texto(tarjeta.find("h4"))
        ubicacion = _texto(tarjeta.find("span", class_=re.compile("job-search-card__location")))
        fecha_nodo = tarjeta.find("time")
        posted_at = _texto(fecha_nodo)
        # `time datetime="YYYY-MM-DD"` es la fecha exacta cuando LinkedIn la da;
        # si no, se convierte el relativo ("hace 3 días") como en Google Jobs.
        fecha_abs = (fecha_nodo or {}).get("datetime") if fecha_nodo else None
        if not fecha_abs and posted_at:
            fecha_abs = fecha_de_posted_at(posted_at, referencia)

        enlace = tarjeta.find("a", href=True)
        apply_link = enlace["href"].split("?")[0] if enlace else None

        filas.append({
            "job_id": job_id,
            "title": titulo,
            "company": empresa,
            "location": ubicacion,
            "city": (ubicacion or "").split(",")[0].strip() or None,
            "posted_at": posted_at,
            "fecha_publicacion": fecha_abs,
            "apply_link": apply_link,
            "keyword": keyword,
            "programa_relacionado": programa,
            "pais": _PAIS,
        })
    return filas


def _buscar_pagina(keyword: str, start: int) -> str | None:
    """
    Una página de resultados (10 ofertas). Devuelve el HTML, o None si hay que
    detenerse (throttling o error). NUNCA reintenta ni rota IP: si LinkedIn pide
    parar, se para.
    """
    params = {"keywords": keyword, "location": _LOCATION, "start": start}
    try:
        r = requests.get(_URL_BUSQUEDA, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    except Exception as e:
        print(f"   ❌ Error de red en '{keyword}' (start={start}): {e}")
        return None

    if r.status_code == 429:
        print("   ⛔ LinkedIn respondió 429 (throttling). Se aborta la corrida por diseño.")
        return None
    if r.status_code != 200:
        print(f"   ⚠ HTTP {r.status_code} en '{keyword}' (start={start}); se omite.")
        return None
    return r.text


def guardar_ofertas(filas: List[Dict[str, Any]]) -> int:
    """Upsert por job_id (volver a ver una oferta la actualiza, no la duplica)."""
    if not filas:
        return 0
    try:
        supabase.table(TABLA).upsert(filas, on_conflict="job_id").execute()
        return len(filas)
    except Exception as e:
        print(f"   ❌ Error guardando en {TABLA}: {e}")
        return 0


def recolectar_linkedin(programas: List[str] | None = None,
                        max_paginas: int | None = None,
                        keywords_por_programa: int = 1) -> Dict[str, Any]:
    """
    Corrida TRIMESTRAL de recolección de ofertas públicas en Colombia.

    Lanza LinkedInDesactivado si no hay aprobación institucional (flag en false).
    Por defecto usa solo la primera keyword en español de cada programa
    (PROGRAMAS_KEYWORDS_CO), para mantener la huella mínima: una búsqueda por
    programa. `keywords_por_programa` permite ampliar puntualmente (p. ej. antes
    de una presentación) sin cambiar el comportamiento por defecto de la corrida
    trimestral automática.
    """
    _verificar_habilitado()

    paginas = max_paginas or LINKEDIN_MAX_PAGINAS
    objetivo = programas or list(PROGRAMAS_KEYWORDS_CO)
    hoy = date.today()

    total_vistas = 0
    total_guardadas = 0
    abortado = False

    print(f"🔎 LinkedIn (ofertas públicas, Colombia) — {len(objetivo)} programas, "
          f"{keywords_por_programa} keyword(s) c/u, máx {paginas} páginas c/u, "
          f"pausa {LINKEDIN_PAUSA_SEG}s")

    for programa in objetivo:
        keywords = (PROGRAMAS_KEYWORDS_CO.get(programa) or [])[:keywords_por_programa]
        if not keywords:
            continue

        for keyword in keywords:
            print(f"  • {programa} — '{keyword}'")

            for pagina in range(paginas):
                html = _buscar_pagina(keyword, start=pagina * 10)
                if html is None:
                    abortado = True
                    break

                filas = _parsear_tarjetas(html, keyword, programa, hoy)
                if not filas:
                    break  # sin más resultados para esta keyword

                total_vistas += len(filas)
                total_guardadas += guardar_ofertas(filas)
                time.sleep(LINKEDIN_PAUSA_SEG)

            if abortado:
                break
        if abortado:
            break

    resumen = {
        "fuente": "linkedin",
        "programas_procesados": len(objetivo),
        "ofertas_vistas": total_vistas,
        "ofertas_guardadas": total_guardadas,
        "abortado_por_throttling": abortado,
        "nota": "Solo ofertas de empleo públicas. No se recolectan datos de personas.",
    }
    print(f"✅ Fin: {total_guardadas} ofertas guardadas"
          f"{' (corrida abortada por throttling)' if abortado else ''}")
    return resumen


def leer_ofertas_linkedin() -> List[Dict[str, Any]]:
    """Lee las ofertas de LinkedIn ya almacenadas (paginado)."""
    filas: List[Dict[str, Any]] = []
    start, page = 0, 1000
    while True:
        try:
            r = supabase.table(TABLA).select("*").order("job_id").range(start, start + page - 1).execute()
        except Exception as e:
            print(f"Error leyendo {TABLA}: {e}")
            break
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < page:
            break
        start += page
    return filas


def estado_linkedin() -> Dict[str, Any]:
    """Estado de la fuente: si está habilitada y cuántas ofertas hay guardadas."""
    try:
        r = supabase.table(TABLA).select("job_id", count="exact", head=True).execute()
        almacenadas = r.count or 0
        tabla_ok = True
    except Exception:
        almacenadas = 0
        tabla_ok = False

    return {
        "habilitado": LINKEDIN_HABILITADO,
        "tabla_creada": tabla_ok,
        "ofertas_almacenadas": almacenadas,
        "max_paginas": LINKEDIN_MAX_PAGINAS,
        "pausa_seg": LINKEDIN_PAUSA_SEG,
        "cadencia_prevista": "trimestral",
        "alcance": "Solo ofertas de empleo públicas (nunca perfiles de personas).",
        "requisito": (
            "Desactivado hasta aprobación de la Universidad: recolectar de LinkedIn "
            "va contra sus Términos de Uso (asunto contractual)."
        ),
    }


if __name__ == "__main__":
    try:
        recolectar_linkedin()
    except LinkedInDesactivado as e:
        print(f"\n⛔ {e}\n")
