"""
Backfill histórico de vacantes desde Adzuna, para poder medir tendencias reales.

EL PROBLEMA
-----------
La recolección normal (`Adzuna/adzuna_service.py`) pide `sort_by=date` en las 2
primeras páginas, así que solo trae las ~100 vacantes MÁS RECIENTES por keyword.
Resultado: el 91% de las filas de `vacantes` tienen `created_at` del mismo mes.
Calcular una tendencia sobre eso mediría el scraper, no el mercado.

LA SOLUCIÓN
-----------
La API de Adzuna acepta dos parámetros que, combinados, permiten muestrear
cualquier mes del pasado:

    max_days_old=D  ->  restringe la ventana a los últimos D días
    sort_direction=up -> devuelve primero las MÁS ANTIGUAS de esa ventana

Es decir: pedir `max_days_old=D, sort_direction=up` aterriza justo en el borde
de edad D. Verificado contra la API real (hoy = julio 2026):

    D=30  -> vacantes de 2026-06        D=90  -> 2026-04
    D=60  -> vacantes de 2026-05        D=365 -> 2025-07

Barriendo D mes a mes obtenemos una muestra estratificada por antigüedad. Las
vacantes se guardan en `vacantes_historicas` (tabla propia, para que el scrape
normal con `borrar=true` jamás borre la historia).

PRESUPUESTO
-----------
Cada llamada = 1 página de 50 resultados. Se recorre keyword por keyword, y para
CADA keyword se barren TODAS las ventanas antes de pasar a la siguiente. Así, si
el presupuesto se agota a mitad, los meses ya cubiertos lo están de forma pareja
(en lugar de tener 2024 completo y 2026 vacío).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

import requests

from config import ADZUNA_APP_ID, ADZUNA_APP_KEY, PROGRAMAS_KEYWORDS, es_pertinente, coincide_con_keyword
from Adzuna.adzuna_service import supabase

TABLA_HIST = "vacantes_historicas"
TABLA_VOL = "muestreo_volumen"

# Días promedio por mes: 365.25 / 12. Se usa para convertir "hace N meses" en
# el `max_days_old` que hay que pedirle a la API.
DIAS_POR_MES = 30.44

RESULTS_PER_PAGE = 50
TIMEOUT = 30


def _ventanas(meses_atras: int) -> List[int]:
    """max_days_old a pedir para muestrear cada uno de los últimos N meses.

    Se apunta a la mitad del mes objetivo para que la muestra caiga dentro de él
    y no en la frontera con el mes vecino.
    """
    return [int(m * DIAS_POR_MES) for m in range(1, meses_atras + 1)]


def _buscar(keyword: str, max_days_old: int, pais: str = "us") -> Tuple[List[Dict[str, Any]], int]:
    """Una llamada a Adzuna (mercado `pais`). Devuelve (resultados, count).

    `count` es el TOTAL de vacantes que coinciden en esa ventana (no solo las 50
    que devuelve la página). Viene gratis en la misma respuesta y es la clave
    para saber el volumen real de cada keyword.
    """
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "results_per_page": RESULTS_PER_PAGE,
        "sort_by": "date",
        "sort_direction": "up",     # ← más antiguas primero: nos lleva al borde de la ventana
        "max_days_old": max_days_old,
    }
    try:
        r = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/{pais}/search/1",
            params=params,
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            print(f"   [!] HTTP {r.status_code} para '{keyword}' (D={max_days_old}, {pais})")
            return [], 0
        data = r.json()
        return data.get("results", []), int(data.get("count") or 0)
    except Exception as e:
        print(f"   [!] Error en '{keyword}' (D={max_days_old}, {pais}): {e}")
        return [], 0


def _fila(job: Dict[str, Any], keyword: str, programa: str, pais: str = "us") -> Dict[str, Any] | None:
    """Convierte el JSON de Adzuna al esquema de `vacantes_historicas`.

    Devuelve None si la oferta no corresponde al programa: Adzuna resuelve por
    full-text match, así que "registered nurse" también devuelve "Registered
    Veterinary Nurse", y aquí el programa se estampa por la keyword buscada.
    """
    if "id" not in job or not job.get("created"):
        return None
    if not es_pertinente(programa, job.get("title")):
        return None
    # El backfill pide sort_direction=up (más antiguas primero) para poder
    # muestrear meses pasados, y eso desactiva el orden por relevancia de
    # Adzuna: para keywords amplias de 1-2 palabras, la mayoría de lo que
    # vuelve no tiene relación real con lo buscado. Ver coincide_con_keyword().
    if not coincide_con_keyword(keyword, job.get("title")):
        return None
    return {
        "id": int(job["id"]),
        "title": job.get("title"),
        "company": (job.get("company") or {}).get("display_name"),
        "category": (job.get("category") or {}).get("label"),
        "contract_time": job.get("contract_time"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "created_at": job.get("created"),
        "fuente": "adzuna",
        "pais": pais,
        "keyword": keyword,
        "programa_relacionado": programa,
    }


def _guardar(filas: List[Dict[str, Any]]) -> int:
    """Upsert por id: reejecutar el backfill actualiza en vez de duplicar."""
    if not filas:
        return 0
    # Dedup dentro del propio lote (una misma vacante puede salir en dos ventanas).
    unicas = {f["id"]: f for f in filas}
    try:
        supabase.table(TABLA_HIST).upsert(
            list(unicas.values()), on_conflict="id"
        ).execute()
        return len(unicas)
    except Exception as e:
        print(f"   [!] Error guardando lote: {e}")
        return 0


def _mes_de_ventana(dias: int) -> str:
    """Mes (YYYY-MM-01) al que apunta una ventana `max_days_old`."""
    objetivo = date.today() - timedelta(days=dias)
    return objetivo.replace(day=1).isoformat()


def _volumenes_de_counts(counts: List[Tuple[int, int]]) -> Dict[str, int]:
    """Convierte counts acumulados por ventana en volumen real por mes.

    `counts` es [(dias, count_acumulado), ...] ordenado de ventana más corta a
    más larga. Como `count` cuenta TODAS las vacantes de los últimos `dias` días,
    la diferencia entre dos ventanas consecutivas es lo publicado en ese mes.

    Nota: Adzuna retira vacantes antiguas de su índice, así que los meses lejanos
    quedan subestimados. Por eso aguas abajo se usa el SHARE (reparto dentro de
    cada mes) y no el volumen absoluto: la atrición afecta a todas las keywords
    del mismo mes y se cancela al dividir.
    """
    volumenes: Dict[str, int] = {}
    previo = 0
    for dias, acumulado in sorted(counts):
        delta = max(0, acumulado - previo)
        volumenes[_mes_de_ventana(dias)] = delta
        previo = acumulado
    return volumenes


def _guardar_volumenes(filas: List[Dict[str, Any]]) -> int:
    if not filas:
        return 0
    # Postgres rechaza un upsert que traiga la misma clave dos veces en el mismo
    # comando ("ON CONFLICT DO UPDATE cannot affect row a second time"). Puede
    # pasar porque dos programas compartan su primera keyword (p. ej.
    # 'financial analyst'), así que deduplicamos por la clave completa antes de
    # enviar (la misma que usa on_conflict).
    unicas = {(f["keyword"], f["periodo"], f.get("fuente", "adzuna"), f["pais"]): f for f in filas}
    try:
        supabase.table(TABLA_VOL).upsert(
            list(unicas.values()), on_conflict="keyword,periodo,fuente,pais"
        ).execute()
        return len(unicas)
    except Exception as e:
        print(f"   [!] Error guardando volúmenes: {e}")
        return 0


def keywords_ya_recolectadas(pais: str = "us") -> set[str]:
    """Keywords que ya tienen vacantes en `vacantes_historicas` para ese país."""
    return {f["keyword"] for f in leer_historico(pais) if f.get("keyword")}


def recolectar_historico(
    meses_atras: int = 24,
    presupuesto: int = 250,
    pausa: float = 0.25,
    saltar_existentes: bool = True,
    keywords_por_programa: int = 1,
    pais: str = "us",
) -> Dict[str, Any]:
    """Muestrea los últimos `meses_atras` meses gastando como mucho `presupuesto` llamadas.

    Guarda dos cosas por cada llamada:
      - las vacantes devueltas          -> `vacantes_historicas`
      - el `count` total de la ventana  -> `muestreo_volumen` (peso de la muestra)

    Con `saltar_existentes=True` (por defecto) omite las keywords que ya tienen
    histórico. Así se puede ampliar la cobertura en varias tandas sin volver a
    pagar las llamadas de lo ya recolectado. Pásalo a False para refrescar todo.

    `keywords_por_programa` controla cuántas keywords de cada programa se usan
    (por defecto 1: solo la primera). Subirlo diversifica los cargos detectados
    —cada keyword trae títulos distintos— a costa de más llamadas. Es la palanca
    correcta para que más cargos superen el umbral de tendencia: la mayoría de
    los títulos de vacante aparecen una sola vez, así que más señal solo viene de
    más volumen de datos, no de relajar los filtros.
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise RuntimeError("Faltan ADZUNA_APP_ID / ADZUNA_APP_KEY en el .env")

    ventanas = _ventanas(meses_atras)
    # Las N primeras keywords de cada programa, SIN repetir globalmente: varios
    # programas comparten keywords (p. ej. 'machine learning engineer' está en
    # Ciencia de Datos y en Ing. en IA). Repetirlas gastaría llamadas en vacantes
    # que ya tenemos. Cada keyword se asocia al primer programa que la reclama.
    keywords: List[Tuple[str, str]] = []
    vistas: set[str] = set()
    for prog, kws in PROGRAMAS_KEYWORDS.items():
        for kw in kws[:keywords_por_programa]:
            if kw not in vistas:
                vistas.add(kw)
                keywords.append((prog, kw))

    if saltar_existentes:
        ya = keywords_ya_recolectadas(pais)
        antes = len(keywords)
        keywords = [(p, k) for p, k in keywords if k not in ya]
        if antes != len(keywords):
            print(f"Saltando {antes - len(keywords)} keywords ya recolectadas ({pais})")

    if not keywords:
        return {
            "status": "nada_que_hacer",
            "llamadas_usadas": 0,
            "vacantes_guardadas": 0,
            "volumenes_guardados": 0,
            "meses_cubiertos": 0,
            "cobertura_por_mes": {},
        }

    print(f"Backfill [{pais}]: {meses_atras} meses × {len(keywords)} keywords, tope {presupuesto} llamadas")

    llamadas = 0
    guardadas = 0
    por_mes: Dict[str, int] = {}
    lote: List[Dict[str, Any]] = []
    filas_volumen: List[Dict[str, Any]] = []

    for programa, keyword in keywords:
        if llamadas >= presupuesto:
            break

        counts: List[Tuple[int, int]] = []
        muestreadas_por_mes: Dict[str, int] = {}

        # Para esta keyword barremos TODAS las ventanas antes de pasar a la
        # siguiente: si el presupuesto se agota, los meses ya cubiertos lo están
        # de forma pareja en vez de tener 2024 completo y 2026 vacío.
        for dias in ventanas:
            if llamadas >= presupuesto:
                break

            resultados, count = _buscar(keyword, dias, pais)
            llamadas += 1
            counts.append((dias, count))

            for job in resultados:
                fila = _fila(job, keyword, programa, pais)
                if not fila:
                    continue
                lote.append(fila)
                mes = str(fila["created_at"])[:7]
                por_mes[mes] = por_mes.get(mes, 0) + 1
                muestreadas_por_mes[f"{mes}-01"] = muestreadas_por_mes.get(f"{mes}-01", 0) + 1

            if len(lote) >= 500:
                guardadas += _guardar(lote)
                lote = []

            time.sleep(pausa)  # cortesía con la API

        # Volumen real de esta keyword en cada mes, a partir de los counts.
        for periodo, volumen in _volumenes_de_counts(counts).items():
            n = muestreadas_por_mes.get(periodo, 0)
            if n == 0 or volumen == 0:
                continue  # sin muestra o sin publicaciones: nada que ponderar
            filas_volumen.append(
                {
                    "keyword": keyword,
                    "periodo": periodo,
                    "fuente": "adzuna",
                    "pais": pais,
                    "volumen": volumen,
                    "n_muestreadas": n,
                }
            )

        print(f"  · {programa[:38]:38} llamadas={llamadas}/{presupuesto}")

    guardadas += _guardar(lote)
    vol_guardados = _guardar_volumenes(filas_volumen)

    print(f"\nBackfill terminado: {llamadas} llamadas, {guardadas} vacantes, {vol_guardados} volúmenes")
    print("Cobertura por mes (antes de deduplicar):")
    for mes in sorted(por_mes):
        print(f"   {mes}: {por_mes[mes]}")

    return {
        "status": "completed",
        "llamadas_usadas": llamadas,
        "presupuesto": presupuesto,
        "vacantes_guardadas": guardadas,
        "volumenes_guardados": vol_guardados,
        "meses_cubiertos": len(por_mes),
        "cobertura_por_mes": dict(sorted(por_mes.items())),
    }


