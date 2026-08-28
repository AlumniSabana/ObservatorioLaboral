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
from config import es_pertinente, _plegar, coincide_con_keyword
from Salarios.trm_service import tasas_a_cop, fecha_tasas, PAIS_MONEDA
from Tendencias.escolaridad import detectar_escolaridad
from Tendencias.seniority import detectar_seniority
from Tendencias.tendencias_service import PAIS_DEFECTO, TODOS
from traducciones import agrupar_sector, traducir_cargo, traducir_sector

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
            .select("title,company,category,programa_relacionado,pais,keyword,salary_min,salary_max")
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
                   paises: list[str] | None = None, top: int = 15,
                   escolaridad: str = TODOS) -> dict[str, Any]:
    """
    Top-N de cargos, sectores, empresas y programas sobre la muestra histórica,
    filtrada por país(es), programa, seniority y escolaridad (los filtros de
    Tendencias).

    `escolaridad` es un eje DISTINTO de `seniority`: no mide experiencia sino
    tipo de ocupación (Grandes Grupos CIUO-08 + Junior/Recién Graduado). Ver
    Tendencias/escolaridad.py. Vive solo aquí (no en el motor de tendencias
    temporales) a propósito: es el filtro que alimenta estas 4 gráficas de
    demanda actual, no la serie histórica.

    Devuelve listas `[{label, count}]` ya traducidas al español (los sectores,
    además, agrupados en los 6 campos amplios de `agrupar_sector`).
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
        # A diferencia de `es_pertinente` (más abajo), esto no es un problema de
        # ATRIBUCIÓN sino de VALIDEZ: el backfill de Adzuna pide más antiguas
        # primero, lo que desactiva el orden por relevancia de la API, y para
        # keywords amplias la mayoría de lo que vuelve no tiene relación real
        # con lo buscado (ni con este programa ni con ningún otro). Por eso se
        # descarta siempre, incluso con "Todos los programas". Ver
        # coincide_con_keyword() en config.py.
        if not coincide_con_keyword(f.get("keyword"), f.get("title")):
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
        if escolaridad != TODOS and detectar_escolaridad(f.get("title")) != escolaridad:
            continue

        total += 1
        cargo = traducir_cargo(normalize_title(f.get("title") or ""))
        if cargo:
            cargos[cargo] += 1
        sector = agrupar_sector(traducir_sector(f.get("category")))
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
            "escolaridad": escolaridad,
        },
    }


def salario_vacantes_cop(programa: str, paises: list[str] | None = None) -> dict[str, Any]:
    """Salario promedio MENSUAL en COP de las vacantes de Adzuna seleccionadas.

    Solo Adzuna (us/gb/ca/mx/es) trae salario estructurado — Google Jobs solo
    trae `salary_raw` como texto libre y LinkedIn no trae salario en absoluto,
    así que ninguno de los dos aporta aquí aunque estén seleccionados.

    Adzuna publica el salario ANUAL en la moneda local de cada mercado. Se
    promedia min/max de cada vacante, se divide entre 12 y se convierte a COP
    con la TRM del momento (Salarios/trm_service.py), para poder mostrarlo al
    lado del salario mensual de GEIH que ya trae esta misma tarjeta.

    Reusa las mismas reglas de pertinencia que el resto de Tendencias
    (`es_pertinente`, `coincide_con_keyword`): una vacante que no pasa esos
    filtros tampoco debería contar aquí.
    """
    paises_moneda = [p for p in (paises or []) if p in PAIS_MONEDA]
    if not paises_moneda or not programa or programa == TODOS:
        return {"disponible": False}

    tasas = tasas_a_cop()
    if not tasas:
        return {"disponible": False}

    filas = _leer_historico_demanda()
    valores_cop: list[float] = []
    for f in filas:
        if f.get("pais") not in paises_moneda:
            continue
        if f.get("programa_relacionado") != programa:
            continue
        if not es_pertinente(programa, f.get("title")):
            continue
        if not coincide_con_keyword(f.get("keyword"), f.get("title")):
            continue
        smin, smax = f.get("salary_min"), f.get("salary_max")
        if not smin and not smax:
            continue
        anual_local = (smin + smax) / 2 if (smin and smax) else (smin or smax)
        mensual_cop = anual_local / 12 * tasas[PAIS_MONEDA[f["pais"]]]
        valores_cop.append(mensual_cop)

    if not valores_cop:
        return {"disponible": False}

    return {
        "disponible": True,
        "media_cop": round(sum(valores_cop) / len(valores_cop)),
        "n": len(valores_cop),
        "paises": paises_moneda,
        "trm_fecha": fecha_tasas(),
    }
