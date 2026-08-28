"""
Motor de tendencias temporales.

Portado de `build_tendencias.py` (proyecto Reto-Alumni) y generalizado: allá
operaba sobre *skills*; aquí opera sobre un "término" cualquiera, de modo que
la misma lógica sirve para varias dimensiones:

    dimension='cargo'   -> títulos normalizados ('software engineer', ...)
    dimension='sector'  -> categorías de Adzuna ('IT Jobs', 'Legal Jobs', ...)
    dimension='skill'   -> reservado: requiere una fuente con texto completo
                           (Adzuna trunca las descripciones a 500 caracteres,
                           así que no da señal de skills). Ver skills_extractor.

MÉTRICA: `share`, no menciones absolutas
----------------------------------------
Cada mes se muestrea con un número distinto de vacantes, así que los conteos
crudos no son comparables. Se usa la proporción del mes:

    share(término, mes) = vacantes del mes con ese término / vacantes del mes

Un mes en el que el término no aparece cuenta como share = 0 (no como dato
faltante): omitirlo sesgaría la pendiente hacia arriba.

CÁLCULO DE LA TENDENCIA
-----------------------
Regresión lineal ponderada sobre la serie de shares, dando más peso a los meses
recientes (peso = posición + 1). La pendiente se normaliza contra la media
SIMPLE para que sea comparable entre términos de distinta magnitud (normalizar
contra la media ponderada, como hacía Reto-Alumni, rompía la simetría: una
subida y su bajada espejo se clasificaban distinto), y se clasifica con un
umbral simétrico:

    pendiente_norm >  0.08  -> creciente
    pendiente_norm < -0.08  -> decreciente
    en otro caso            -> estable
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from statistics import quantiles
from typing import Any, Dict, List, Tuple

from Adzuna.adzuna_service import normalize_title, supabase
from Tendencias.escolaridad import NIVELES as NIVELES_ESCOLARIDAD
from Tendencias.seniority import NIVELES, detectar_seniority
from config import es_pertinente, coincide_con_keyword
from traducciones import traducir_sector, traducir_cargo

TABLA_OBS = "tendencias_observaciones"

# Valor centinela para "sin filtrar". Se guarda como una combinación más, de modo
# que el frontend siempre lee la misma tabla con la misma consulta.
TODOS = "TODOS"

# Fuentes de datos conocidas. Cada tendencia se guarda con su (fuente, pais); hoy
# solo Adzuna alimenta el histórico. `opciones_disponibles` solo ofrece las que de
# verdad tienen datos, así que añadir aquí una fuente futura (p. ej. Google Jobs)
# no la muestra hasta que exista muestra suya.
FUENTES_CATALOGO = [
    {"fuente": "adzuna", "pais": "us", "label": "Adzuna — Estados Unidos"},
    {"fuente": "adzuna", "pais": "gb", "label": "Adzuna — Reino Unido"},
    {"fuente": "adzuna", "pais": "ca", "label": "Adzuna — Canadá"},
    {"fuente": "adzuna", "pais": "mx", "label": "Adzuna — México"},
    {"fuente": "adzuna", "pais": "es", "label": "Adzuna — España"},
    {"fuente": "google_jobs", "pais": "co", "label": "Google Jobs — Colombia"},
    # pais='co_li' (no 'co'): Colombia ya la cubre Google Jobs y la lectura
    # multi-país combina ignorando `fuente` — ver Tendencias/linkedin_sync.py.
    {"fuente": "linkedin", "pais": "co_li", "label": "LinkedIn — Colombia"},
]
FUENTE_DEFECTO = "adzuna"
PAIS_DEFECTO = "us"


def fuente_de_pais(pais: str) -> str:
    """Fuente que alimenta ese mercado ('co' -> google_jobs, el resto -> adzuna).

    Cada país lo cubre una sola fuente, así que basta el país para saber de dónde
    salen sus datos. Evita cablear 'adzuna' en las consultas y perder los mercados
    de otras fuentes.
    """
    for f in FUENTES_CATALOGO:
        if f["pais"] == pais:
            return f["fuente"]
    return FUENTE_DEFECTO

# Umbral de clasificación (mismo valor que en Reto-Alumni).
UMBRAL = 0.08

# Filtros de calidad: sin ellos, términos vistos 2 veces producen tendencias
# espectaculares y sin sentido. Todos operan sobre la MUESTRA CRUDA, nunca sobre
# las cifras ponderadas (un peso alto convertiría una vacante suelta en "señal").
MIN_VACANTES_MES = 25    # un mes con menos vacantes muestreadas no es representativo
MIN_PERIODOS = 3         # se necesitan >=3 meses válidos para hablar de tendencia
MIN_MUESTRA_TOTAL = 15   # el término debe aparecer en >=15 vacantes reales en total


# ---------------------------------------------------------------------------
# 1. Agregación: muestra cruda -> observaciones (término, mes, share)
# ---------------------------------------------------------------------------

def _periodo(created_at: str) -> str:
    """'2026-06-05T07:14:43+00:00' -> '2026-06-01' (primer día del mes)."""
    return f"{str(created_at)[:7]}-01"


def _terminos(fila: Dict[str, Any], dimension: str) -> List[str]:
    """Términos que aporta una vacante en esa dimensión.

    'cargo' y 'sector' dan como mucho UNO; 'skill' da VARIOS (una vacante pide
    varias competencias/herramientas), y cada uno cuenta como una observación.

    Las skills vienen ya extraídas del texto en la columna `skills` — solo las
    fuentes con descripción completa las traen (Google Jobs sí; Adzuna no, porque
    trunca a 500 caracteres, ver README §9.7).
    """
    if dimension == "cargo":
        # Se traduce el cargo a español (identidad canónica): así las variantes
        # ruidosas de EE.UU. se fusionan bajo un mismo rol durante la agregación.
        t = traducir_cargo(normalize_title(fila.get("title") or ""))
        return [t] if t else []
    if dimension == "sector":
        c = traducir_sector(fila.get("category"))
        return [c] if c else []
    if dimension == "skill":
        skills = fila.get("skills")
        return [s for s in skills if s] if isinstance(skills, list) else []
    if dimension == "programa":
        # Dimensión interna: precalcula la demanda de cada carrera para que
        # `skills_demandadas` no tenga que releer las ~61k vacantes crudas.
        p = fila.get("programa_relacionado")
        return [p] if p else []
    raise ValueError(f"Dimensión no soportada: {dimension}")


def agregar_observaciones(
    filas: List[Dict[str, Any]],
    dimension: str,
    volumenes: List[Dict[str, Any]] | None = None,
    programa: str = TODOS,
    seniority: str = TODOS,
    fuente: str = FUENTE_DEFECTO,
    pais: str = PAIS_DEFECTO,
) -> List[Dict[str, Any]]:
    """Convierte la muestra cruda en filas de `tendencias_observaciones`.

    PONDERACIÓN (post-estratificación)
    ----------------------------------
    La muestra está balanceada por construcción: el recolector pide ~50 vacantes
    por keyword y por mes, así que 'chef' pesa lo mismo que 'software engineer'
    aunque el mercado publique 100x más de este último. Si se contara la muestra
    en crudo, el reparto por sector sería el de nuestras keywords, no el del
    mercado, y todo saldría "estable".

    Por eso cada vacante muestreada se pondera con:

        peso = volumen_real(keyword, mes) / muestreadas(keyword, mes)

    de modo que las 50 vacantes de 'software engineer' representen las ~66.000
    que de verdad se publicaron ese mes. `volumen_real` sale del campo `count`
    de la API (ver historical_collector._volumenes_de_counts).

    Si no hay volúmenes (o la keyword no aparece en ellos) el peso es 1: se
    degrada al conteo crudo en vez de descartar la fila.

    `programa` y `seniority` solo se estampan en la salida: el filtrado de `filas`
    lo hace quien llama. El peso se calcula siempre contra la muestra COMPLETA de
    la keyword (no contra el subconjunto filtrado), porque cada vacante
    muestreada representa `volumen / muestreadas_totales` vacantes del mercado
    independientemente de por qué la hayamos seleccionado.
    """
    # (keyword, periodo) -> peso de cada vacante muestreada
    peso: Dict[Tuple[str, str], float] = {}
    for v in volumenes or []:
        n = v.get("n_muestreadas") or 0
        if n > 0:
            peso[(v["keyword"], str(v["periodo"]))] = v["volumen"] / n

    # periodo -> total ponderado (denominador del share)
    total_por_periodo: Dict[str, float] = defaultdict(float)
    # periodo -> vacantes realmente muestreadas (control de representatividad)
    muestra_por_periodo: Dict[str, int] = defaultdict(int)
    # (periodo, término) -> peso acumulado
    acumulado: Dict[Tuple[str, str], float] = defaultdict(float)
    # (periodo, término) -> vacantes crudas muestreadas (soporte real)
    crudo: Dict[Tuple[str, str], int] = defaultdict(int)

    for fila in filas:
        if not fila.get("created_at"):
            continue
        # El backfill de Adzuna pide sort_direction=up (más antiguas primero,
        # para poder muestrear meses pasados), lo que desactiva el orden por
        # relevancia de la API: para keywords amplias de 1-2 palabras, la
        # mayoría de lo que vuelve no tiene relación real con lo buscado
        # (verificado: "organizational development" trajo 0% de títulos
        # relevantes). Se descarta toda la fila, no solo el término de cargo,
        # porque si el título no coincide con lo buscado tampoco es fiable su
        # sector ni sus skills. Ver coincide_con_keyword() en config.py.
        if not coincide_con_keyword(fila.get("keyword"), fila.get("title")):
            continue
        p = _periodo(fila["created_at"])
        w = peso.get((fila.get("keyword") or "", p), 1.0)

        total_por_periodo[p] += w
        muestra_por_periodo[p] += 1

        # Una vacante puede aportar varios términos (p. ej. varias skills).
        for term in _terminos(fila, dimension):
            acumulado[(p, term)] += w
            crudo[(p, term)] += 1

    # Pre-filtro por término: descarta ya los que NUNCA superarán los umbrales de
    # calidad de construir_tendencias (poca muestra total o pocos meses). Sin esto
    # se guardaba toda la cola larga —el 86% de los títulos aparece una sola vez—
    # inflando la tabla ~10x (cargo/TODOS/TODOS pasó de 28.977 a ~2.900 filas) y
    # haciendo lentísima la lectura. Los mínimos se miden sobre la MUESTRA CRUDA.
    muestra_por_termino: Dict[str, int] = defaultdict(int)
    periodos_por_termino: Dict[str, set] = defaultdict(set)
    for (periodo, termino), n in crudo.items():
        if muestra_por_periodo[periodo] >= MIN_VACANTES_MES:
            muestra_por_termino[termino] += n
            periodos_por_termino[termino].add(periodo)

    if dimension == "programa":
        # La dimensión interna 'programa' describe el MIX de carreras demandadas,
        # así que se conservan todas: descartar las pequeñas haría que los shares
        # no sumaran 1 y sesgaría el ranking de skills que se calcula con ellos.
        terminos_validos = set(muestra_por_termino)
    else:
        terminos_validos = {
            t
            for t in muestra_por_termino
            if muestra_por_termino[t] >= MIN_MUESTRA_TOTAL
            and len(periodos_por_termino[t]) >= MIN_PERIODOS
        }

    observaciones = []
    for (periodo, termino), menciones_pond in acumulado.items():
        if termino not in terminos_validos:
            continue
        # Un mes con pocas vacantes REALMENTE muestreadas no es representativo,
        # por muy grande que sea su peso.
        if muestra_por_periodo[periodo] < MIN_VACANTES_MES:
            continue
        total = total_por_periodo[periodo]
        if total <= 0:
            continue
        observaciones.append(
            {
                "dimension": dimension,
                "termino": termino,
                "periodo": periodo,
                "fuente": fuente,
                "pais": pais,
                "programa": programa,
                "seniority": seniority,
                # Se redondea a entero para la columna: es una estimación del
                # número de vacantes del mercado, no un conteo de la muestra.
                "menciones": int(round(menciones_pond)),
                "n_vacantes": int(round(total)),
                "muestra": crudo[(periodo, termino)],
                "share": menciones_pond / total,
            }
        )
    return observaciones


def guardar_observaciones(observaciones: List[Dict[str, Any]], limpiar: bool = False) -> int:
    """Persiste las observaciones. Con `limpiar=True` vacía la tabla primero.

    El borrado importa: si un término deja de superar los filtros de calidad tras
    ampliar la muestra, un simple upsert lo dejaría ahí para siempre como fila
    zombi de un cálculo viejo.
    """
    if limpiar:
        supabase.table(TABLA_OBS).delete().neq("id", 0).execute()
        # Los periodos y las fuentes pudieron cambiar: invalida el caché de
        # opciones en memoria Y en disco.
        global _cache_opciones
        _cache_opciones = None
        CACHE_OPCIONES_PATH.unlink(missing_ok=True)

    if not observaciones:
        return 0

    guardadas = 0
    for i in range(0, len(observaciones), 500):
        lote = observaciones[i : i + 500]
        supabase.table(TABLA_OBS).upsert(
            lote,
            on_conflict="dimension,termino,periodo,fuente,pais,programa,seniority",
        ).execute()
        guardadas += len(lote)
    return guardadas


def leer_observaciones(
    dimension: str,
    programa: str = TODOS,
    seniority: str = TODOS,
    fuente: str | None = None,
    paises: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Observaciones de uno o varios países (se combinan aguas arriba).

    NO se filtra por fuente: cada país lo cubre una sola fuente (Colombia ->
    Google Jobs, el resto -> Adzuna), así que el país ya la determina. Filtrar
    además por fuente rompería las selecciones que mezclan mercados de fuentes
    distintas. El parámetro se mantiene por compatibilidad y se ignora.
    """
    paises = paises or [PAIS_DEFECTO]
    filas: List[Dict[str, Any]] = []
    start, page = 0, 1000
    while True:
        r = (
            supabase.table(TABLA_OBS)
            .select("*")
            .eq("dimension", dimension)
            .eq("programa", programa)
            .eq("seniority", seniority)
            .in_("pais", paises)
            .order("periodo")
            .range(start, start + page - 1)
            .execute()
        )
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < page:
            break
        start += page
    return filas


