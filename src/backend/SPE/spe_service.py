"""
spe_service.py — el SPE (Colombia) como fuente de skills del Observatorio.

Consulta las tablas que llena `SPE/cargar_anexos.py` y las expone con la misma
forma que el resto de fuentes, para que aparezcan en el selector junto a Adzuna,
O*NET y los informes PDF.

LA VENTAJA FRENTE A O*NET
El ranking de skills de la página es DERIVADO: importancia normativa de O*NET
(EE.UU.) × demanda de cada programa. Esto es lo contrario: competencias realmente
pedidas en vacantes colombianas, contadas sobre ~1,8 millones de ofertas.

CÓMO SE CONECTA CON LOS PROGRAMAS
El CIUO de 2 dígitos del SPE es la misma taxonomía que el CNO que ya usa
`Salarios/salarios_service.PROGRAMA_CNO`. Un programa → su código → sus
competencias. No hace falta ningún mapeo nuevo.
"""

from __future__ import annotations

from typing import Any

from Adzuna.adzuna_service import supabase

TABLA_OCUP = "spe_ocupaciones"
TABLA_COMP = "spe_competencias"

# Cómo se presenta cada categoría del anexo y si es competencia o herramienta.
#
# 'digital_basico' ("Conocimiento digital básico") va como TECNOLOGÍA, no
# competencia: sus términos son "Software", "Web", "Redes", "Telecomunicaciones",
# "Informática"... — conocimiento técnico, no habilidad blanda/transversal. Antes
# estaba junto a 'transversal' y esos términos salían mezclados con cosas como
# "Trabajo en equipo" bajo "Competencias", que es justo lo que confundía en la
# presentación (feedback del 12 ago 2026, corregido antes de la entrega).
CATEGORIAS = {
    "transversal": ("Competencias transversales", "competencia"),
    "digital": ("Competencias digitales", "competencia"),
    "digital_basico": ("Conocimiento digital básico", "tecnologia"),
    "ofimatica": ("Ofimática", "tecnologia"),
    "programa": ("Programas y herramientas", "tecnologia"),
    "lenguaje": ("Lenguajes de programación", "tecnologia"),
    "practica": ("Prácticas y procesos", "tecnologia"),
    "habilidad_digital": ("Habilidades digitales", "tecnologia"),
}

# Qué categorías alimentan cada pestaña de la página de Skills.
#
# OJO con 'digital': esa hoja del anexo es un RESUMEN cuyas columnas son los
# nombres de las demás hojas ("Conocimiento en ofimática", "Lenguajes"…), no
# competencias. Incluirla metería nombres de categoría en el ranking y contaría
# dos veces lo mismo, así que se deja fuera de ambas listas a propósito.
_POR_TIPO = {
    "competencia": ["transversal"],
    "tecnologia": ["ofimatica", "programa", "lenguaje", "practica", "habilidad_digital", "digital_basico"],
}

_cache_tablas: bool | None = None
_PAGINA = 1000


def _todas_las_filas(consulta_factory) -> list[dict]:
    """
    Trae TODAS las filas de una consulta, paginando.

    Supabase corta en 1000 filas por petición. Sin paginar, un ranking calculado
    sobre 123k filas se construía en realidad con las primeras 1000 y salía mal
    sin dar ningún error: el tipo de fallo más difícil de detectar.
    """
    filas: list[dict] = []
    inicio = 0
    while True:
        try:
            r = consulta_factory().range(inicio, inicio + _PAGINA - 1).execute()
        except Exception:
            break
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < _PAGINA:
            break
        inicio += _PAGINA
    return filas


def tablas_disponibles() -> bool:
    """True si la migración 007 ya corrió. Cachea el resultado."""
    global _cache_tablas
    if _cache_tablas is None:
        try:
            supabase.table(TABLA_COMP).select("id").limit(1).execute()
            _cache_tablas = True
        except Exception:
            _cache_tablas = False
    return _cache_tablas


def invalidar_cache() -> None:
    global _cache_tablas
    _cache_tablas = None


def hay_datos() -> bool:
    """True si además de existir, las tablas tienen filas cargadas."""
    if not tablas_disponibles():
        return False
    try:
        r = supabase.table(TABLA_COMP).select("id", count="exact", head=True).execute()
        return (r.count or 0) > 0
    except Exception:
        return False


def _ciuo_de_programa(programa: str) -> str | None:
    """Código CIUO/CNO asociado al programa académico."""
    from Salarios.salarios_service import PROGRAMA_CNO
    return PROGRAMA_CNO.get(programa)


