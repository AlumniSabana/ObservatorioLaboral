"""
seniority_analisis.py — "¿qué nivel de experiencia conviene más?" por programa.

Para la página "Perfil Ocupacional". Responde con qué seniority tiene el mejor
balance entre ACCESO (cuántas vacantes hay) y PAGO, usando las vacantes de Adzuna
(la única fuente con título + salario por oferta; GEIH no trae seniority y los
rangos SPE son agregados sin título).

Decisiones de diseño (honestas con el dato):
  - El pago se expresa como ÍNDICE relativo entre niveles (mediana global = 100),
    no en COP: Adzuna es mercado internacional, así que el nivel COP no aplica a
    Colombia, pero la RELACIÓN entre niveles sí es informativa.
  - La recomendación NO usa el ratio ingenuo salario/demanda (premiaría siempre al
    senior, mal consejo para un egresado). Usa un score balanceado 50% acceso +
    50% pago, solo entre niveles con muestra suficiente (n>=5), y excluye la bolsa
    "sin especificar" (nivel no declarado en el título, no un nivel real).
  - Guardarraíl de baja muestra: si hay pocas vacantes etiquetadas, la confianza
    es "limitada" y la UI lo advierte en vez de dar un veredicto tajante.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from Adzuna.adzuna_service import fetch_jobs_from_db
from Tendencias.seniority import (
    GRADUADO,
    JUNIOR,
    NO_ESPECIFICADO,
    SENIOR,
    detectar_seniority,
)

# Niveles que entran a la recomendación (excluye NO_ESPECIFICADO = residual).
_NIVELES_REC = (GRADUADO, JUNIOR, SENIOR)

# Etiquetas legibles y orden de menor a mayor experiencia para la UI.
_ETIQUETAS = {
    GRADUADO: "Recién graduado",
    JUNIOR: "Junior",
    NO_ESPECIFICADO: "Sin especificar",
    SENIOR: "Senior / Liderazgo",
}
_ORDEN = [GRADUADO, JUNIOR, NO_ESPECIFICADO, SENIOR]

_MIN_N_NIVEL = 5      # muestra mínima por nivel para poder recomendarlo
_MIN_N_CONFIABLE = 30  # muestra etiquetada total para confianza "alta"


def _punto_medio(job: dict) -> float | None:
    """Punto medio salarial de una vacante, o None si no tiene salario."""
    smin, smax = job.get("salary_min"), job.get("salary_max")
    if smin and smax:
        return (smin + smax) / 2
    return None


def seniority_optimo(programa: str, paises: list[str] | None = None,
                     jobs_programa: list[dict] | None = None) -> dict[str, Any]:
    """
    Distribución de demanda × pago por nivel de experiencia para un programa, con
    la recomendación del nivel con mejor balance. Ver docstring del módulo.

    `jobs_programa`: vacantes Adzuna del programa ya cargadas (las pasa el composer
    para no volver a leer la BD). Si es None, se leen y filtran aquí.
    """
    if jobs_programa is None:
        jobs = [j for j in fetch_jobs_from_db(fuente="adzuna")
                if j.get("programa_relacionado") == programa]
    else:
        jobs = jobs_programa
    total = len(jobs)

    base = {
        "niveles": [],
        "recomendado": None,
        "confianza": "sin_datos",
        "n_total_etiquetadas": 0,
        "n_total": total,
        "fuente": "Adzuna (mercado internacional)",
        "nota_indice": "Índice de pago relativo entre niveles (mediana global = 100).",
    }
    if total == 0:
        return base

    # Agrupar por nivel y calcular la mediana salarial global (para el índice).
    por_nivel: dict[str, list[dict]] = {}
    for j in jobs:
        por_nivel.setdefault(detectar_seniority(j.get("title")), []).append(j)

    sal_global = [pm for j in jobs if (pm := _punto_medio(j)) is not None]
    mediana_global = median(sal_global) if sal_global else None

    niveles = []
    for codigo in _ORDEN:
        js = por_nivel.get(codigo, [])
        if not js:
            continue
        sals = [pm for j in js if (pm := _punto_medio(j)) is not None]
        sal_medio = median(sals) if sals else None
        indice = (round(sal_medio / mediana_global * 100)
                  if sal_medio and mediana_global else None)
        niveles.append({
            "codigo": codigo,
            "etiqueta": _ETIQUETAS[codigo],
            "demanda_pct": round(len(js) / total * 100, 1),
            "n": len(js),
            "salario_indice": indice,
            "n_con_salario": len(sals),
        })

    # Recomendación: score 50% acceso + 50% pago, entre niveles reales con n>=5.
    candidatos = [nv for nv in niveles
                  if nv["codigo"] in _NIVELES_REC and nv["n"] >= _MIN_N_NIVEL
                  and nv["salario_indice"] is not None]
    recomendado = None
    if candidatos:
        max_dem = max(nv["demanda_pct"] for nv in candidatos) or 1
        max_ind = max(nv["salario_indice"] for nv in candidatos) or 1

        def _score(nv: dict) -> float:
            return 0.5 * (nv["demanda_pct"] / max_dem) + 0.5 * (nv["salario_indice"] / max_ind)

        mejor = max(candidatos, key=_score)
        recomendado = {
            "codigo": mejor["codigo"],
            "etiqueta": mejor["etiqueta"],
            "motivo": (f"Concentra el {mejor['demanda_pct']}% de las vacantes con un pago "
                       f"del {mejor['salario_indice']}% del promedio: el mejor balance "
                       f"entre oportunidades y salario."),
        }

    n_etiquetadas = sum(nv["n"] for nv in niveles if nv["codigo"] in _NIVELES_REC)
    base.update({
        "niveles": niveles,
        "recomendado": recomendado,
        "confianza": "alta" if n_etiquetadas >= _MIN_N_CONFIABLE else "limitada",
        "n_total_etiquetadas": n_etiquetadas,
    })
    return base