def _count(keyword: str, max_days_old: int, pais: str = "us") -> int:
    """Solo el `count` de la ventana (pide 1 resultado: la llamada es más liviana)."""
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "results_per_page": 1,
        "max_days_old": max_days_old,
    }
    try:
        r = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/{pais}/search/1", params=params, timeout=TIMEOUT
        )
        return int(r.json().get("count") or 0) if r.status_code == 200 else 0
    except Exception as e:
        print(f"   [!] count falló para '{keyword}' (D={max_days_old}, {pais}): {e}")
        return 0


def recolectar_volumenes(meses_atras: int = 24, pausa: float = 0.2, pais: str = "us") -> Dict[str, Any]:
    """Rellena `muestreo_volumen` para las keywords ya presentes en el histórico.

    Se usa cuando la muestra ya está descargada pero faltan los pesos (o se
    quieren refrescar), p. ej. si un backfill se cortó antes de consolidarlos.
    No vuelve a bajar vacantes: solo pide `count`.

    `n_muestreadas` se cuenta desde `vacantes_historicas` (del país indicado), no
    desde la corrida que descargó los datos. Así es idempotente y no depende del
    estado de otra ejecución. SALTA las keywords que ya tienen volumen guardado.
    """
    filas = leer_historico(pais)
    if not filas:
        return {"status": "sin_historico", "volumenes_guardados": 0}

    # (keyword, periodo) -> vacantes realmente guardadas
    muestreadas: Dict[Tuple[str, str], int] = {}
    for f in filas:
        kw = f.get("keyword")
        if not kw or not f.get("created_at"):
            continue
        clave = (kw, f"{str(f['created_at'])[:7]}-01")
        muestreadas[clave] = muestreadas.get(clave, 0) + 1

    # Keywords que YA tienen volumen: no re-consultarlas (robustez ante cortes).
    ya_con_vol = {v["keyword"] for v in leer_volumenes(pais)}
    keywords = sorted({kw for kw, _ in muestreadas} - ya_con_vol)
    ventanas = _ventanas(meses_atras)
    print(f"Volúmenes [{pais}]: {len(keywords)} keywords pendientes × {len(ventanas)} ventanas")

    filas_volumen: List[Dict[str, Any]] = []
    llamadas = 0
    for kw in keywords:
        counts: List[Tuple[int, int]] = []
        for dias in ventanas:
            counts.append((dias, _count(kw, dias, pais)))
            llamadas += 1
            time.sleep(pausa)

        lote_kw: List[Dict[str, Any]] = []
        for periodo, volumen in _volumenes_de_counts(counts).items():
            n = muestreadas.get((kw, periodo), 0)
            if n == 0 or volumen == 0:
                continue
            lote_kw.append(
                {
                    "keyword": kw,
                    "periodo": periodo,
                    "fuente": "adzuna",
                    "pais": pais,
                    "volumen": volumen,
                    "n_muestreadas": n,
                }
            )
        # Guardar por keyword: si la red corta, lo ya hecho queda persistido.
        _guardar_volumenes(lote_kw)
        filas_volumen.extend(lote_kw)
        print(f"  · {kw:34} llamadas={llamadas}")

    print(f"\nVolúmenes guardados [{pais}]: {len(filas_volumen)} ({llamadas} llamadas)")
    return {"status": "completed", "llamadas_usadas": llamadas, "volumenes_guardados": len(filas_volumen)}


