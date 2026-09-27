"""
Orquestador de "Actualizar histórico": todas las fuentes, todas las zonas.

QUÉ RESUELVE
------------
El botón "Actualizar histórico" de la página de Tendencias llamaba a
`POST /tendencias/recolectar`, que SOLO hacía el backfill de Adzuna para UN
país (por defecto EE.UU.). Google Jobs y LinkedIn tenían cada uno su propio
endpoint de recolección y otro de sincronización, y había que acordarse de
llamarlos en orden. En la práctica el Admin pulsaba un botón que decía
"actualizar" y actualizaba una de once zonas.

Este módulo recorre en una sola corrida, en este orden:

  1. Adzuna  — backfill de los 5 mercados del catálogo (us, gb, ca, mx, es),
               cada uno con su propio `presupuesto` de llamadas (es el mismo
               significado que tenía el parámetro cuando solo se corría EE.UU.;
               con `saltar_existentes` las keywords ya recolectadas no gastan).
  2. Google Jobs (co) — recolección round-robin con SerpApi + sincronización
               hacia `vacantes_historicas` (Tendencias/google_jobs_sync.py).
  3. LinkedIn — los mercados de `PAISES_LATAM` (co, mx, ar, cl, pe) en una
               corrida + sincronización (Tendencias/linkedin_sync.py).
  4. Ubicaciones observadas — se refrescan ANTES de recalcular, para que una
               ciudad nueva que llegó en esta misma corrida ya se recorte de
               los títulos (Tendencias/ubicaciones.py).
  5. `recalcular_todo()` + invalidación de los cachés que leen el histórico.

y devuelve un RESUMEN POR FUENTE Y ZONA (estado, filas, llamadas, error,
duración) para que la interfaz muestre qué pasó con cada una.

REGLAS DE SEGURIDAD (heredadas de cada fuente; este módulo las respeta, no las
relaja)
  - Si una fuente falla, se anota el error y se CONTINÚA con la siguiente: una
    caída de SerpApi no debe impedir el backfill de Adzuna ni el recálculo.
  - SerpApi: antes de recolectar se consulta el semáforo de cuota
    (GoogleJobs/serpapi_cuota.py; no consume búsquedas). En ROJO se omite la
    fuente: cada petición devolvería 429. El 429 durante la corrida ya aborta
    la recolección entera dentro de `procesar_vacantes_google`; aquí se marca
    como PARCIAL. Nunca se reintenta.
  - LinkedIn: exige `LINKEDIN_HABILITADO` (aprobación institucional). Si está
    apagado se reporta como "desactivada", no como error. Un 429 aborta la
    corrida completa de LinkedIn (no se pasa al siguiente país) dentro de
    `recolectar_linkedin_latam`; los países no alcanzados se reportan como
    "omitida". Nunca se reintenta, ni se rota IP, ni se usan proxies.
  - Una sola corrida a la vez (`threading.Lock`): dos "Actualizar" seguidos
    gastarían la cuota de SerpApi dos veces y pisarían el recálculo. La
    segunda petición recibe `ActualizacionEnCurso` (el endpoint responde 409).

PARA PROBARLO SIN TOCAR APIS NI BASE
------------------------------------
Todas las llamadas externas pasan por el diccionario `DEPENDENCIAS`, así que
un script puede sustituirlas por funciones falsas (ver la verificación en el
informe de la rama). No hay ninguna otra vía a la red desde este módulo.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from config import LINKEDIN_HABILITADO
from GoogleJobs.google_jobs_service import procesar_vacantes_google
from GoogleJobs.serpapi_cuota import estado_cuota, registrar_uso_local
from LinkedIn.linkedin_service import PAISES_LATAM, LinkedInDesactivado, recolectar_linkedin_latam
from Tendencias.demanda_actual import invalidar_cache as invalidar_demanda
from Tendencias.geografia import invalidar_cache as invalidar_geografia
from Tendencias.google_jobs_sync import sincronizar as sincronizar_google_jobs
from Tendencias.historical_collector import leer_historico, leer_volumenes, recolectar_historico
from Tendencias.linkedin_sync import sincronizar as sincronizar_linkedin
from Tendencias.skills_demandadas import limpiar_cache as limpiar_cache_skills
from Tendencias.tendencias_service import FUENTES_CATALOGO, recalcular_todo
from Tendencias.ubicaciones import cargar_ubicaciones

# Punto único de salida hacia el mundo exterior. Los tests lo parchean.
DEPENDENCIAS: Dict[str, Callable[..., Any]] = {
    "adzuna_recolectar": recolectar_historico,
    "serpapi_cuota": estado_cuota,
    "serpapi_registrar_uso": registrar_uso_local,
    "google_recolectar": procesar_vacantes_google,
    "google_sincronizar": sincronizar_google_jobs,
    "linkedin_recolectar": recolectar_linkedin_latam,
    "linkedin_sincronizar": sincronizar_linkedin,
    "cargar_ubicaciones": cargar_ubicaciones,
    "leer_historico": leer_historico,
    "leer_volumenes": leer_volumenes,
    "recalcular_todo": recalcular_todo,
    "invalidar_caches": lambda: (invalidar_demanda(), invalidar_geografia(), limpiar_cache_skills()),
}

FUENTES_VALIDAS = ("adzuna", "google_jobs", "linkedin")

# Estados posibles de una fuente/zona en el resumen. La UI los pinta con color.
OK, SIN_CAMBIOS, PARCIAL, OMITIDA, DESACTIVADA, ERROR = (
    "ok", "sin_cambios", "parcial", "omitida", "desactivada", "error",
)


class ActualizacionEnCurso(RuntimeError):
    """Ya hay una actualización corriendo en este proceso."""


_lock = threading.Lock()
_estado: Dict[str, Any] = {"en_curso": False, "inicio": None, "ultima": None}


def estado_actualizacion() -> Dict[str, Any]:
    """¿Hay una corrida en curso? ¿Cómo terminó la última? (memoria del proceso)."""
    return dict(_estado)


def _label(fuente: str, pais: str) -> str:
    for f in FUENTES_CATALOGO:
        if f["fuente"] == fuente and f["pais"] == pais:
            return f["label"]
    return f"{fuente} — {pais}"


def _fila(fuente: str, pais: str, **campos: Any) -> Dict[str, Any]:
    base = {
        "fuente": fuente,
        "pais": pais,
        "label": _label(fuente, pais),
        "estado": OK,
        "filas": None,
        "llamadas": None,
        "error": None,
        "duracion_seg": None,
        "detalle": None,
    }
    base.update(campos)
    return base


def _ejecutar(fila: Dict[str, Any], fn: Callable[[], Dict[str, Any] | None]) -> Dict[str, Any]:
    """Corre un paso midiendo el tiempo; un fallo se anota y NO se propaga."""
    t0 = time.monotonic()
    try:
        fila.update(fn() or {})
    except Exception as e:  # la siguiente fuente debe correr igual
        fila["estado"] = ERROR
        fila["error"] = f"{type(e).__name__}: {e}"[:300]
    fila["duracion_seg"] = round(time.monotonic() - t0, 1)
    return fila


# ── Pasos por fuente ────────────────────────────────────────────────────────

def _paso_adzuna(pais: str, meses: int, presupuesto: int, keywords_por_programa: int) -> Dict[str, Any]:
    r = DEPENDENCIAS["adzuna_recolectar"](
        meses_atras=meses,
        presupuesto=presupuesto,
        pais=pais,
        keywords_por_programa=keywords_por_programa,
    )
    estado = SIN_CAMBIOS if r.get("status") == "nada_que_hacer" else OK
    return {
        "estado": estado,
        "filas": r.get("vacantes_guardadas", 0),
        "llamadas": r.get("llamadas_usadas", 0),
        "detalle": r,
    }


def _paso_google(cuota: Dict[str, Any]) -> Dict[str, Any]:
    """Recolecta (si el semáforo lo permite) y sincroniza Google Jobs."""
    detalle: Dict[str, Any] = {"serpapi": {k: cuota.get(k) for k in ("semaforo", "restantes", "total", "estimado")}}
    estado = OK
    error = None
    llamadas = 0

    if cuota.get("semaforo") == "rojo":
        # Cada petición devolvería 429: no se gasta ni una.
        estado, error = OMITIDA, f"Recolección omitida — {cuota.get('recomendacion')}"
    else:
        try:
            r = DEPENDENCIAS["google_recolectar"](borrar=False)
            detalle["recoleccion"] = r
            llamadas = int(r.get("busquedas_usadas") or 0)
            DEPENDENCIAS["serpapi_registrar_uso"](llamadas)
            if r.get("status") == "error":
                estado, error = ERROR, r.get("message") or "SerpApi devolvió error"
            elif r.get("abortado_por_cupo_serpapi"):
                estado, error = PARCIAL, "SerpApi respondió 429: cupo mensual agotado a mitad de la corrida."
        except Exception as e:
            estado, error = ERROR, f"{type(e).__name__}: {e}"[:300]

    # La sincronización es idempotente y barata: se intenta aunque la
    # recolección haya fallado, para llevar al histórico lo que YA hay en
    # `vacantes_google` (p. ej. de una corrida anterior).
    filas = None
    try:
        s = DEPENDENCIAS["google_sincronizar"]()
        detalle["sincronizacion"] = s
        filas = s.get("sincronizadas")
    except Exception as e:
        detalle["sincronizacion"] = {"error": str(e)[:300]}
        if estado == OK:
            estado, error = ERROR, f"Sincronización falló: {e}"[:300]

    return {"estado": estado, "error": error, "filas": filas, "llamadas": llamadas, "detalle": detalle}


def _pasos_linkedin(keywords_por_programa: int) -> List[Dict[str, Any]]:
    """Una fila por país de PAISES_LATAM, más la sincronización común."""
    paises = list(PAISES_LATAM)
    filas: List[Dict[str, Any]] = []
    t0 = time.monotonic()

    if not LINKEDIN_HABILITADO:
        for p in paises:
            filas.append(_fila("linkedin", f"{p}_li", estado=DESACTIVADA, duracion_seg=0.0,
                               error="LINKEDIN_HABILITADO=false: requiere aprobación de la Universidad."))
        return filas

    try:
        r = DEPENDENCIAS["linkedin_recolectar"](keywords_por_programa=keywords_por_programa)
    except LinkedInDesactivado as e:
        for p in paises:
            filas.append(_fila("linkedin", f"{p}_li", estado=DESACTIVADA, duracion_seg=0.0, error=str(e)[:300]))
        return filas
    except Exception as e:
        dur = round(time.monotonic() - t0, 1)
        for p in paises:
            filas.append(_fila("linkedin", f"{p}_li", estado=ERROR, duracion_seg=dur,
                               error=f"{type(e).__name__}: {e}"[:300]))
        return filas

    dur = round(time.monotonic() - t0, 1)
    por_pais = r.get("por_pais") or {}
    abortado = bool(r.get("abortado_por_throttling"))
    for p in paises:
        if p in por_pais:
            d = por_pais[p]
            filas.append(_fila(
                "linkedin", f"{p}_li",
                estado=PARCIAL if d.get("abortado_por_throttling") else OK,
                filas=d.get("ofertas_guardadas"),
                error="LinkedIn respondió 429 (throttling): corrida detenida por diseño." if d.get("abortado_por_throttling") else None,
                duracion_seg=dur,
                detalle=d,
            ))
        else:
            filas.append(_fila(
                "linkedin", f"{p}_li",
                estado=OMITIDA, duracion_seg=0.0,
                error="No se alcanzó: la corrida se detuvo antes por throttling." if abortado else "No incluido en la corrida.",
            ))

    # Sincronización común a todos los países (idempotente).
    try:
        s = DEPENDENCIAS["linkedin_sincronizar"]()
        for f in filas:
            f["detalle"] = {**(f.get("detalle") or {}), "sincronizacion": {"sincronizadas": s.get("sincronizadas")}}
    except Exception as e:
        for f in filas:
            if f["estado"] == OK:
                f["estado"], f["error"] = ERROR, f"Sincronización falló: {e}"[:300]
    return filas


# ── Corrida completa ────────────────────────────────────────────────────────

def actualizar_todo(
    meses: int = 24,
    presupuesto: int = 250,
    keywords_por_programa: int = 1,
    fuentes: List[str] | None = None,
    pais_adzuna: str | None = None,
) -> Dict[str, Any]:
    """Recorre todas las fuentes y zonas, recalcula y devuelve el resumen.

    `meses` y `presupuesto` conservan el significado que tenían para el
    backfill de Adzuna (el frontend los manda tal cual). `fuentes` limita la
    corrida (p. ej. ['adzuna']); `pais_adzuna` limita Adzuna a un mercado
    (compatibilidad con el `pais=` del endpoint antiguo). Lanza
    `ActualizacionEnCurso` si ya hay una corrida.
    """
    if not _lock.acquire(blocking=False):
        raise ActualizacionEnCurso("Ya hay una actualización del histórico en curso; espera a que termine.")

    inicio = datetime.now(timezone.utc)
    _estado.update(en_curso=True, inicio=inicio.isoformat())
    t0 = time.monotonic()
    quiere = set(fuentes or FUENTES_VALIDAS)
    desconocidas = quiere - set(FUENTES_VALIDAS)
    if desconocidas:
        _lock.release()
        _estado.update(en_curso=False)
        raise ValueError(f"Fuentes desconocidas: {', '.join(sorted(desconocidas))}. Válidas: {', '.join(FUENTES_VALIDAS)}")

    filas: List[Dict[str, Any]] = []
    resumen: Dict[str, Any] = {
        "status": "completed",
        "inicio": inicio.isoformat(),
        "parametros": {
            "meses": meses, "presupuesto": presupuesto,
            "keywords_por_programa": keywords_por_programa,
            "fuentes": sorted(quiere), "pais_adzuna": pais_adzuna,
        },
        "fuentes": filas,
        "serpapi": None,
        "ubicaciones": None,
        "recalculo": None,
        "vacantes_historicas_totales": None,
        "error": None,
    }

    try:
        # 1. Adzuna, mercado por mercado.
        if "adzuna" in quiere:
            mercados = [f["pais"] for f in FUENTES_CATALOGO if f["fuente"] == "adzuna"]
            if pais_adzuna:
                mercados = [pais_adzuna]
            for pais in mercados:
                filas.append(_ejecutar(
                    _fila("adzuna", pais),
                    lambda pais=pais: _paso_adzuna(pais, meses, presupuesto, keywords_por_programa),
                ))

        # 2. Google Jobs (Colombia), con el semáforo por delante.
        if "google_jobs" in quiere:
            try:
                cuota = DEPENDENCIAS["serpapi_cuota"]()
            except Exception as e:
                cuota = {"semaforo": "rojo", "recomendacion": f"No se pudo leer la cuota: {e}"}
            resumen["serpapi"] = cuota
            filas.append(_ejecutar(_fila("google_jobs", "co"), lambda: _paso_google(cuota)))

        # 3. LinkedIn (todos los mercados de PAISES_LATAM).
        if "linkedin" in quiere:
            filas.extend(_pasos_linkedin(keywords_por_programa))

        # 4. Ubicaciones observadas: antes del recálculo, para que apliquen ya.
        try:
            resumen["ubicaciones"] = DEPENDENCIAS["cargar_ubicaciones"](forzar=True)
        except Exception as e:
            resumen["ubicaciones"] = {"error": str(e)[:300]}

        # 5. Recálculo de todas las series + invalidación de cachés.
        try:
            historico = DEPENDENCIAS["leer_historico"]()
            volumenes = DEPENDENCIAS["leer_volumenes"]()
            resumen["recalculo"] = DEPENDENCIAS["recalcular_todo"](historico, volumenes)
            resumen["vacantes_historicas_totales"] = len(historico)
            DEPENDENCIAS["invalidar_caches"]()
        except Exception as e:
            resumen["status"] = "error"
            resumen["error"] = f"Recálculo falló: {type(e).__name__}: {e}"[:300]

        if resumen["status"] != "error":
            problemas = [f for f in filas if f["estado"] in (PARCIAL, OMITIDA, ERROR)]
            resumen["status"] = "parcial" if problemas else "completed"
    finally:
        fin = datetime.now(timezone.utc)
        resumen["fin"] = fin.isoformat()
        resumen["duracion_seg"] = round(time.monotonic() - t0, 1)
        _estado.update(en_curso=False, ultima=resumen)
        _lock.release()

    return resumen