def _meses_entre(desde: str, hasta: str) -> List[str]:
    """Secuencia de periodos 'YYYY-MM-01' entre desde y hasta, ambos inclusive."""
    y, m = int(desde[:4]), int(desde[5:7])
    yf, mf = int(hasta[:4]), int(hasta[5:7])
    out = []
    while (y, m) <= (yf, mf):
        out.append(f"{y:04d}-{m:02d}-01")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# Caché de las opciones de filtro. Solo cambian tras un recálculo, y calcularlas
# cuesta ~20 consultas (una por fuente y dimensión) ≈ 9 s, así que además de la
# memoria se persisten en disco para que reiniciar el backend no las repita.
# `guardar_observaciones(limpiar=True)` invalida ambos niveles.
_cache_opciones: Dict[str, Any] | None = None
CACHE_OPCIONES_PATH = Path(__file__).parent / "_cache_opciones.json"


def opciones_disponibles() -> Dict[str, List[str]]:
    """Valores de filtro para poblar los dropdowns.

    Se DERIVAN, no se escanean: los programas vienen del catálogo O*NET (config),
    los niveles de seniority son una constante, y los periodos se generan a partir
    del rango (min/max) de la tabla —dos consultas que usan el índice de periodo—.

    Antes esto escaneaba las ~121k filas de `tendencias_observaciones` solo para
    sacar 30 valores distintos, y tardaba ~26 s: era lo que congelaba los filtros.

    Ofrecer un programa sin datos en alguna combinación no es un problema: la
    página ya muestra "sin datos para esta combinación" cuando toca.
    """
    global _cache_opciones
    if _cache_opciones is not None:
        return _cache_opciones

    # Caché en disco: sobrevive a reinicios del backend.
    if CACHE_OPCIONES_PATH.exists():
        try:
            with open(CACHE_OPCIONES_PATH, encoding="utf-8") as fh:
                _cache_opciones = json.load(fh)
            return _cache_opciones
        except Exception:
            pass  # caché corrupto: se recalcula

    from ONet.onet_service import PROGRAMAS_ONET

    programas = [TODOS] + sorted(PROGRAMAS_ONET.keys())
    seniorities = [TODOS] + list(NIVELES)
    # Nivel de escolaridad: eje independiente de seniority (tipo de ocupación,
    # no experiencia). Solo alimenta demanda_actual.py, pero se expone junto a
    # las demás opciones para que el frontend arranque el dropdown sin un
    # segundo viaje de red. Ver Tendencias/escolaridad.py.
    escolaridades = [TODOS] + list(NIVELES_ESCOLARIDAD)
    periodos: List[str] = []

    try:
        r_min = (
            supabase.table(TABLA_OBS).select("periodo").order("periodo").limit(1).execute()
        )
        r_max = (
            supabase.table(TABLA_OBS)
            .select("periodo")
            .order("periodo", desc=True)
            .limit(1)
            .execute()
        )
        if r_min.data and r_max.data:
            periodos = _meses_entre(r_min.data[0]["periodo"], r_max.data[0]["periodo"])
    except Exception:
        periodos = []

    # Fuentes que de verdad tienen datos (un count por fuente del catálogo, barato).
    # Se anota además qué dimensiones tiene cada una: Google Jobs no entrega
    # sector, y solo las fuentes con texto completo producen skills.
    #
    # RETRY POR CONSULTA, no por mercado: este bucle hace hasta 4 peticiones HTTP
    # secuenciales a Supabase por mercado (1 conteo base + 1 por dimensión). Antes
    # un solo `try/except` envolvía las 4 y CUALQUIER hipo de red transitorio (ya
    # observado en esta sesión: ReadError, WinError 10054) descartaba el mercado
    # ENTERO en silencio — sin log, sin reintento. Como esto se recalcula de forma
    # no determinista según qué tan cargada esté la red en ese momento, un mercado
    # podía aparecer en una corrida y faltar en la siguiente sin motivo aparente.
    # Ahora cada conteo reintenta solo, y si de verdad falla tras los reintentos
    # se registra explícitamente en vez de desaparecer sin dejar rastro.
    def _contar_con_reintento(query_factory, intentos: int = 3) -> int | None:
        for intento in range(1, intentos + 1):
            try:
                r = query_factory().execute()
                return r.count or 0
            except Exception as e:
                if intento == intentos:
                    print(f"   ⚠ opciones_disponibles: conteo falló tras {intentos} intentos: {e}")
                    return None
                time.sleep(0.5 * intento)
        return None

    fuentes = []
    for f in FUENTES_CATALOGO:
        total = _contar_con_reintento(
            lambda f=f: supabase.table(TABLA_OBS).select("id", count="exact", head=True)
            .eq("fuente", f["fuente"]).eq("pais", f["pais"])
        )
        if total is None:
            print(f"   ⚠ opciones_disponibles: se omite {f['fuente']}/{f['pais']} (conteo base falló)")
            continue
        if total == 0:
            continue

        dims = []
        for dim in ("cargo", "sector", "skill"):
            n = _contar_con_reintento(
                lambda f=f, dim=dim: supabase.table(TABLA_OBS).select("id", count="exact", head=True)
                .eq("fuente", f["fuente"]).eq("pais", f["pais"]).eq("dimension", dim)
            )
            if n is None:
                print(f"   ⚠ opciones_disponibles: {f['fuente']}/{f['pais']} dimension={dim} "
                      f"quedó indeterminada (se omite esa dimensión, no el mercado)")
            elif n > 0:
                dims.append(dim)

        # `id` y `tipo` son para el selector multi-fuente del frontend. Los
        # campos originales (fuente, pais, label) se conservan tal cual para
        # no romper a quien ya los consume.
        fuentes.append({
            **f,
            "dimensiones": dims,
            "id": f"{f['fuente']}:{f['pais']}",
            "tipo": "vacantes",
            "naturaleza": "observado",
        })

    # O*NET no vive en `tendencias_observaciones` (es normativo, no una muestra de
    # vacantes), pero el usuario debe poder verlo y elegirlo como fuente de skills.
    fuentes.append({
        "fuente": "onet",
        "pais": None,
        "id": "onet",
        "tipo": "normativo",
        "naturaleza": "normativo",
        "label": "O*NET 27.3",
        "sublabel": "qué requiere cada ocupación (EE.UU.)",
        "dimensiones": ["skill"],
    })

    # SPE Colombia: competencias observadas en vacantes reales. Solo aparece si
    # hay datos cargados (migración 007 + ETL de los anexos).
    try:
        from SPE.spe_service import catalogo_fuente
        fuentes.extend(catalogo_fuente())
    except Exception:
        pass

    # CNO 2025 del SENA: el equivalente colombiano de O*NET, ya en español.
    # Normativo como O*NET, pero con la taxonomía del país.
    try:
        from SENA.sena_service import catalogo_fuente as catalogo_sena
        fuentes.extend(catalogo_sena())
    except Exception:
        pass

    # Informes PDF validados. Si la migración 006 no se ha ejecutado, devuelve []
    # y la funcionalidad queda simplemente invisible.
    try:
        from Informes.informes_service import catalogo_fuentes
        fuentes.extend(catalogo_fuentes())
    except Exception:
        pass

    _cache_opciones = {
        "programas": programas,
        "seniorities": seniorities,
        "escolaridades": escolaridades,
        "periodos": periodos,
        "fuentes": fuentes,
    }
    try:
        # Escritura ATÓMICA (temp + reemplazo), no en el archivo final directo.
        # Motivo real, no hipotético: dos peticiones concurrentes contra un caché
        # recién invalidado (p. ej. justo después de un recálculo) disparan cada
        # una su propio recómputo y ambas intentan escribir el mismo archivo a la
        # vez. Escribir directo permite que sus bytes se intercalen — se observó
        # en esta sesión como texto corrupto ("AdministraciÃ³n" en vez
        # de "Administración", un mojibake de doble-UTF-8 causado por la
        # intercalación). `os.replace` es atómico: el último en terminar
        # reemplaza limpio, nunca deja un archivo a medio escribir.
        tmp = CACHE_OPCIONES_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_cache_opciones, fh, ensure_ascii=False)
        os.replace(tmp, CACHE_OPCIONES_PATH)
    except Exception:
        pass  # sin disco escribible seguimos con el caché en memoria
    return _cache_opciones


