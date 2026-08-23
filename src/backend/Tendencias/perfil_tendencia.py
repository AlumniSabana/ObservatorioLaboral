"""
perfil_tendencia.py — tendencia de demanda OBSERVADA de un programa.

Para la página "Perfil Ocupacional". Reusa (sin editar) los helpers de
`skills_demandadas.py` que ya calculan el share mensual de cada programa a partir
de la tabla precalculada `tendencias_observaciones`.

IMPORTANTE: es una tendencia OBSERVADA (lo que ha pasado en la muestra histórica),
NO una proyección/forecast. La UI debe rotularla así.
"""

from __future__ import annotations

from typing import Any

from Tendencias.skills_demandadas import _demanda_por_programa_mensual, _media_movil
from Tendencias.tendencias_service import PAIS_DEFECTO, TODOS, calcular_tendencia

# Por encima de esta magnitud, la variación % no es fiable (base minúscula o pico
# reciente de datos la disparan). Se omite y se muestra solo la dirección robusta.
_VARIACION_MAX_FIABLE = 300.0


def tendencia_programa(programa: str, paises: list[str] | None = None) -> dict[str, Any]:
    """
    Serie mensual del índice de demanda de un programa + dirección y variación.

    `indice` = share del programa ese mes × 100 (suavizado con media móvil de 3).
    `variacion_pct` compara la media de los últimos 3 meses contra los primeros 3.
    `direccion` ∈ {creciente, estable, decreciente} por banda ±8%.
    """
    paises = paises or [PAIS_DEFECTO]
    demanda_m, periodos = _demanda_por_programa_mensual(TODOS, paises)
    meses = demanda_m.get(programa, {})

    if not meses or len(periodos) < 2:
        return {"serie": [], "direccion": "sin_datos", "variacion_pct": None,
                "n_meses": len(periodos)}

    serie_raw = [meses.get(p, 0.0) * 100 for p in periodos]
    serie_suave = _media_movil(serie_raw, 3)
    serie = [{"periodo": p, "indice": round(v, 3)} for p, v in zip(periodos, serie_suave)]

    # Dirección: regresión lineal ponderada con zona neutra (el mismo clasificador
    # robusto de la página de Tendencias), inmune a picos puntuales del final.
    direccion, _score = calcular_tendencia(serie_suave)

    # Variación %: media de los últimos 3 meses vs. los primeros 3. Solo se reporta
    # si es plausible; si la dispara una base minúscula/pico, se omite (None) y la
    # UI muestra únicamente la dirección.
    k = min(3, len(serie_suave))
    prim = sum(serie_suave[:k]) / k
    ult = sum(serie_suave[-k:]) / k
    variacion_pct = round((ult - prim) / prim * 100, 1) if prim else None

    # Coherencia con la dirección (que es la señal robusta): la variación % solo se
    # reporta cuando acompaña a una dirección creciente/decreciente, con el mismo
    # signo y una magnitud plausible. En "estable" no se muestra número (por
    # definición está dentro de la zona neutra) para no contradecir el veredicto.
    if variacion_pct is None or abs(variacion_pct) > _VARIACION_MAX_FIABLE:
        variacion_pct = None
    elif direccion == "estable":
        variacion_pct = None
    elif (direccion == "creciente" and variacion_pct <= 0) or \
         (direccion == "decreciente" and variacion_pct >= 0):
        variacion_pct = None

    return {"serie": serie, "direccion": direccion,
            "variacion_pct": variacion_pct, "n_meses": len(periodos)}
