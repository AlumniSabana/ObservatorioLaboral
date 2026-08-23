"""
demanda_actual.py — top-N de demanda para la página de Tendencias.

Sirve las 4 gráficas "más demandados" (cargos, sectores, empresas, programas)
que antes vivían en Análisis de mercado, pero AQUÍ leen la misma fuente que las
tendencias — la tabla `vacantes_historicas` — para que respondan a los MISMOS
filtros de esa página: país(es), programa y seniority.

Por qué no reusar get_analytics (Análisis de mercado): aquel lee la tabla
`vacantes`, que solo tiene Adzuna EE.UU. + Google Colombia. `vacantes_historicas`
tiene los 6 mercados (us, gb, ca, mx, es, co), así que es la única fuente capaz de
respetar el filtro de países de Tendencias.

Traducciones EN→ES iguales al resto (cargos y sectores). El seniority no es una
columna: se infiere del título con `detectar_seniority` (igual que el backfill).
"""

from __future__ import annotations

import time as _time
from collections import Counter
from typing import Any

from Adzuna.adzuna_service import normalize_title, supabase
from config import es_pertinente, _plegar
from Tendencias.seniority import detectar_seniority
from Tendencias.tendencias_service import PAIS_DEFECTO, TODOS
from traducciones import traducir_cargo, traducir_sector

_TABLA = "vacantes_historicas"

# Caché en memoria de la muestra histórica (solo las columnas que se agregan).
# Son ~61k filas (decenas de viajes a Supabase); la tabla solo cambia al recolectar.
_cache: dict[str, Any] = {"ts": 0.0, "rows": None}
_TTL = 600  # segundos (10 min): la muestra histórica solo cambia al recolectar,
#            y ese flujo invalida el caché explícitamente (invalidar_cache()).


def _leer_historico_demanda() -> list[dict]:
    """Lee (cacheada) la muestra histórica con las columnas necesarias."""
    ahora = _time.time()
    if _cache["rows"] is not None and (ahora - _cache["ts"]) < _TTL:
        return _cache["rows"]

    filas: list[dict] = []
    start, page = 0, 1000
    while True:
        r = (
            supabase.table(_TABLA)
            .select("title,company,category,programa_relacionado,pais")
            .order("id")
            .range(start, start + page - 1)
            .execute()
        )
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < page:
            break
        start += page

    _cache.update(ts=ahora, rows=filas)
    return filas


def invalidar_cache() -> None:
    """Fuerza la relectura en la próxima llamada (tras recolectar histórico)."""
    _cache.update(ts=0.0, rows=None)


# Nombres placeholder que algunas fuentes ponen cuando el empleador pidió
# anonimato (frecuente en Google Jobs Colombia y en el SPE). No son una empresa
# real: mostrarlos como "la empresa que más contrata" es ruido, no información.
_EMPRESAS_CONFIDENCIALES = {
    "confidential",
    "confidencial",
    "empresa confidencial",
    "empresa confidencial ",
    "razon social confidencial",
    "razón social confidencial",
    "nombre confidencial",
    "importante empresa",
    "importante empresa del sector",
    "empresa del sector",
    "n/a",
    "no disponible",
}


def _es_empresa_confidencial(nombre: str) -> bool:
    return _plegar(nombre).strip() in _EMPRESAS_CONFIDENCIALES


def demanda_actual(programa: str = TODOS, seniority: str = TODOS,
                   paises: list[str] | None = None, top: int = 15) -> dict[str, Any]:
    """
    Top-N de cargos, sectores, empresas y programas sobre la muestra histórica,
    filtrada por país(es), programa y seniority (los filtros de Tendencias).

    Devuelve listas `[{label, count}]` ya traducidas al español.
    """
    paises = paises or [PAIS_DEFECTO]
    conjunto_paises = set(paises)

    filas = _leer_historico_demanda()

    cargos: Counter = Counter()
    sectores: Counter = Counter()
    empresas: Counter = Counter()
    programas: Counter = Counter()
    total = 0

    for f in filas:
        if f.get("pais") not in conjunto_paises:
            continue
        prog = f.get("programa_relacionado")
        if programa != TODOS and prog != programa:
            continue
        # La etiqueta `programa_relacionado` viene de la keyword buscada, no del
        # título: "registered nurse" arrastra "Registered Veterinary Nurse" a
        # Enfermería. Se descarta al leer porque las filas ya guardadas conservan
        # su etiqueta vieja (el filtro también corre al recolectar).
        #
        # El descarte es de ATRIBUCIÓN, no de validez: una vacante de veterinaria
        # es una vacante real. Por eso solo se excluye del conteo cuando se está
        # mirando UN programa; con "Todos" sigue sumando al total del mercado y lo
        # único que se corrige es a qué programa se le acredita (más abajo).
        pertinente = es_pertinente(prog, f.get("title"))
        if programa != TODOS and not pertinente:
            continue
        if seniority != TODOS and detectar_seniority(f.get("title")) != seniority:
            continue

        total += 1
        cargo = traducir_cargo(normalize_title(f.get("title") or ""))
        if cargo:
            cargos[cargo] += 1
        sector = traducir_sector(f.get("category"))
        if sector:
            sectores[sector] += 1
        empresa = f.get("company")
        if empresa and not _es_empresa_confidencial(empresa):
            empresas[empresa] += 1
        # Solo se acredita al programa si el título de verdad le corresponde.
        if prog and pertinente:
            programas[prog] += 1

    def _top(cnt: Counter) -> list[dict]:
        return [{"label": k, "count": v} for k, v in cnt.most_common(top)]

    return {
        "cargos": _top(cargos),
        "sectores": _top(sectores),
        "empresas": _top(empresas),
        "programas": _top(programas),
        "meta": {
            "total": total,
            "paises": paises,
            "programa": programa,
            "seniority": seniority,
        },
    }