# ---------------------------------------------------------------------------
# 2. Cálculo de la tendencia
# ---------------------------------------------------------------------------

def calcular_tendencia(valores: List[float]) -> Tuple[str, float]:
    """Regresión lineal ponderada sobre la serie. Devuelve (tendencia, score 0-1).

    Los pesos crecen con el tiempo (1, 2, 3, ...) para que los meses recientes
    manden sobre los antiguos.
    """
    if len(valores) < 2:
        return "estable", 0.5

    x = list(range(len(valores)))
    y = valores
    w = [xi + 1 for xi in x]

    sw = sum(w)
    swx = sum(wi * xi for wi, xi in zip(w, x))
    swy = sum(wi * yi for wi, yi in zip(w, y))
    swxx = sum(wi * xi * xi for wi, xi in zip(w, x))
    swxy = sum(wi * xi * yi for wi, xi, yi in zip(w, x, y))

    denominador = sw * swxx - swx**2
    if denominador == 0:
        return "estable", 0.5

    pendiente = (sw * swxy - swx * swy) / denominador

    # Normalizar contra la media SIMPLE: hace comparables términos de magnitudes
    # muy distintas (un sector con 30% de share vs. uno con 0.5%).
    #
    # Reto-Alumni normalizaba contra la media ponderada, lo que rompía la
    # simetría: la serie [.10 .11 .12 .13 .14] daba "estable" mientras que su
    # espejo [.14 .13 .12 .11 .10] daba "decreciente", porque los pesos recientes
    # inflan el denominador cuando la serie sube. La media simple es idéntica en
    # ambos casos, así que subidas y bajadas del mismo tamaño se clasifican igual.
    media_y = sum(y) / len(y)
    if not media_y:
        return "estable", 0.5
    pendiente_norm = pendiente / media_y

    if pendiente_norm > UMBRAL:
        return "creciente", round(min(1.0, 0.5 + pendiente_norm * 2), 3)
    if pendiente_norm < -UMBRAL:
        return "decreciente", round(min(1.0, 0.5 + abs(pendiente_norm) * 2), 3)
    return "estable", round(max(0.2, 0.5 - abs(pendiente_norm) / UMBRAL * 0.3), 3)


