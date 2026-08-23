"""
perfil_service.py — compone el "Perfil Ocupacional" de un programa académico.

Casi todo el dato ya existe repartido en otros servicios; este módulo lo REÚNE en
un único JSON que consumen la página y el reporte PDF, y calcula unos pocos
derivados (salario vs. nacional, nivel educativo que más paga).

Fuentes que compone:
  - Salarios/salarios_service   → salario COP por programa + por nivel educativo.
  - ONet/onet_service           → competencias/tecnologías con peso + perfil O*NET
                                  (RIASEC, job zone, descripción).
  - Tendencias/seniority_analisis → qué seniority conviene más.
  - Tendencias/perfil_tendencia   → tendencia de demanda observada.
  - Adzuna/get_analytics          → sectores que contratan (mercado internacional).
  - GoogleJobs/get_analytics_google → ciudades que contratan (Colombia).
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Any

from Salarios.salarios_service import salario_por_programa
from ONet.onet_service import competencias_scored, perfil_onet
from Tendencias.seniority_analisis import seniority_optimo
from Tendencias.perfil_tendencia import tendencia_programa
from traducciones import traducir_sector


def _sectores(jobs_programa: list[dict]) -> list[dict]:
    """
    Top sectores que contratan el perfil, contados directo de las vacantes ya
    cargadas (Adzuna, mercado internacional). El sector se traduce al vuelo porque
    en la BD viene en inglés. Evita una segunda lectura completa vía get_analytics.
    """
    conteo = Counter()
    for j in jobs_programa:
        cat = traducir_sector(j.get("category")) or "Sin especificar"
        conteo[cat] += 1
    return [{"category": c, "count": n} for c, n in conteo.most_common(6)]


def _ciudades_colombia(programa: str) -> list[dict]:
    """
    Top ciudades que contratan el perfil en Colombia (Google Jobs + LinkedIn).

    Se combinan las dos porque ambas tienen el mismo campo (`city`) y el mismo
    filtro (`programa_relacionado`) — a diferencia de sector o skills, donde
    LinkedIn no aporta nada. Sumar sus conteos da una foto más completa del
    mercado colombiano sin arriesgar nada: es una unión de conteos por ciudad,
    no una serie temporal donde mezclar fuentes distintas pudiera sesgar una
    tendencia (ver Tendencias/linkedin_sync.py para ese caso, que sí es delicado).

    NORMALIZACIÓN DE TILDES: cada fuente escribe la misma ciudad distinto
    ("Bogotá" en una, "Bogota" sin tilde en otra), y sin normalizar contaban
    como ciudades separadas — se vio en producción con datos reales. Se agrupa
    por una clave sin tildes/mayúsculas, pero se MUESTRA la grafía más
    frecuente entre las fuentes (no una forma canónica inventada), para no
    imponer una ortografía que ninguna fuente usó realmente.
    """
    # clave normalizada -> (Counter de grafías originales -> cuántas veces
    # apareció cada una, conteo total de vacantes)
    normalizadas: dict[str, tuple[Counter[str], int]] = {}

    def _sumar(ciudad_cruda: str, peso: int) -> None:
        clave = _normalizar_texto(ciudad_cruda)
        if not clave:
            return
        grafias, total = normalizadas.get(clave, (Counter(), 0))
        # Ponderado por `peso`, no por nº de filas: Google Jobs llega ya
        # agregado (1 fila, count=57) y LinkedIn en crudo (19 filas, 1 c/u).
        # Contar filas haría ganar a la grafía con más filas aunque pese
        # menos en vacantes reales — ya pasó: "Bogota" sin tilde ganaba con
        # 19 filas de LinkedIn frente a la única fila "Bogotá" (57) de
        # Google Jobs, pese a representar menos de un tercio del volumen.
        grafias[ciudad_cruda] += peso
        normalizadas[clave] = (grafias, total + peso)

    try:
        from GoogleJobs.google_jobs_service import get_analytics_google
        g = get_analytics_google(filtros={"programa": programa})
        for c in g.get("cities") or []:
            if c.get("city"):
                _sumar(c["city"], c.get("count", 0))
    except Exception:
        pass

    try:
        from LinkedIn.linkedin_service import leer_ofertas_linkedin
        for oferta in leer_ofertas_linkedin():
            if oferta.get("programa_relacionado") != programa:
                continue
            ciudad = oferta.get("city")
            if ciudad:
                _sumar(ciudad, 1)
    except Exception:
        pass

    salida = [
        {"city": grafias.most_common(1)[0][0], "count": total}
        for grafias, total in normalizadas.values()
    ]
    salida.sort(key=lambda x: -x["count"])
    return salida[:6]


def _normalizar_texto(s: str) -> str:
    """Sin tildes ni mayúsculas, para agrupar variantes de escritura de un mismo
    nombre ('Bogotá' / 'Bogota' / 'BOGOTÁ' deben contar como la misma ciudad)."""
    return unicodedata.normalize("NFKD", s.strip().lower()).encode("ascii", "ignore").decode()


def _nivel_top_paga(niveles_edu: list[dict]) -> dict | None:
    """Nivel educativo con mayor mediana y su incremento vs. el pregrado (base)."""
    if not niveles_edu:
        return None
    top = max(niveles_edu, key=lambda x: x["mediana"])
    # Base = nivel universitario de pregrado (el de menor 'orden' entre los >=10).
    base_cands = [n for n in niveles_edu if n.get("orden", 0) >= 10]
    base = min(base_cands, key=lambda x: x["orden"]) if base_cands else None
    inc = None
    if base and base.get("mediana"):
        inc = round((top["mediana"] / base["mediana"] - 1) * 100, 1)
    return {
        "nombre": top["nombre"],
        "mediana": top["mediana"],
        "incremento_vs_pregrado_pct": inc,
    }


def construir_perfil_ocupacional(programa: str, paises: list[str] | None = None) -> dict[str, Any]:
    """Reúne todas las piezas del perfil ocupacional de un programa (ver módulo)."""
    # Vacantes Adzuna del programa: se leen UNA vez y se reutilizan para seniority
    # y sectores (antes eran dos lecturas completas de ~7k filas → 17 s).
    from Adzuna.adzuna_service import fetch_jobs_from_db
    jobs_programa = [j for j in fetch_jobs_from_db(fuente="adzuna")
                     if j.get("programa_relacionado") == programa]

    salario = salario_por_programa(programa)
    skills = competencias_scored(programa)
    onet = perfil_onet(programa)
    seniority = seniority_optimo(programa, paises, jobs_programa=jobs_programa)
    tendencia = tendencia_programa(programa, paises)

    kpis = salario.get("kpis")
    meta_sal = salario.get("meta", {})
    mediana_nac = meta_sal.get("mediana_nacional")
    vs_nacional_pct = None
    if kpis and mediana_nac:
        vs_nacional_pct = round((kpis["mediana"] / mediana_nac - 1) * 100, 1)

    niveles_edu = salario.get("nivel_educativo") or []

    # Habilidades técnicas de O*NET (Programación, Ciencia, Matemáticas...) que
    # NO deben mostrarse como "Competencias clave" de la ocupación — se mueven a
    # tecnologías SOLO en esta vista por programa. El pool de mercado que usa
    # Competencias/skills_demandadas.py se deja intacto a propósito: ver la nota
    # en ONet/onet_service.competencias_scored.
    tecnicas = set(skills.get("competencias_tecnicas", []))
    competencias_todas = skills.get("competencias", [])
    tecnologias_todas = skills.get("tecnologias", []) + [
        c for c in competencias_todas if c["nombre"] in tecnicas
    ]
    competencias_todas = [c for c in competencias_todas if c["nombre"] not in tecnicas]

    # Ordenar competencias y tecnologías por peso (las más importantes primero).
    competencias = sorted(competencias_todas, key=lambda s: -s.get("peso", 0))[:10]
    tecnologias = sorted(tecnologias_todas, key=lambda s: -s.get("peso", 0))[:12]

    encontrado = bool(kpis) or bool(competencias) or bool(onet.get("riasec"))

    # CNO 2025 (SENA): lo mismo que O*NET pero con la taxonomía colombiana y ya en
    # español. Si la migración 009 no corrió, `sin_datos` y la sección no se pinta.
    cno_sena: dict = {"sin_datos": True}
    try:
        from SENA.sena_service import skills_de_programa
        hab = skills_de_programa(programa, "habilidad")
        con = skills_de_programa(programa, "conocimiento")
        if not hab.get("sin_datos") or not con.get("sin_datos"):
            cno_sena = {
                "sin_datos": False,
                "ocupacion": hab.get("ocupacion") or con.get("ocupacion"),
                "habilidades": hab.get("items", []),
                "conocimientos": con.get("items", []),
            }
    except Exception:
        pass

    return {
        "programa": programa,
        "encontrado": encontrado,
        "onet": onet,
        "salario": {
            "cno": salario.get("cno"),
            "kpis": kpis,
            "vs_nacional_pct": vs_nacional_pct,
            "mediana_nacional": mediana_nac,
            "rango_spe": salario.get("rango_spe"),
            "spe_rangos": salario.get("spe_rangos", []),
            "nivel_educativo": niveles_edu,
            "nivel_educativo_nacional": salario.get("nivel_educativo_nacional", False),
            "nivel_top_paga": _nivel_top_paga(niveles_edu),
        },
        "skills": {"competencias": competencias, "tecnologias": tecnologias},
        "cno_sena": cno_sena,
        "seniority": seniority,
        "tendencia": tendencia,
        "sectores": _sectores(jobs_programa),
        "ciudades_colombia": _ciudades_colombia(programa),
        "meta": {"fuentes": (["O*NET", "GEIH-DANE", "SPE", "Adzuna", "Google Jobs", "LinkedIn"]
                             + ([] if cno_sena["sin_datos"] else ["CNO 2025 - SENA"]))},
    }
