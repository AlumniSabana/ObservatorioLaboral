"""
preguntas_service.py — registro y resumen de las preguntas hechas al asistente.

QUÉ RESUELVE
------------
Las preguntas al chat nacen en el navegador (burbuja `src/lib/floating-chat.tsx`
en Perfil ocupacional, Análisis salarial, Cursos, Competencias…, y el chat de
/asistente) y pasan por la ruta /api/chat de Next.js, que las manda al modelo
y no deja rastro. La Dirección de Alumni quiere saber QUÉ se pregunta en cada
sección y CUÁNTO cuesta (tokens y USD estimados) por pregunta y por sesión.

Aquí viven las dos operaciones sobre la tabla `preguntas_asistente`
(migración 011):

    registrar(...)   una fila por pregunta (la llama /api/chat desde el servidor)
    resumen(...)     top de preguntas por categoría + totales (solo Admin)

DEGRADACIÓN: si la migración 011 no está aplicada, `registrar` descarta en
silencio (el chat no puede fallar por la analítica) y `resumen` responde
`disponible=false` con el aviso "pendiente de aplicar migración 011", igual que
hace Informes con `tablas_disponibles()`.

PRIVACIDAD (Ley 1581): no se guarda IP, correo ni identificador de persona.
`sesion_id` es aleatorio y efímero (lo genera el navegador por pestaña). El
texto de la pregunta es libre y PUEDE contener datos personales que el usuario
escriba por su cuenta: se recorta a 500 caracteres y la retención de la tabla
la decide la Universidad (ver la cabecera de la migración 011).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from Adzuna.adzuna_service import supabase

TABLA = "preguntas_asistente"
MIGRACION = "011"

# Categorías que desglosa el dashboard. Cualquier otra cosa cae en 'otras'.
CATEGORIAS = ("perfil_ocupacional", "analisis_salarial", "cursos", "competencias", "empresas", "otras")
ETIQUETAS = {
    "perfil_ocupacional": "Perfil ocupacional",
    "analisis_salarial": "Análisis salarial",
    "cursos": "Cursos",
    "competencias": "Competencias",
    "empresas": "Empresas (asistente)",
    "otras": "Otras páginas",
}

MAX_PREGUNTA = 500
MAX_SESION = 64
_RE_SESION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_cache_tabla: bool | None = None


def tabla_disponible() -> bool:
    """True si la migración 011 ya se ejecutó. Se cachea hasta `invalidar_cache()`."""
    global _cache_tabla
    if _cache_tabla is None:
        try:
            supabase.table(TABLA).select("id").limit(1).execute()
            _cache_tabla = True
        except Exception:
            _cache_tabla = False
    return _cache_tabla


def invalidar_cache() -> None:
    global _cache_tabla
    _cache_tabla = None


def normalizar_pregunta(texto: str) -> str:
    """'¿Qué EMPRESAS contratan?  ' -> 'que empresas contratan'.

    Minúsculas, sin tildes, sin signos de puntuación y con espacios colapsados:
    es la llave con la que se agrupan las "preguntas más realizadas".
    """
    plano = "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    plano = re.sub(r"[^\w\s]", " ", plano)
    return re.sub(r"\s+", " ", plano).strip()


def categoria_de_pagina(pagina: str | None) -> str:
    """Deriva la categoría del título de la página que manda el frontend."""
    p = normalizar_pregunta(pagina or "")
    if "perfil" in p:
        return "perfil_ocupacional"
    if "salari" in p:
        return "analisis_salarial"
    if "curso" in p or "formacion" in p:
        return "cursos"
    if "competencia" in p or "habilidad" in p or "skill" in p:
        return "competencias"
    if "empresa" in p or "cultura" in p:
        return "empresas"
    return "otras"


def registrar(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Guarda una pregunta. Nunca lanza por la tabla ausente: devuelve `guardada=False`."""
    pregunta = (datos.get("pregunta") or "").strip()
    if not pregunta:
        raise ValueError("pregunta vacía")

    categoria = datos.get("categoria") or categoria_de_pagina(datos.get("pagina"))
    if categoria not in CATEGORIAS:
        categoria = categoria_de_pagina(datos.get("pagina")) if datos.get("pagina") else "otras"

    sesion = (datos.get("sesion_id") or "").strip()[:MAX_SESION]
    if sesion and not _RE_SESION.match(sesion):
        sesion = ""  # no se acepta nada que no sea un id opaco

    def _entero(v: Any) -> int | None:
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    fila = {
        "categoria": categoria,
        "pagina": (datos.get("pagina") or None) and str(datos["pagina"])[:120],
        "pregunta": pregunta[:MAX_PREGUNTA],
        "pregunta_normalizada": normalizar_pregunta(pregunta)[:MAX_PREGUNTA],
        "sesion_id": sesion or None,
        "modelo": (datos.get("modelo") or None) and str(datos["modelo"])[:80],
        "tokens_entrada": _entero(datos.get("tokens_entrada")),
        "tokens_salida": _entero(datos.get("tokens_salida")),
        "costo_usd_estimado": (
            float(datos["costo_usd_estimado"]) if datos.get("costo_usd_estimado") is not None else None
        ),
    }

    if not tabla_disponible():
        return {"guardada": False, "motivo": f"pendiente de aplicar migración {MIGRACION}", "categoria": categoria}
    try:
        supabase.table(TABLA).insert(fila).execute()
        return {"guardada": True, "categoria": categoria}
    except Exception as e:
        # Un fallo de escritura tampoco debe romper el chat.
        invalidar_cache()
        return {"guardada": False, "motivo": str(e)[:200], "categoria": categoria}