# ---------------------------------------------------------------------------
# 3. Estructura final que consume el frontend
# ---------------------------------------------------------------------------

def _umbral_cuota(terminos: Dict[str, Any]) -> float:
    """Cuota mínima para que un término pueda salir en las tarjetas destacadas.

    Es RELATIVO (el percentil 25 de la propia dimensión), no un porcentaje fijo,
    porque las escalas no son comparables: la cuota máxima de un cargo ronda el
    1.5% mientras que la de un sector llega al 42%. Un umbral absoluto vaciaría
    una dimensión y no filtraría nada en la otra.

    Sin este filtro, el score (que mide pendiente relativa, no importancia)
    corona términos marginales: 'medical assistant', con score 1.0 y un 0.06% de
    cuota, se anunciaba como el cargo más dinámico del mercado.

    Se usa el p25 y no la mediana a propósito: el p25 (0.068% en cargos) basta
    para descartar la cola de ruido y deja pasar señales reales como
    'data engineer'; la mediana descartaba la mitad de los términos y dejaba las
    tarjetas de "emergentes" vacías.
    """
    if not terminos:
        return 0.0
    shares = [v["share_promedio"] for v in terminos.values()]
    if len(shares) < 4:
        # quantiles() exige al menos 2 puntos y con tan pocos términos el p25 no
        # significa nada: mejor no filtrar.
        return 0.0
    return quantiles(shares, n=4)[0]


