"""
Ubicaciones observadas en los datos, para limpiar los títulos de cargo.

QUÉ RESUELVE
------------
Los títulos de vacante arrastran la ciudad o el departamento ("Analista de
Datos Bogotá", "Coordinador Comercial - Medellín", "Analista de gestión del
talento Pitalito Huila") y cada variante se contaba como un cargo distinto en
TODAS las vistas que agrupan por cargo (demanda actual, tendencias, geografía,
perfil). `traducciones.canonizar_cargo` ya quitaba una lista curada a mano de
ciudades, pero la lista se quedaba corta: medido en sep-2026, seguían
colándose Huila, Rionegro, Yumbo, Siberia, Marmato, Sibaté, Palmira, Cota…

Este módulo aprende esos nombres de donde ya están:

  1. `DEPARTAMENTOS` de Tendencias/geografia.py (los 33, código DANE -> nombre).
  2. Las ciudades OBSERVADAS en `vacantes_google.city` y `vacantes_linkedin.city`
     (solo lectura; ~380 valores distintos, todos los mercados de LATAM).

y las registra en `traducciones.registrar_ubicaciones()`, que decide cuáles
acepta (descarta países, vocabulario de cargo y valores basura como "Control"
o "Colegio" que vienen en la columna `city`) y las recorta SOLO de los extremos
del título. Por qué solo de los extremos y no en cualquier posición: ver el
bloque `_UBICACIONES_EXTREMO` en traducciones.py.

CUÁNDO SE CARGA
---------------
La primera vez que `traducir_cargo` se ejecuta en el proceso (perezoso, ver
`traducciones._asegurar_ubicaciones`) y cada vez que la actualización del
histórico termina de sincronizar fuentes (Tendencias/actualizacion.py llama a
`cargar_ubicaciones(forzar=True)`): así una ciudad nueva que llegue con una
recolección se empieza a recortar en la misma corrida.

CACHÉ EN DISCO
--------------
La lista se guarda en `_cache_ubicaciones.json` (ignorado por Git, como los
demás `_cache_*.json` de esta carpeta) para que reiniciar el backend no
vuelva a leer ~6.300 filas de Supabase. Se refresca si tiene más de
`CACHE_TTL_DIAS` días o si se pide `forzar=True`. Si la base no responde y no
hay caché, se registran igual los departamentos (no dependen de la red) y se
sigue: la limpieza queda algo más corta, pero nunca rompe la traducción.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from Adzuna.adzuna_service import supabase
from Tendencias.geografia import DEPARTAMENTOS
from traducciones import registrar_ubicaciones, ubicaciones_registradas

CACHE_PATH = Path(__file__).parent / "_cache_ubicaciones.json"
CACHE_TTL_DIAS = 7

# Tablas crudas con columna `city`. Se leen SOLO esas columnas: no hace falta
# la vacante entera para aprender nombres de lugar.
_TABLAS_CIUDAD = ("vacantes_google", "vacantes_linkedin")


def _leer_ciudades_bd() -> List[str]:
    """Valores distintos de `city` en las tablas crudas (paginando de a 1000)."""
    vistas: set[str] = set()
    for tabla in _TABLAS_CIUDAD:
        inicio, pagina = 0, 1000
        while True:
            r = (
                supabase.table(tabla)
                .select("city")
                .not_.is_("city", "null")
                .range(inicio, inicio + pagina - 1)
                .execute()
            )
            if not r.data:
                break
            for f in r.data:
                c = (f.get("city") or "").strip()
                if c:
                    vistas.add(c)
            if len(r.data) < pagina:
                break
            inicio += pagina
    return sorted(vistas)


def _leer_cache() -> Dict[str, Any] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        actualizado = datetime.fromisoformat(d["actualizado_en"])
        if datetime.now(timezone.utc) - actualizado > timedelta(days=CACHE_TTL_DIAS):
            return None
        return d
    except Exception:
        return None  # caché corrupto o formato viejo: se regenera


def _escribir_cache(ciudades: List[str]) -> None:
    """Escritura atómica (temp + reemplazo), por la misma razón que en
    tendencias_service: dos peticiones concurrentes no deben intercalar bytes."""
    try:
        tmp = CACHE_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"actualizado_en": datetime.now(timezone.utc).isoformat(), "ciudades": ciudades},
                fh,
                ensure_ascii=False,
            )
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass  # sin disco escribible seguimos solo con la memoria


def cargar_ubicaciones(forzar: bool = False) -> Dict[str, Any]:
    """Registra departamentos + ciudades observadas en `traducciones`.

    Devuelve un resumen (cuántas se leyeron, cuántas aceptó el filtro de
    `registrar_ubicaciones`, de dónde salieron). Nunca lanza: si la base falla
    se registran al menos los departamentos y se informa `origen='solo_departamentos'`.
    """
    # Los departamentos no dependen de la red: van siempre.
    nuevos_dep = registrar_ubicaciones(DEPARTAMENTOS.values())

    cache = None if forzar else _leer_cache()
    origen = "cache"
    ciudades: List[str] = []
    if cache:
        ciudades = list(cache.get("ciudades") or [])
    else:
        try:
            ciudades = _leer_ciudades_bd()
            _escribir_cache(ciudades)
            origen = "supabase"
        except Exception as e:
            origen = "solo_departamentos"
            print(f"   ⚠ No se pudieron leer las ciudades observadas ({e}); solo departamentos.")

    nuevas_ciu = registrar_ubicaciones(ciudades) if ciudades else 0
    return {
        "origen": origen,
        "departamentos_registrados": nuevos_dep,
        "ciudades_leidas": len(ciudades),
        "ciudades_registradas": nuevas_ciu,
        "ubicaciones_totales": ubicaciones_registradas(),
    }
