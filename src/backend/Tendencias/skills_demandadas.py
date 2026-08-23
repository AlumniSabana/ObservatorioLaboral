"""
Ranking de "skills más demandadas" — competencias y tecnologías.

QUÉ ES (y qué NO es)
--------------------
NO es extracción de skills del texto de las vacantes: Adzuna trunca las
descripciones a 500 caracteres, así que no hay skills que extraer (ver README
§9.7). Las skills OBSERVADAS reales llegarán de Google Jobs, que sí trae texto
completo.

Esto es una vista DERIVADA: cruza dos cosas que sí tenemos,
  1. la demanda real de cada programa académico (share de vacantes, observado en
     Adzuna con fecha de publicación real), y
  2. qué competencias y tecnologías usa cada programa, según O*NET (normativo,
     con un peso de importancia por skill),
para responder: "dado lo que el mercado está pidiendo (mix de ocupaciones), ¿qué
skills concentran más demanda?".

    demanda(skill) = Σ_programa  share(programa) × peso_onet(skill, programa) / 100

POR QUÉ NO HAY TENDENCIA TEMPORAL AQUÍ
--------------------------------------
Se probó y no es fiable: las skills con peso real (Excel, Office, comunicación)
son transversales a casi todos los programas, así que su mezcla agregada es plana
en el tiempo; las únicas que "se mueven" son nicho de un solo programa, con peso
marginal. Forzar una tendencia sería deshonesto. Por eso esta vista es un
RANKING de nivel de demanda, no una serie temporal. La tendencia real de skills
vendrá de observarlas en texto (Google Jobs).

El `share` de cada programa se pondera igual que en tendencias_service: cada
vacante muestreada se reescala por el volumen real de su keyword (post-
estratificación), para que el mix refleje el mercado y no nuestro muestreo.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from ONet.onet_service import (
    PROGRAMAS_ONET,
    competencias_scored,
    homologada_a,
    CATEGORIAS_HOMOLOGADAS_13,
    NOMBRES_TECNICOS_ES,
)
from Tendencias.tendencias_service import (
    FUENTE_DEFECTO,
    PAIS_DEFECTO,
    TODOS,
    leer_observaciones,
)

# Cachés de proceso: se llenan la primera vez y se reusan hasta reiniciar.
# Clave: (seniority, países) — el share depende de qué mercados se combinen.
_cache_demanda: Dict[Any, Dict[str, float]] = {}
_cache_mapa_onet: Dict[str, Any] | None = None

# El mapa O*NET además se persiste en disco: reconstruirlo son ~27 llamadas a su
# API (~38 s) y es data de referencia que cambia pocas veces al año.
CACHE_ONET_PATH = Path(__file__).parent / "_cache_onet.json"


def _mapa_onet() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """{programa: {'competencias': {nombre: {peso, descripcion}}, 'tecnologias': {...}}}.

    Construirlo cuesta ~27 llamadas a la API de O*NET (una por ocupación), unos
    38 s. Como O*NET es data de referencia que cambia pocas veces al año, se
    guarda en disco (`_cache_onet.json`) además de en memoria: así solo la
    primerísima vez se pega a la API, y los reinicios del backend son inmediatos.

    Para forzar su regeneración basta con borrar el archivo.
    """
    global _cache_mapa_onet
    if _cache_mapa_onet is not None:
        return _cache_mapa_onet

    # 1) Caché en disco
    if CACHE_ONET_PATH.exists():
        try:
            with open(CACHE_ONET_PATH, encoding="utf-8") as fh:
                _cache_mapa_onet = json.load(fh)
            return _cache_mapa_onet
        except Exception:
            pass  # caché corrupto: se regenera

    # 2) Construirlo desde la API
    mapa: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for programa in PROGRAMAS_ONET:
        datos = competencias_scored(programa)
        mapa[programa] = {
            "competencias": {
                c["nombre"]: {"peso": c["peso"], "descripcion": c["descripcion"]}
                for c in datos["competencias"]
            },
            "tecnologias": {
                t["nombre"]: {"peso": t["peso"], "descripcion": t["descripcion"]}
                for t in datos["tecnologias"]
            },
        }

    # Solo se persiste si vino con contenido (no cachear un fallo de la API).
    if any(m["competencias"] or m["tecnologias"] for m in mapa.values()):
        try:
            with open(CACHE_ONET_PATH, "w", encoding="utf-8") as fh:
                json.dump(mapa, fh, ensure_ascii=False)
        except Exception:
            pass  # sin disco escribible seguimos con el caché en memoria

    _cache_mapa_onet = mapa
    return mapa


def _obs_programa(pais: str, seniority: str) -> List[Dict[str, Any]]:
    """Observaciones precalculadas de la dimensión interna 'programa'.

    Antes esto se calculaba releyendo las ~61.000 vacantes crudas (y una vez por
    país), lo que costaba más de un minuto. Ahora la demanda por carrera se
    precalcula en `recalcular_todo` como una dimensión más, así que aquí solo se
    leen unas cientos de filas ya agregadas.
    """
    return leer_observaciones("programa", TODOS, seniority, FUENTE_DEFECTO, [pais])


def _demanda_de_un_pais(pais: str, seniority: str) -> Dict[str, float]:
    """{programa: share} DENTRO de un solo mercado (suma 1 entre programas).

    Se agrega sobre todo el periodo: se suman las vacantes estimadas de cada
    carrera y se divide por el total del mercado.
    """
    obs = _obs_programa(pais, seniority)
    if not obs:
        return {}

    acum: Dict[str, float] = defaultdict(float)
    for o in obs:
        acum[o["termino"]] += o["menciones"]

    total = sum(acum.values())
    return {prog: v / total for prog, v in acum.items()} if total else {}


# seniority -> {programa: {periodo: share}}  (desglose mensual del share)
_cache_demanda_mensual: Dict[Any, Any] = {}


def _demanda_mensual_de_un_pais(pais: str, seniority: str):
    """({programa: {periodo: share}}, {periodos}) dentro de un solo mercado.

    Igual que `_demanda_de_un_pais` pero sin colapsar el tiempo. Usa las mismas
    observaciones precalculadas: el `share` de cada fila ya es la cuota de esa
    carrera dentro de su mes.
    """
    obs = _obs_programa(pais, seniority)
    if not obs:
        return {}, set()

    shares: Dict[str, Dict[str, float]] = defaultdict(dict)
    periodos = set()
    for o in obs:
        shares[o["termino"]][o["periodo"]] = o["share"]
        periodos.add(o["periodo"])

    return {prog: dict(meses) for prog, meses in shares.items()}, periodos


def _demanda_por_programa_mensual(seniority: str = TODOS, paises: List[str] | None = None):
    """({programa: {periodo: share}}, [periodos ordenados]).

    Devuelve el share de cada carrera por mes: el share de cada
    programa se calcula mes a mes dentro de cada mercado.

    Al combinar países se promedia igual que en el ranking: cada mes, el share de
    un programa es la media de sus shares en los mercados que tienen datos ESE mes
    (los que no cubren el mes no entran en el denominador). Con un solo país
    devuelve su share tal cual.
    """
    paises = paises or [PAIS_DEFECTO]
    clave = (seniority, tuple(sorted(paises)))
    if clave in _cache_demanda_mensual:
        d = _cache_demanda_mensual[clave]
        return d, sorted({p for prog in d.values() for p in prog})

    por_pais = {}
    periodos_por_pais = {}
    for pais in paises:
        shares, periodos = _demanda_mensual_de_un_pais(pais, seniority)
        por_pais[pais] = shares
        periodos_por_pais[pais] = periodos

    # Cuántos mercados aportan datos en cada mes (denominador de la media).
    paises_por_periodo: Dict[str, int] = defaultdict(int)
    for periodos in periodos_por_pais.values():
        for p in periodos:
            paises_por_periodo[p] += 1

    combinado: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for pais, shares in por_pais.items():
        for prog, meses in shares.items():
            for p, s in meses.items():
                combinado[prog][p] += s / paises_por_periodo[p]

    resultado = {prog: dict(meses) for prog, meses in combinado.items()}
    _cache_demanda_mensual[clave] = resultado
    return resultado, sorted(paises_por_periodo)


def _skill_mes_mercado(clave: str, seniority: str, paises: List[str]):
    """({skill: {periodo: demanda_mercado}}, [periodos]).

    Base ÚNICA del ranking y de la gráfica de evolución, para que ambos listen
    exactamente las mismas skills en el mismo orden. La demanda de una skill en un
    mes es Σ_carrera share(carrera, mes) × peso_onet(skill, carrera)/100 sobre el
    mix completo de carreras (mercado), sin restringir por programa.
    """
    mapa = _mapa_onet()
    demanda_m, periodos = _demanda_por_programa_mensual(seniority, paises)
    skill_mes: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for prog, meses in demanda_m.items():
        for nombre, info in mapa.get(prog, {}).get(clave, {}).items():
            factor = info["peso"] / 100.0
            for periodo, share in meses.items():
                skill_mes[nombre][periodo] += share * factor
    return skill_mes, sorted(periodos)


def _descripcion_skill(mapa: Dict[str, Any], clave: str, skill: str) -> str:
    """Descripción O*NET de una skill (la misma en cualquier ocupación que la use)."""
    for prog in mapa.values():
        info = prog.get(clave, {}).get(skill)
        if info:
            return info["descripcion"]
    return ""


def _cuantos_programas(mapa: Dict[str, Any], clave: str, skill: str) -> int:
    """En cuántas ocupaciones/carreras aparece la skill (su transversalidad)."""
    return sum(1 for prog in mapa.values() if skill in prog.get(clave, {}))


def _media_movil(serie: List[float], ventana: int = 3) -> List[float]:
    """Suaviza la serie con una media móvil centrada, para atenuar el ruido de
    muestreo mensual (cada mes se muestrean ~50 vacantes/keyword, así que el share
    mensual de un programa fluctúa bastante y esos picos no son señal real)."""
    n = len(serie)
    if n < ventana:
        return serie
    out = []
    r = ventana // 2
    for i in range(n):
        lo, hi = max(0, i - r), min(n, i + r + 1)
        out.append(sum(serie[lo:hi]) / (hi - lo))
    return out


def _pendiente_normalizada(serie: List[float]) -> float:
    """Pendiente de la serie relativa a su propia media (regresión ponderada).

    Misma fórmula que `tendencias_service.calcular_tendencia`, pero devolviendo
    el valor crudo en vez de la etiqueta: aquí las skills se ordenan entre sí,
    no se clasifican contra un umbral fijo (ver `_kpis_movimiento`).
    """
    n = len(serie)
    if n < 2:
        return 0.0
    x = list(range(n))
    w = [xi + 1 for xi in x]
    sw = sum(w)
    swx = sum(wi * xi for wi, xi in zip(w, x))
    swy = sum(wi * yi for wi, yi in zip(w, serie))
    swxx = sum(wi * xi * xi for wi, xi in zip(w, x))
    swxy = sum(wi * xi * yi for wi, xi, yi in zip(w, x, serie))
    den = sw * swxx - swx**2
    if den == 0:
        return 0.0
    pendiente = (sw * swxy - swx * swy) / den
    media = sum(serie) / n
    return pendiente / media if media else 0.0


def _kpis_movimiento(
    series: List[Dict[str, Any]],
    demanda: Dict[str, float] | None = None,
    top: int = 5,
    umbral: float | None = None,
    umbral_baja: float | None = None,
    umbral_sube: float | None = None,
) -> Dict[str, Any]:
    """Skills que MÁS suben y MÁS bajan dentro del periodo analizado.

    Es un ranking COMPARATIVO, no una clasificación absoluta como la de cargos.
    El motivo es de escala: la demanda de una skill es un promedio sobre muchos
    programas, así que se suaviza por construcción y sus pendientes son ~4x más
    pequeñas que las de un cargo. Con el umbral fijo de tendencias (±0.08) TODAS
    saldrían "estables" por artefacto matemático, no porque no se muevan.

    Por eso aquí no se afirma "esta skill crece", sino "estas son las que más han
    subido/bajado" — que es lo que los datos sí sostienen. La UI lo etiqueta así.

    Se DEDUPLICAN las pendientes idénticas: las skills que solo pertenecen a una
    misma carrera siguen exactamente su curva, así que aparecerían repetidas
    diciendo lo mismo (cuatro programas de fisioterapia con la misma pendiente).
    De cada grupo se conserva la de mayor demanda.
    """
    demanda = demanda or {}
    movimientos = [
        {
            "nombre": s["nombre"],
            "pendiente": round(_pendiente_normalizada(s["valores"]), 5),
            "_demanda": demanda.get(s["nombre"], 0.0),
        }
        for s in series
    ]

    # ZONA NEUTRA. Sin ella, clasificar por el mero signo marca como "en declive"
    # a competencias que están planas: 'Escucha activa' con pendiente -0.0029 no
    # está cayendo, es ruido alrededor de cero. Como la magnitud depende de la
    # dimensión (las tecnologías se mueven mucho más que las competencias, que son
    # transversales), el umbral se deriva de la dispersión observada.
    #
    # IMPORTANTE: se recibe calculado sobre TODO el mercado, no sobre el
    # subconjunto filtrado. Si se midiera dentro del propio subconjunto, siempre
    # habría "emergentes" y "en declive" aunque todas estuvieran planas —forzando
    # un ranking donde no hay señal—. Midiendo contra el mercado, un programa
    # cuyas skills no destacan sale correctamente con todo estable.
    if umbral is None:
        magnitudes = sorted(abs(m["pendiente"]) for m in movimientos)
        umbral = magnitudes[len(magnitudes) // 2] if magnitudes else 0.0

    # Zona neutra ASIMÉTRICA: pedido explícito (13 ago 2026) — más fácil marcar
    # una competencia "en declive" (umbral más bajo) y más difícil marcar
    # "emergente" (umbral más alto), en vez del mismo umbral para ambos lados.
    umbral_baja = umbral if umbral_baja is None else umbral_baja
    umbral_sube = umbral if umbral_sube is None else umbral_sube

    def top_unicos(candidatos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        vistos: set = set()
        salida = []
        for m in candidatos:
            if m["pendiente"] in vistos:
                continue  # misma señal que una ya listada
            vistos.add(m["pendiente"])
            salida.append({"nombre": m["nombre"], "pendiente": m["pendiente"]})
            if len(salida) >= top:
                break
        return salida

    # Orden: por movimiento y, a igualdad, la más demandada primero.
    suben = sorted(
        (m for m in movimientos if m["pendiente"] > umbral_sube),
        key=lambda m: (-m["pendiente"], -m["_demanda"]),
    )
    bajan = sorted(
        (m for m in movimientos if m["pendiente"] < -umbral_baja),
        key=lambda m: (m["pendiente"], -m["_demanda"]),
    )
    return {
        "modo": "skills",
        "emergentes": {"total": len(suben), "top": top_unicos(suben)},
        "en_declive": {"total": len(bajan), "top": top_unicos(bajan)},
        "estables": len(movimientos) - len(suben) - len(bajan),
        "analizadas": len(movimientos),
    }


def evolucion_skills(
    tipo: str = "tecnologia",
    programa: str = TODOS,
    seniority: str = TODOS,
    top: int = 8,
    paises: List[str] | None = None,
) -> Dict[str, Any]:
    """Serie temporal de la demanda de MERCADO de las `top` skills más demandadas.

    La serie de cada skill es su demanda en el mercado completo (mix de todas las
    carreras), así que cada una se mueve de forma distinta.

    Al filtrar por un programa solo se restringe QUÉ skills se listan —las que esa
    carrera usa—, pero cada una conserva su curva de mercado. (Antes, con un
    programa, se proyectaba la demanda de la carrera sobre el peso O*NET, que es
    plano dentro de una ocupación, así que las líneas salían idénticas y
    superpuestas; por eso ese enfoque se abandonó.)

    La serie va suavizada con media móvil de 3 meses y escalada ×100 para
    legibilidad ("índice de demanda"). Coincide con el ranking de `skills_demandadas`.
    """
    if tipo not in ("competencia", "tecnologia"):
        raise ValueError("tipo debe ser 'competencia' o 'tecnologia'")

    paises = paises or [PAIS_DEFECTO]
    clave = "competencias" if tipo == "competencia" else "tecnologias"
    mapa = _mapa_onet()

    # Misma base que el ranking (`_skill_mes_mercado`): demanda de mercado de cada
    # skill mes a mes. Así el ranking y la gráfica listan las mismas skills en el
    # mismo orden. Al filtrar por programa solo se restringe QUÉ skills se listan.
    skill_mes_kpi, periodos = _skill_mes_mercado(clave, seniority, paises)
    if not periodos:
        return {
            "tipo": tipo,
            "programa": programa,
            "seniority": seniority,
            "paises": paises,
            "periodos": [],
            "series": [],
            "sin_datos": True,
        }

    skills_del_programa = (
        set(mapa.get(programa, {}).get(clave, {})) if programa != TODOS else None
    )

    # --- KPIs de movimiento y dibujo, ambos sobre la demanda de mercado ------
    prom_kpi = {
        s: sum(m.get(p, 0) for p in periodos) / len(periodos) for s, m in skill_mes_kpi.items()
    }
    serie_kpi_de = lambda s: [  # noqa: E731
        round(v * 100, 3) for v in _media_movil([skill_mes_kpi[s].get(p, 0) for p in periodos])
    ]
    # Se descarta la cola marginal: una skill con demanda ínfima puede tener una
    # pendiente enorme sin significar nada. p25, igual criterio que en tendencias.
    valores_todos = sorted(prom_kpi.values())
    corte_kpi = valores_todos[len(valores_todos) // 4] if len(valores_todos) >= 4 else 0.0
    relevantes_mercado = [s for s in prom_kpi if prom_kpi[s] >= corte_kpi]

    # Umbral de la zona neutra medido sobre TODO el mercado (ver _kpis_movimiento).
    magnitudes = sorted(
        abs(_pendiente_normalizada(serie_kpi_de(s))) for s in relevantes_mercado
    )
    umbral_mercado = magnitudes[len(magnitudes) // 2] if magnitudes else 0.0

    # Al filtrar por programa solo se restringe QUÉ skills se listan. Las
    # técnicas (Programación, Ciencia, Matemáticas...) SÍ entraron en
    # `umbral_mercado` de arriba —le dan la volatilidad que evita que todo
    # salga "estable" (ver competencias_scored)— pero no se nombran aquí: no
    # son competencias blandas, igual que en el ranking de más arriba.
    es_competencia = tipo == "competencia"
    relevantes_kpi = [
        s
        for s in relevantes_mercado
        if (skills_del_programa is None or s in skills_del_programa)
        and not (es_competencia and s in NOMBRES_TECNICOS_ES)
    ]
    # Asimetría pedida solo para COMPETENCIAS (no tecnologías): más fácil marcar
    # "en declive" (umbral 25% más bajo) y más difícil marcar "emergente"
    # (umbral 25% más alto) que el punto medio simétrico de siempre. Si hace
    # falta más o menos sensibilidad, ajustar estos dos factores.
    FACTOR_UMBRAL_BAJA = 0.75
    FACTOR_UMBRAL_SUBE = 1.25
    kpis = _kpis_movimiento(
        [{"nombre": s, "valores": serie_kpi_de(s)} for s in relevantes_kpi],
        prom_kpi,
        umbral=umbral_mercado,
        umbral_baja=umbral_mercado * FACTOR_UMBRAL_BAJA if es_competencia else None,
        umbral_sube=umbral_mercado * FACTOR_UMBRAL_SUBE if es_competencia else None,
    )

    # Para dibujar: las más demandadas por DEMANDA DE MERCADO (mismo criterio que
    # el ranking y los KPIs), respetando el programa. Antes, con un programa, se
    # usaba la serie de la carrera × peso O*NET plano, así que las líneas salían
    # IDÉNTICAS y superpuestas (las 25 tecnologías de Ing. Informática pesan 70).
    # Con la serie de mercado cada skill tiene su propia curva y coincide con lo
    # que muestra el ranking.
    candidatas_dibujo = [
        s
        for s in prom_kpi
        if (skills_del_programa is None or s in skills_del_programa)
        and not (es_competencia and s in NOMBRES_TECNICOS_ES)
    ]

    # GARANTÍA DE LAS 13: en competencias, se asegura que aparezca al menos una
    # línea por cada categoría homologada que tenga algún constituyente con
    # datos — la de mayor demanda de esa categoría—, antes de completar con las
    # demás por demanda normal. Pedido explícito: "que en la barra de tendencias
    # aparezcan las 13 con las que están homologadas y otras más" (12 ago 2026).
    # No todas las 13 tienen skill de O*NET asignada (ver HOMOLOGACION_13): solo
    # se puede garantizar cobertura de las que sí.
    representantes: List[str] = []
    if es_competencia:
        for categoria in CATEGORIAS_HOMOLOGADAS_13:
            miembros = [s for s in candidatas_dibujo if homologada_a(s) == categoria]
            if miembros:
                representantes.append(max(miembros, key=lambda s: prom_kpi[s]))

    # Mismo orden que el ranking (valor crudo, desempate alfabético) para el
    # resto; los representantes van primero y no se duplican.
    resto = sorted(
        (s for s in candidatas_dibujo if s not in representantes),
        key=lambda s: (-prom_kpi[s], s),
    )
    elegidas = representantes + resto[: max(0, top - len(representantes))]
    series = [{"nombre": s, "valores": serie_kpi_de(s)} for s in elegidas]

    return {
        "tipo": tipo,
        "programa": programa,
        "seniority": seniority,
        "paises": paises,
        "periodos": periodos,
        "series": series,
        "suavizado": "media_movil_3m",
        # Skills que más suben / más bajan (ranking comparativo, ver _kpis_movimiento).
        "kpis": kpis,
        "sin_datos": not series,
    }


def skills_demandadas(
    tipo: str = "tecnologia",
    programa: str = TODOS,
    seniority: str = TODOS,
    top: int = 25,
    paises: List[str] | None = None,
) -> Dict[str, Any]:
    """Ranking de skills demandadas.

    tipo='competencia' -> competencias O*NET (transversales, blandas/cognitivas)
    tipo='tecnologia'  -> herramientas y tecnologías (Excel, SAP, Python…)

    Con `programa` != TODOS el ranking es el de esa carrera (share = 1, así que
    refleja el peso O*NET puro de esa ocupación) y `paises` no influye: las
    competencias O*NET de una ocupación no dependen del mercado.

    Con TODOS los programas se pondera por la demanda real de cada carrera,
    combinando los `paises` seleccionados con el mismo criterio que las
    tendencias: se promedia el share de cada mercado (cada país pesa igual).
    """
    if tipo not in ("competencia", "tecnologia"):
        raise ValueError("tipo debe ser 'competencia' o 'tecnologia'")

    paises = paises or [PAIS_DEFECTO]
    clave = "competencias" if tipo == "competencia" else "tecnologias"
    mapa = _mapa_onet()

    # El índice se calcula SIEMPRE sobre la demanda de MERCADO (mix de todas las
    # carreras). Antes, al filtrar por un programa se usaba `{programa: 1.0}`, y
    # como O*NET da a casi todas las tecnologías de una ocupación el mismo peso
    # (25 herramientas de Ing. Informática, todas con 70), salían empatadas a 100.
    # Con la demanda de mercado sí se diferencian: una skill vale por cuántas
    # carreras demandadas la usan, no por un peso O*NET plano.
    #
    # Se usa la MISMA base que la gráfica de evolución (`_skill_mes_mercado`) para
    # que el ranking y la gráfica listen exactamente las mismas skills en el mismo
    # orden. El índice de una skill es su demanda media a lo largo del periodo.
    skill_mes, periodos = _skill_mes_mercado(clave, seniority, paises)
    skills_del_programa = (
        set(mapa.get(programa, {}).get(clave, {})) if programa != TODOS else None
    )

    acum: Dict[str, float] = {}
    desc: Dict[str, str] = {}
    progs: Dict[str, int] = {}
    n_periodos = len(periodos) or 1
    for skill, meses in skill_mes.items():
        if skills_del_programa is not None and skill not in skills_del_programa:
            continue
        # Las técnicas de O*NET (Programación, Ciencia, Matemáticas...) siguen
        # sumando en `skill_mes` (le dan volatilidad real al KPI de tendencia,
        # ver comentario en competencias_scored), pero NO se muestran aquí como
        # si fueran una competencia blanda — es justo el feedback del 12 ago
        # 2026 ("Ciencia sigue apareciendo como competencia").
        if tipo == "competencia" and skill in NOMBRES_TECNICOS_ES:
            continue
        acum[skill] = sum(meses.values()) / n_periodos
        desc[skill] = _descripcion_skill(mapa, clave, skill)
        progs[skill] = _cuantos_programas(mapa, clave, skill)

    if not acum:
        return {
            "tipo": tipo,
            "programa": programa,
            "seniority": seniority,
            "paises": paises,
            "items": [],
            "sin_datos": True,
        }

    maximo = max(acum.values()) or 1.0
    # Orden por el valor CRUDO (no el índice redondeado) con desempate alfabético,
    # el mismo criterio que la gráfica de evolución, para que ambos listen las
    # skills en idéntico orden incluso cuando dos empatan al redondear.
    items = [
        {
            "nombre": nombre,
            "descripcion": desc[nombre],
            # Normalizado a 0-100 respecto al líder: es un índice de demanda
            # relativa, legible, no un porcentaje de vacantes.
            "indice": round(acum[nombre] / maximo * 100, 1),
            "n_programas": progs[nombre],
            # Categoría de las 13 homologadas (Monitoreo entorno 2025) a la que
            # pertenece esta competencia, o None si no es homologable. Solo
            # aplica a tipo='competencia' (las tecnologías no se homologaron).
            "homologada": homologada_a(nombre) if tipo == "competencia" else None,
        }
        for nombre in sorted(acum, key=lambda s: (-acum[s], s))
    ]

    return {
        "tipo": tipo,
        "programa": programa,
        "seniority": seniority,
        "paises": paises,
        "items": items[:top],
        "sin_datos": False,
    }


def limpiar_cache(incluir_onet: bool = False) -> None:
    """Invalida los cachés de demanda. Llamar tras un backfill/recálculo.

    NO toca el mapa O*NET por defecto: lo que cambia con un recálculo es la
    demanda del mercado, no las competencias que O*NET asigna a cada ocupación
    (y reconstruirlo cuesta ~27 llamadas a su API). Usa `incluir_onet=True` solo
    si quieres forzar que se vuelva a descargar.
    """
    global _cache_mapa_onet
    _cache_demanda.clear()
    _cache_demanda_mensual.clear()
    if incluir_onet:
        _cache_mapa_onet = None
        CACHE_ONET_PATH.unlink(missing_ok=True)