def _insights(terminos: Dict[str, Any]) -> Dict[str, Any]:
    """Las tres tarjetas destacadas, portadas del dashboard de Reto-Alumni.

    Allí hablaban de *skills*; aquí de cargos o sectores, que es lo que los datos
    de Adzuna soportan de verdad (ver README §9.7). El criterio de "emergente"
    (creciente con score > 0.7) es el mismo que usaba Reto-Alumni; lo que se
    añade es el filtro de cuota mínima (ver `_umbral_cuota`), porque ordenar solo
    por score destacaba términos sin peso en el mercado.

    Los KPIs de la cabecera NO usan este filtro: allí sí interesa el recuento
    completo de crecientes/estables/decrecientes.
    """
    minimo = _umbral_cuota(terminos)
    relevantes = {n: v for n, v in terminos.items() if v["share_promedio"] >= minimo}

    crecientes = sorted(
        [(n, v) for n, v in relevantes.items() if v["tendencia"] == "creciente"],
        key=lambda x: -x[1]["score_tendencia"],
    )
    decrecientes = sorted(
        [(n, v) for n, v in relevantes.items() if v["tendencia"] == "decreciente"],
        key=lambda x: -x[1]["score_tendencia"],
    )
    emergentes = [(n, v) for n, v in crecientes if v["score_tendencia"] > 0.7]

    resumir = lambda pares: [  # noqa: E731
        {"termino": n, "score": v["score_tendencia"], "share": v["share_promedio"]}
        for n, v in pares
    ]

    return {
        # Cuota mínima aplicada, para que la UI pueda explicar el recorte.
        "umbral_cuota": minimo,
        # "Skill más dinámica" -> el término que más crece
        "mas_dinamico": (
            {
                "termino": crecientes[0][0],
                "score": crecientes[0][1]["score_tendencia"],
                "share": crecientes[0][1]["share_promedio"],
            }
            if crecientes
            else None
        ),
        # "Competencias emergentes" -> señal de crecimiento fuerte
        "emergentes": {"total": len(emergentes), "top": resumir(emergentes[:5])},
        # "Skills a monitorear" -> los que retroceden
        "a_monitorear": {"total": len(decrecientes), "top": resumir(decrecientes[:5])},
    }


