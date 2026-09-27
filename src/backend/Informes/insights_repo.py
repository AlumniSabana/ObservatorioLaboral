"""
insights_repo.py — persistencia de los insights generados (tabla
`insights_generados`, migración 012).

Existe como módulo aparte porque lo usan DOS generadores distintos
(insights_service.py para los individuales e insights_conjuntos.py para los
conjuntos) y UN lector público (GET /informes/insights-generados, que alimenta
la vista de Usuario). Ninguno de ellos debería saber cómo se guarda un insight.

DEGRADACIÓN: la migración 012 se aplica a mano en Supabase, así que el backend
puede estar corriendo sin la tabla. En ese caso `guardar()` devuelve None y
`listar()` devuelve [] — nunca lanzan — y los endpoints responden
`persistido: false` / `disponible: false` para que la UI lo avise. Mismo patrón
que `informes_service.tablas_disponibles()`.
"""

from __future__ import annotations

from typing import Any

from Adzuna.adzuna_service import supabase

TABLA_INSIGHTS = "insights_generados"

TIPO_INDIVIDUAL = "individual"
TIPO_CONJUNTO = "conjunto"
TIPOS = (TIPO_INDIVIDUAL, TIPO_CONJUNTO)

AVISO_SIN_TABLA = (
    "Los insights no se están guardando: falta aplicar la migración 012 "
    "(src/backend/migrations/012_insights_generados.sql) en Supabase."
)

_cache_tabla: bool | None = None


def tabla_disponible() -> bool:
    """True si la migración 012 ya se ejecutó. Se cachea hasta `invalidar_cache()`."""
    global _cache_tabla
    if _cache_tabla is None:
        try:
            supabase.table(TABLA_INSIGHTS).select("id").limit(1).execute()
            _cache_tabla = True
        except Exception:
            _cache_tabla = False
    return _cache_tabla


def invalidar_cache() -> None:
    """Reevalúa si la tabla existe (llamar tras correr la migración)."""
    global _cache_tabla
    _cache_tabla = None


def snapshot_informes(informes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Metadatos mínimos que se congelan junto al insight.

    El insight describe lo que decían esos documentos EN ESE MOMENTO; si el
    informe se retira o se reactiva con otro título, el texto guardado sigue
    siendo legible y trazable sin depender de la fila viva de `informes`.
    """
    return [{
        "id": i["id"],
        "titulo": i.get("titulo"),
        "editor": i.get("editor"),
        "anio_referencia": i.get("anio_referencia"),
    } for i in informes]


def guardar(
    tipo: str,
    informe_ids: list[str],
    titulo: str,
    contenido: str,
    modelo: str,
    informes: list[dict[str, Any]] | None = None,
    motivo_grupo: str | None = None,
    creado_por: str | None = None,
) -> dict[str, Any] | None:
    """
    Inserta el insight y devuelve la fila creada, o None si la tabla no existe.

    No lanza por falta de tabla: generar el texto ya costó una llamada al
    modelo y el usuario debe verlo aunque no se pueda guardar.
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo debe ser uno de {TIPOS}, no '{tipo}'")
    if not tabla_disponible():
        return None
    fila = {
        "tipo": tipo,
        "informe_ids": list(informe_ids),
        "informes": snapshot_informes(informes or []),
        "titulo": titulo,
        "contenido": contenido,
        "modelo": modelo,
        "motivo_grupo": motivo_grupo,
        "creado_por": creado_por,
    }
    r = supabase.table(TABLA_INSIGHTS).insert(fila).execute()
    return r.data[0] if r.data else None


def listar(
    informe_id: str | None = None,
    tipo: str | None = None,
    limite: int = 50,
) -> list[dict[str, Any]]:
    """
    Insights guardados, más recientes primero.

    `informe_id` filtra los que MENCIONAN ese informe (`informe_ids @> {id}`):
    así la vista de Usuario encuentra tanto el insight individual de su PDF como
    uno individual generado sobre varios informes que lo incluye.
    """
    if not tabla_disponible():
        return []
    q = supabase.table(TABLA_INSIGHTS).select("*").order("creado_en", desc=True).limit(limite)
    if tipo in TIPOS:
        q = q.eq("tipo", tipo)
    if informe_id:
        q = q.contains("informe_ids", [informe_id])
    return q.execute().data or []