def leer_volumenes(pais: str | None = None) -> List[Dict[str, Any]]:
    """Volumen real y tamaño de muestra por (keyword, mes). Incluye `pais`."""
    filas: List[Dict[str, Any]] = []
    start, page = 0, 1000
    while True:
        q = (
            supabase.table(TABLA_VOL)
            .select("keyword,periodo,volumen,n_muestreadas,pais")
            .order("id")
            .range(start, start + page - 1)
        )
        if pais:
            q = q.eq("pais", pais)
        r = q.execute()
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < page:
            break
        start += page
    return filas


_COLS_BASE = "id,title,category,created_at,keyword,programa_relacionado,fuente,pais"

# `skills` llega con la migración 004. Se detecta una sola vez para poder leer
# también cuando esa migración aún no está aplicada (modo reducido).
_tiene_skills: bool | None = None


def _select_historico() -> str:
    global _tiene_skills
    if _tiene_skills is None:
        try:
            supabase.table(TABLA_HIST).select("skills").limit(1).execute()
            _tiene_skills = True
        except Exception:
            _tiene_skills = False
    return f"{_COLS_BASE},skills" if _tiene_skills else _COLS_BASE


def leer_historico(pais: str | None = None) -> List[Dict[str, Any]]:
    """Trae la muestra histórica desde Supabase (paginada). Filtra por país si se indica."""
    filas: List[Dict[str, Any]] = []
    start, page = 0, 1000
    columnas = _select_historico()
    while True:
        q = (
            supabase.table(TABLA_HIST)
            .select(columnas)
            .order("id")
            .range(start, start + page - 1)
        )
        if pais:
            q = q.eq("pais", pais)
        r = q.execute()
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < page:
            break
        start += page
    return filas


if __name__ == "__main__":
    recolectar_historico()