def construir_tendencias(
    dimension: str = "cargo",
    programa: str = TODOS,
    seniority: str = TODOS,
    desde: str | None = None,
    hasta: str | None = None,
    top: int | None = None,
    fuente: str = FUENTE_DEFECTO,
    paises: List[str] | None = None,
) -> Dict[str, Any]:
    """Serie + clasificación, ya filtrada.

    `desde`/`hasta` acotan el rango de meses (formato 'YYYY-MM-01'); `top` limita
    cuántos términos se devuelven, ordenados por fuerza de la señal.

    COMBINAR VARIOS PAÍSES
    ----------------------
    `paises` acepta varios mercados. Se combinan promediando el share de cada uno,
    de modo que **cada país pesa igual**, NO sumando volúmenes. El motivo es que
    los mercados son de tamaños muy distintos: EE.UU. concentra el ~93% del volumen
    estimado, así que sumar haría invisibles a México o España (0.2% cada uno) y
    seleccionarlos no cambiaría nada.

        share_combinado(término, mes) = Σ share(término, mes, país) / nº países con datos ese mes

    Un país donde el término no aparece cuenta como share 0 (no se omite: omitirlo
    sesgaría la media hacia arriba). Un país sin datos en ese mes no entra en el
    denominador.

    Ojo con la lectura: `share_promedio` es una media entre mercados, mientras que
    `total_menciones` sí es la suma de vacantes estimadas de todos ellos.
    """
    paises = paises or [PAIS_DEFECTO]
    observaciones = leer_observaciones(dimension, programa, seniority, fuente, paises)

    if desde:
        observaciones = [o for o in observaciones if o["periodo"] >= desde]
    if hasta:
        observaciones = [o for o in observaciones if o["periodo"] <= hasta]

    # Descarta términos que no pueden pertenecer a este programa. `programa_relacionado`
    # se estampa con la keyword buscada sin mirar el título, así que "registered nurse"
    # arrastraba "Registered Veterinary Nurse" a Enfermería y salía como el cargo
    # "Auxiliar veterinario(a)". Se filtra al LEER porque las observaciones ya
    # calculadas conservan el término viejo; el mismo filtro corre al recolectar.
    if programa != TODOS and dimension == "cargo":
        observaciones = [o for o in observaciones if es_pertinente(programa, o.get("termino"))]

    if not observaciones:
        return {
            "meta": {
                "dimension": dimension,
                "programa": programa,
                "seniority": seniority,
                "fuente": fuente,
                "paises": paises,
                "total_terminos": 0,
                "crecientes": 0,
                "estables": 0,
                "decrecientes": 0,
                "periodos": [],
                "sin_datos": True,
            },
            "terminos": {},
            "insights": _insights({}),
        }

    # Todos los meses con datos, en orden. Definen el eje temporal común.
    periodos = sorted({o["periodo"] for o in observaciones})

    # Países que aportan datos en cada mes: son el denominador de la media. Un país
    # que aún no cubre ese mes no debe penalizar la media de los que sí.
    paises_por_periodo: Dict[str, set] = defaultdict(set)
    for o in observaciones:
        paises_por_periodo[o["periodo"]].add(o["pais"])

    # n_vacantes estimadas del mes = suma de las de cada país (una por país-mes).
    n_por_pais_periodo = {(o["periodo"], o["pais"]): o["n_vacantes"] for o in observaciones}
    n_por_periodo: Dict[str, int] = defaultdict(int)
    for (per, _p), n in n_por_pais_periodo.items():
        n_por_periodo[per] += n

    # término -> periodo -> {país: observación}
    por_termino: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
    for o in observaciones:
        por_termino[o["termino"]][o["periodo"]][o["pais"]] = o

    terminos: Dict[str, Any] = {}
    for termino, hist in por_termino.items():
        # El soporte se mide en vacantes REALES muestreadas (sumadas entre países),
        # no en la estimación ponderada.
        total_muestra = sum(
            o.get("muestra", 0) for per in hist.values() for o in per.values()
        )
        if total_muestra < MIN_MUESTRA_TOTAL:
            continue
        if len(hist) < MIN_PERIODOS:
            continue

        serie: List[float] = []
        historial: Dict[str, Dict[str, Any]] = {}
        for p in periodos:
            obs_p = hist.get(p, {})
            n_paises = len(paises_por_periodo[p]) or 1
            # Media entre países: los que no tienen el término aportan 0.
            share_prom = sum(o["share"] for o in obs_p.values()) / n_paises
            serie.append(share_prom)
            historial[p] = {
                "menciones": sum(o["menciones"] for o in obs_p.values()),
                "share": round(share_prom, 5),
                "n_vacantes": n_por_periodo[p],
            }

        tendencia, score = calcular_tendencia(serie)
        presentes = sorted(hist)
        terminos[termino] = {
            "historial": historial,
            "tendencia": tendencia,
            "score_tendencia": score,
            "total_menciones": sum(
                o["menciones"] for per in hist.values() for o in per.values()
            ),
            "total_muestra": total_muestra,
            "primera_aparicion": presentes[0],
            "ultima_aparicion": presentes[-1],
            "periodos_cubiertos": len(hist),
            "share_promedio": round(sum(serie) / len(serie), 5),
        }

    conteo = lambda t: sum(1 for v in terminos.values() if v["tendencia"] == t)  # noqa: E731

    # Los KPIs y los insights se calculan sobre TODOS los términos que pasaron los
    # filtros de calidad; `top` solo recorta lo que se envía por la red. Si no,
    # "12 crecientes" cambiaría al mover el deslizador de Top N.
    meta = {
        "dimension": dimension,
        "fuente": fuente,
        "paises": paises,
        "programa": programa,
        "seniority": seniority,
        "total_terminos": len(terminos),
        "crecientes": conteo("creciente"),
        "estables": conteo("estable"),
        "decrecientes": conteo("decreciente"),
        "periodos": periodos,
        "vacantes_por_periodo": {p: n_por_periodo[p] for p in periodos},
        "sin_datos": False,
    }
    insights = _insights(terminos)

    if top:
        mejores = sorted(
            terminos.items(), key=lambda x: -x[1]["score_tendencia"]
        )[:top]
        terminos = dict(mejores)

    return {"meta": meta, "terminos": terminos, "insights": insights}