def _leer_todo(dias: int | None) -> List[Dict[str, Any]]:
    filas: List[Dict[str, Any]] = []
    inicio, pagina = 0, 1000
    while True:
        q = (
            supabase.table(TABLA)
            .select("categoria,pregunta,pregunta_normalizada,sesion_id,modelo,"
                    "tokens_entrada,tokens_salida,costo_usd_estimado,creado_en")
            .order("id")
            .range(inicio, inicio + pagina - 1)
        )
        if dias:
            desde = datetime.now(timezone.utc).timestamp() - dias * 86400
            q = q.gte("creado_en", datetime.fromtimestamp(desde, tz=timezone.utc).isoformat())
        r = q.execute()
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < pagina:
            break
        inicio += pagina
    return filas


def resumen(top: int = 10, dias: int | None = None) -> Dict[str, Any]:
    """Top de preguntas por categoría y totales (tokens, costo, sesiones)."""
    if not tabla_disponible():
        return {
            "disponible": False,
            "motivo": f"pendiente de aplicar migración {MIGRACION} ({TABLA})",
            "categorias": [],
            "totales": None,
        }

    filas = _leer_todo(dias)

    por_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for f in filas:
        por_cat[f.get("categoria") or "otras"].append(f)

    def _suma(fs: List[Dict[str, Any]], campo: str) -> float:
        return sum(float(f.get(campo) or 0) for f in fs)

    categorias = []
    for cat in CATEGORIAS:
        fs = por_cat.get(cat, [])
        conteo: Counter = Counter()
        ejemplo: Dict[str, str] = {}
        ultima: Dict[str, str] = {}
        for f in fs:
            clave = f.get("pregunta_normalizada") or normalizar_pregunta(f.get("pregunta") or "")
            if not clave:
                continue
            conteo[clave] += 1
            # Se muestra la redacción MÁS RECIENTE de esa pregunta.
            if f.get("creado_en", "") >= ultima.get(clave, ""):
                ultima[clave] = f.get("creado_en", "")
                ejemplo[clave] = f.get("pregunta") or clave
        categorias.append({
            "categoria": cat,
            "etiqueta": ETIQUETAS[cat],
            "total": len(fs),
            "distintas": len(conteo),
            "sesiones": len({f.get("sesion_id") for f in fs if f.get("sesion_id")}),
            "tokens_entrada": int(_suma(fs, "tokens_entrada")),
            "tokens_salida": int(_suma(fs, "tokens_salida")),
            "costo_usd_estimado": round(_suma(fs, "costo_usd_estimado"), 6),
            "top": [
                {"pregunta": ejemplo[k], "veces": n, "ultima_vez": ultima[k]}
                for k, n in conteo.most_common(top)
            ],
        })

    sesiones = {f.get("sesion_id") for f in filas if f.get("sesion_id")}
    costo_total = _suma(filas, "costo_usd_estimado")
    return {
        "disponible": True,
        "dias": dias,
        "categorias": categorias,
        "totales": {
            "preguntas": len(filas),
            "sesiones": len(sesiones),
            "tokens_entrada": int(_suma(filas, "tokens_entrada")),
            "tokens_salida": int(_suma(filas, "tokens_salida")),
            "costo_usd_estimado": round(costo_total, 6),
            "costo_usd_por_sesion": round(costo_total / len(sesiones), 6) if sesiones else None,
            "costo_usd_por_pregunta": round(costo_total / len(filas), 6) if filas else None,
            "con_tokens": sum(1 for f in filas if f.get("tokens_salida") is not None),
            "modelos": dict(Counter(f.get("modelo") or "desconocido" for f in filas)),
        },
        "nota": (
            "Costo ESTIMADO con precios configurados por variable de entorno; no es la factura. "
            "El texto de las preguntas es libre y puede contener datos personales (Ley 1581): "
            "definir retención."
        ),
    }