def competencias(programa: str = "TODOS", tipo: str = "competencia",
                 top: int = 20) -> dict[str, Any]:
    """
    Ranking de competencias observadas en vacantes colombianas.

    Con `programa` concreto se restringe al CIUO de ese programa; con 'TODOS' se
    agrega el mercado colombiano completo. `tipo` elige entre competencias
    (blandas/digitales) y tecnologías (herramientas, lenguajes…).
    """
    vacio = {"items": [], "total_menciones": 0, "programa": programa,
             "tipo": tipo, "sin_datos": True}
    if not tablas_disponibles():
        return vacio

    categorias = _POR_TIPO.get(tipo, _POR_TIPO["competencia"])
    ciuo = None
    if programa != "TODOS":
        ciuo = _ciuo_de_programa(programa)
        if not ciuo:
            return vacio

    def consulta():
        q = (supabase.table(TABLA_COMP)
             .select("competencia,categoria,menciones,ciuo2")
             .in_("categoria", categorias))
        return q.eq("ciuo2", ciuo) if ciuo else q

    filas = _todas_las_filas(consulta)

    if not filas:
        return vacio

    acum: dict[str, dict] = {}
    for f in filas:
        nombre = f["competencia"]
        e = acum.setdefault(nombre, {"nombre": nombre, "categoria": f["categoria"], "menciones": 0})
        e["menciones"] += int(f.get("menciones") or 0)

    ordenados = sorted(acum.values(), key=lambda x: -x["menciones"])[:top]
    maximo = ordenados[0]["menciones"] if ordenados else 1

    return {
        "items": [{
            "nombre": it["nombre"],
            "categoria": CATEGORIAS.get(it["categoria"], (it["categoria"], ""))[0],
            "menciones": it["menciones"],
            # Índice 0-100 relativo al líder, igual que el ranking derivado, para
            # que ambas vistas se lean con la misma escala.
            "indice": round(it["menciones"] / maximo * 100, 1),
        } for it in ordenados],
        "total_menciones": sum(v["menciones"] for v in acum.values()),
        "programa": programa,
        "tipo": tipo,
        "sin_datos": False,
    }


def ocupaciones_top(top: int = 15, departamento: str | None = None) -> dict[str, Any]:
    """Ocupaciones con más ofertas en Colombia (agregado del periodo cargado)."""
    if not tablas_disponibles():
        return {"items": [], "total": 0}
    def consulta():
        q = supabase.table(TABLA_OCUP).select("ciuo2,ocupacion,ofertas")
        return q.eq("departamento", departamento) if departamento else q

    filas = _todas_las_filas(consulta)

    acum: dict[str, dict] = {}
    sin_clasificar = 0
    for f in filas:
        clave = f["ciuo2"]
        ofertas = int(f.get("ofertas") or 0)
        # Las vacantes que el SPE no logró clasificar se cuentan aparte: no son
        # una ocupación y mezclarlas encabezaría el ranking con un hueco.
        if clave == "ND":
            sin_clasificar += ofertas
            continue
        e = acum.setdefault(clave, {"ciuo2": clave, "ocupacion": f.get("ocupacion"), "ofertas": 0})
        if not e["ocupacion"]:
            e["ocupacion"] = f.get("ocupacion")
        e["ofertas"] += ofertas

    items = sorted(acum.values(), key=lambda x: -x["ofertas"])[:top]
    clasificadas = sum(v["ofertas"] for v in acum.values())
    return {
        "items": items,
        "total": clasificadas,
        "sin_clasificar": sin_clasificar,
        "total_anexo": clasificadas + sin_clasificar,
    }


def tendencias(dimension: str = "transversal", top: int = 8) -> dict[str, Any]:
    """
    Serie mensual nacional del SPE: cómo se movió cada término mes a mes.

    Es la primera tendencia OBSERVADA de Colombia en el Observatorio (las demás
    vienen de mercados extranjeros o son derivadas de O*NET). `dimension`:
    'ocupacion', 'transversal' o 'digital'.

    Se ordenan las series por su volumen total y se devuelven las `top` mayores,
    para no dibujar 15 líneas ilegibles.
    """
    vacio = {"periodos": [], "series": [], "dimension": dimension, "sin_datos": True}
    try:
        filas = _todas_las_filas(
            lambda: supabase.table("spe_tendencias")
            .select("periodo,termino,valor").eq("dimension", dimension).order("periodo")
        )
    except Exception:
        return vacio
    if not filas:
        return vacio

    periodos = sorted({f["periodo"] for f in filas})
    por_termino: dict[str, dict[str, float]] = {}
    for f in filas:
        por_termino.setdefault(f["termino"], {})[f["periodo"]] = float(f.get("valor") or 0)

    elegidos = sorted(por_termino.items(), key=lambda kv: -sum(kv[1].values()))[:top]

    return {
        "periodos": periodos,
        "series": [
            {"nombre": nombre, "valores": [meses.get(p, 0.0) for p in periodos]}
            for nombre, meses in elegidos
        ],
        "dimension": dimension,
        "sin_datos": False,
    }


def catalogo_fuente() -> list[dict]:
    """
    El SPE como entrada del selector de fuentes. Lista vacía si no hay datos
    cargados, para que la opción no aparezca prometiendo algo que no existe.
    """
    if not hay_datos():
        return []
    try:
        r = supabase.table(TABLA_COMP).select("anio").order("anio", desc=True).limit(1).execute()
        anio = r.data[0]["anio"] if r.data else None
    except Exception:
        anio = None

    return [{
        "id": "spe:co",
        "fuente": "spe",
        "pais": None,
        "tipo": "vacantes",
        "naturaleza": "observado",
        "granularidad_temporal": "mensual",
        "label": "SPE — Colombia",
        "sublabel": f"competencias observadas en vacantes{f' · {anio}' if anio else ''}",
        "dimensiones": ["skill"],
    }]