def recalcular_todo(
    filas_historicas: List[Dict[str, Any]],
    volumenes: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Precalcula TODAS las combinaciones (país × dimensión × programa × seniority).

    Se procesa un país (Adzuna EE.UU., Reino Unido…) a la vez: cada uno es una
    fuente independiente en la tabla, con su propio share y sus propios términos.
    El centinela TODOS representa el agregado sin filtrar en cada eje.

    La tabla se vacía antes de escribir: al ampliar la muestra, un término puede
    dejar de superar los umbrales y no debe sobrevivir como fila zombi.
    """
    # La seniority se infiere del título CRUDO, antes de que normalize_title()
    # la borre para agrupar cargos.
    for fila in filas_historicas:
        fila["_seniority"] = detectar_seniority(fila.get("title"))

    vols = volumenes or []
    # Cada (fuente, país) es un mercado independiente con su propia serie.
    mercados = sorted({
        (f.get("fuente") or FUENTE_DEFECTO, f.get("pais"))
        for f in filas_historicas
        if f.get("pais")
    })

    # Adzuna se pondera con el volumen real de cada keyword, así que un país suyo
    # SIN volúmenes está a medio recolectar y se excluye (sus tendencias saldrían
    # sesgadas). Google Jobs no tiene ese `count`, así que no se le exige.
    paises_con_vol = {v.get("pais", PAIS_DEFECTO) for v in vols}
    excluidos = [
        (fu, pa) for fu, pa in mercados if fu == FUENTE_DEFECTO and pa not in paises_con_vol
    ]
    if excluidos:
        print(f"  [!] Mercados excluidos (Adzuna sin volúmenes, incompletos): {excluidos}")
    mercados = [m for m in mercados if m not in excluidos]

    todas: List[Dict[str, Any]] = []
    for fuente, pais in mercados:
        filas_m = [
            f
            for f in filas_historicas
            if f.get("pais") == pais and (f.get("fuente") or FUENTE_DEFECTO) == fuente
        ]
        vols_m = [v for v in vols if v.get("pais", PAIS_DEFECTO) == pais] if fuente == FUENTE_DEFECTO else []

        programas = sorted({
            f["programa_relacionado"] for f in filas_m if f.get("programa_relacionado")
        })

        # 'skill' solo aplica a fuentes con descripción completa (Google Jobs);
        # en Adzuna la columna viene vacía y no generaría observaciones.
        dimensiones = ["cargo", "sector"]
        if any(isinstance(f.get("skills"), list) and f["skills"] for f in filas_m):
            dimensiones.append("skill")

        # Dimensión interna 'programa': la demanda de cada carrera, precalculada
        # para que `skills_demandadas` no relea el histórico crudo. Solo tiene
        # sentido sin filtrar por programa (sería redundante consigo misma), pero
        # sí por seniority (el mix de carreras cambia según el nivel).
        for sen in [TODOS] + list(NIVELES):
            filas_sen = (
                filas_m if sen == TODOS else [f for f in filas_m if f["_seniority"] == sen]
            )
            if filas_sen:
                todas.extend(
                    agregar_observaciones(
                        filas_sen, "programa", vols_m, TODOS, sen, fuente, pais
                    )
                )

        for dimension in dimensiones:
            for prog in [TODOS] + programas:
                filas_prog = (
                    filas_m
                    if prog == TODOS
                    else [f for f in filas_m if f.get("programa_relacionado") == prog]
                )
                if not filas_prog:
                    continue

                for sen in [TODOS] + list(NIVELES):
                    filas_sen = (
                        filas_prog
                        if sen == TODOS
                        else [f for f in filas_prog if f["_seniority"] == sen]
                    )
                    if not filas_sen:
                        continue

                    todas.extend(
                        agregar_observaciones(
                            filas_sen, dimension, vols_m, prog, sen, fuente, pais
                        )
                    )

    guardadas = guardar_observaciones(todas, limpiar=True)
    return {
        "observaciones": guardadas,
        "mercados": [f"{fu}/{pa}" for fu, pa in mercados],
    }
