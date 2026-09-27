"""
Estado de las fuentes consultadas: cuándo se buscó por última vez en cada una.

QUÉ RESUELVE
------------
El Admin no tenía forma de saber, antes de pulsar "Actualizar histórico", qué
fuente/zona estaba al día y cuál llevaba meses sin consultarse (o nunca se
había consultado). Este módulo lo calcula DESDE LOS DATOS, no desde un
registro aparte que habría que mantener:

  - `vacantes_historicas.recolectado_en` (máximo por fuente/pais): es la tabla
    que alimenta Tendencias, así que es la verdad de "qué hay analizado".
  - `muestreo_volumen.actualizado_en` (máximo por país, Adzuna): el backfill lo
    escribe al terminar cada keyword; si es más reciente, manda.
  - Las tablas crudas de Google Jobs y LinkedIn (`recolectado_en`): reflejan
    la última RECOLECCIÓN aunque la sincronización al histórico no haya
    corrido todavía.
  - La memoria del orquestador (Tendencias/actualizacion.py): si la última
    corrida de este proceso tocó la fuente, se muestra su resultado.

LÍMITE HONESTO: `recolectado_en` tiene `default now()` y los upserts no lo
tocan, así que marca la primera vez que ENTRÓ cada fila. El máximo de la
tabla es, por tanto, "la última vez que llegó una vacante nueva" — para una
fuente que se recolecta completa es lo mismo que la última búsqueda; para una
corrida que no trajo nada nuevo (Adzuna con todas las keywords ya cubiertas)
no se mueve. Por eso se cruza también con `muestreo_volumen` y con la corrida
en memoria.

Se listan TAMBIÉN las fuentes/zonas del catálogo (`FUENTES_CATALOGO`) que
nunca se han consultado: son las que el Admin debe ver como pendientes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from Adzuna.adzuna_service import supabase
from Tendencias.actualizacion import estado_actualizacion
from Tendencias.historical_collector import TABLA_HIST, TABLA_VOL
from Tendencias.tendencias_service import FUENTES_CATALOGO


def _max_fecha(tabla: str, columna: str, filtros: Dict[str, Any]) -> str | None:
    """Valor máximo de una columna de fecha, o None si no hay filas o falla."""
    try:
        q = supabase.table(tabla).select(columna)
        for k, v in filtros.items():
            q = q.eq(k, v)
        r = q.not_.is_(columna, "null").order(columna, desc=True).limit(1).execute()
        if r.data:
            return r.data[0].get(columna)
    except Exception:
        return None
    return None


def _contar(tabla: str, filtros: Dict[str, Any]) -> int | None:
    try:
        q = supabase.table(tabla).select("id", count="exact", head=True)
        for k, v in filtros.items():
            q = q.eq(k, v)
        return q.execute().count or 0
    except Exception:
        return None


def _mas_reciente(*fechas: str | None) -> tuple[str | None, int | None]:
    """(fecha máxima, índice de la que ganó) entre varias ISO (o None)."""
    mejor, idx = None, None
    for i, f in enumerate(fechas):
        if f and (mejor is None or str(f) > str(mejor)):
            mejor, idx = f, i
    return mejor, idx


def estado_fuentes() -> Dict[str, Any]:
    """Última búsqueda por fuente/zona del catálogo, y cuáles nunca se consultaron."""
    ultima_corrida = (estado_actualizacion().get("ultima") or {})
    por_zona_corrida = {
        (f["fuente"], f["pais"]): f for f in (ultima_corrida.get("fuentes") or [])
    }

    salida: List[Dict[str, Any]] = []
    for f in FUENTES_CATALOGO:
        fuente, pais = f["fuente"], f["pais"]
        filas = _contar(TABLA_HIST, {"fuente": fuente, "pais": pais})
        fecha_hist = _max_fecha(TABLA_HIST, "recolectado_en", {"fuente": fuente, "pais": pais})

        # Señales adicionales según la fuente (ver el docstring del módulo).
        candidatos: List[tuple[str, str | None]] = [("vacantes_historicas.recolectado_en", fecha_hist)]
        if fuente == "adzuna":
            candidatos.append(("muestreo_volumen.actualizado_en",
                               _max_fecha(TABLA_VOL, "actualizado_en", {"fuente": "adzuna", "pais": pais})))
        elif fuente == "google_jobs":
            candidatos.append(("vacantes_google.recolectado_en",
                               _max_fecha("vacantes_google", "recolectado_en", {})))
        elif fuente == "linkedin":
            iso = pais[:-3] if pais.endswith("_li") else pais
            candidatos.append(("vacantes_linkedin.recolectado_en",
                               _max_fecha("vacantes_linkedin", "recolectado_en", {"pais": iso})))

        corrida = por_zona_corrida.get((fuente, pais))
        if corrida and ultima_corrida.get("fin") and corrida.get("estado") in ("ok", "sin_cambios", "parcial"):
            candidatos.append(("actualizacion_en_memoria", ultima_corrida["fin"]))

        fecha, idx = _mas_reciente(*[c[1] for c in candidatos])
        salida.append({
            **f,
            "id": f"{fuente}:{pais}",
            "filas_historico": filas,
            "ultima_busqueda": fecha,
            "origen_fecha": candidatos[idx][0] if idx is not None else None,
            "consultada": bool(fecha) or bool(filas),
            "ultima_actualizacion": (
                {"estado": corrida.get("estado"), "filas": corrida.get("filas"),
                 "error": corrida.get("error"), "fin": ultima_corrida.get("fin")}
                if corrida else None
            ),
        })

    return {
        "fuentes": salida,
        "nunca_consultadas": [s["id"] for s in salida if not s["consultada"]],
        "actualizacion": {
            "en_curso": estado_actualizacion().get("en_curso"),
            "inicio": estado_actualizacion().get("inicio"),
            "ultima_fin": ultima_corrida.get("fin"),
            "ultimo_status": ultima_corrida.get("status"),
        },
        "consultado_en": datetime.now(timezone.utc).isoformat(),
    }
