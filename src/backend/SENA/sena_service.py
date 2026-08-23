"""
sena_service.py — habilidades y conocimientos del CNO 2025 (SENA) por programa.

Es la taxonomía de skills COLOMBIANA y en ESPAÑOL: sustituye la necesidad de
traducir O*NET (normativo, EE.UU.) que arrastraba el proyecto.

⚠️ EL CNO DEL SENA NO ES EL MISMO CÓDIGO QUE `PROGRAMA_CNO`
`Salarios/salarios_service.PROGRAMA_CNO` usa los códigos de la GEIH, que sigue la
**CIUO-08**. El CNO del SENA tiene otra estructura (tipo NOC canadiense): en CIUO
el 21-26 son "Profesionales", mientras que en el SENA los grandes grupos 11-17 son
todos "Directores y gerentes". El código `14` existe en ambos y significa cosas
distintas. Por eso aquí hay un mapeo PROPIO, y no se debe reutilizar el otro.

A cambio, el SENA da MÁS precisión: llega a 4 dígitos ("Analistas de sistemas
informáticos") frente a los 2 dígitos de la GEIH ("Profesionales de TI").
"""

from __future__ import annotations

from typing import Any

from Adzuna.adzuna_service import supabase

TABLA_OCUP = "sena_cno_ocupaciones"
TABLA_ATR = "sena_cno_atributos"

# Programa académico de La Sabana -> código de ocupación del CNO 2025 (SENA).
# Se eligió el código de 4 dígitos más cercano al perfil del egresado; donde no
# existe una ocupación específica se usa el grupo (2-3 dígitos), que es más amplio
# pero honesto. Revisable: es un juicio, no un dato.
PROGRAMA_CNO_SENA: dict[str, str] = {
    # Negocios y administración
    "Administración de Empresas": "17",            # Directores y gerentes de servicios y procesos de negocio
    "Administración & Servicio": "17",
    "Administración de Mercadeo y Logística Internacionales": "5126",  # Profesionales en mercadeo y publicidad
    "Administración de Negocios Internacionales": "1227",              # Comercio exterior
    "Economía y Finanzas Internacionales": "1112",                     # Analistas, asesores y agentes de mercado
    "Economía y Finanzas Internacionales Virtual": "1112",
    "Comportamiento Organizacional": "17",
    # Gastronomía
    "Gastronomía": "6241",                          # Chefs
    # Sociales, comunicación y humanidades
    "Psicología": "3161",                           # Psicólogos
    "Comunicación Audiovisual y Multimedios": "5131",  # Productores y directores artísticos
    "Comunicación Corporativa": "1241",             # Mercadeo, publicidad y comunicaciones
    "Comunicación Social y Periodismo": "5123",     # Periodistas
    "Ciencias Políticas": "4171",                   # Analistas de políticas públicas
    "Derecho": "4112",                              # Abogados
    "Relaciones Internacionales": "4173",           # Investigadores y consultores en asuntos públicos
    "Filosofía": "4162",                            # Filósofos, filólogos y afines
    # Educación
    "Licenciatura en Educación Infantil": "4143",   # Profesores de preescolar
    # Salud
    "Enfermería": "3151",                           # Enfermeros
    "Fisioterapia": "3142",                         # Fisioterapeutas
    "Medicina": "3112",                             # Médicos generales
    # Ingenierías y datos
    "Ciencia de Datos": "2161",                     # Matemáticos, estadísticos y actuarios
    "Ingeniería Civil": "2131",                     # Ingenieros en construcción y obras civiles
    "Ingeniería de Bioproducción": "2121",          # Biólogos y biotecnólogos
    "Ingeniería de Diseño e Innovación": "2154",    # Diseñadores industriales
    "Ingeniería Industrial": "2141",                # Ingenieros industriales y de fabricación
    "Ingeniería Informática": "2173",               # Desarrolladores de aplicaciones informáticas
    "Ingeniería Mecánica": "2132",                  # Ingenieros mecánicos
    "Ingeniería Química": "2135",                   # Ingenieros químicos
    "Ingeniería en Inteligencia Artificial": "2171",  # Analistas de sistemas informáticos
}

_cache_tablas: bool | None = None
_PAGINA = 1000


def _todas_las_filas(consulta_factory) -> list[dict]:
    """Pagina la consulta: Supabase corta en 1000 filas y lo hace en silencio."""
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
    """True si la migración 009 ya corrió."""
    global _cache_tablas
    if _cache_tablas is None:
        try:
            supabase.table(TABLA_ATR).select("id").limit(1).execute()
            _cache_tablas = True
        except Exception:
            _cache_tablas = False
    return _cache_tablas


def invalidar_cache() -> None:
    global _cache_tablas
    _cache_tablas = None


def hay_datos() -> bool:
    if not tablas_disponibles():
        return False
    try:
        r = supabase.table(TABLA_ATR).select("id", count="exact", head=True).execute()
        return (r.count or 0) > 0
    except Exception:
        return False


def skills_de_programa(programa: str, tipo: str = "habilidad",
                       incluir_jerarquia: bool = True) -> dict[str, Any]:
    """
    Habilidades o conocimientos del CNO asociado a un programa.

    `incluir_jerarquia` recoge además los atributos de los niveles superiores del
    código (de '2173' sube a '217' y '21'): el CNO describe lo específico en la
    ocupación y lo general en el grupo, así que sin esto se pierde la mitad.
    """
    vacio = {"items": [], "programa": programa, "tipo": tipo,
             "ocupacion": None, "sin_datos": True}
    if not tablas_disponibles():
        return vacio

    codigo = PROGRAMA_CNO_SENA.get(programa)
    if not codigo:
        return vacio

    # Prefijos: '2173' -> ['2173', '217', '21']
    codigos = [codigo[:n] for n in range(len(codigo), 1, -1)] if incluir_jerarquia else [codigo]

    filas = _todas_las_filas(
        lambda: supabase.table(TABLA_ATR)
        .select("nombre,descripcion,codigo_ocupacion,nivel")
        .eq("tipo", tipo).in_("codigo_ocupacion", codigos)
    )
    if not filas:
        return vacio

    # Un mismo nombre puede venir de varios niveles; se conserva el MÁS ESPECÍFICO
    # (mayor nivel), que es el que mejor describe a esa ocupación.
    por_nombre: dict[str, dict] = {}
    for f in filas:
        n = f["nombre"]
        if n not in por_nombre or f["nivel"] > por_nombre[n]["nivel"]:
            por_nombre[n] = f

    items = sorted(por_nombre.values(), key=lambda x: (-x["nivel"], x["nombre"]))

    try:
        oc = supabase.table(TABLA_OCUP).select("codigo,nombre").eq("codigo", codigo).execute()
        ocupacion = oc.data[0] if oc.data else {"codigo": codigo, "nombre": None}
    except Exception:
        ocupacion = {"codigo": codigo, "nombre": None}

    return {
        "items": [{
            "nombre": i["nombre"],
            "descripcion": i.get("descripcion"),
            "nivel": i["nivel"],
            "especifica": i["nivel"] == len(codigo),  # propia de la ocupación, no heredada
        } for i in items],
        "programa": programa,
        "tipo": tipo,
        "ocupacion": ocupacion,
        "sin_datos": False,
    }


def denominaciones(programa: str) -> list[str]:
    """
    Sinónimos de cargo del CNO para ese programa. Sirven para reconocer títulos de
    vacante en español sin mantener el diccionario a mano de `traducciones.py`.
    """
    if not tablas_disponibles():
        return []
    codigo = PROGRAMA_CNO_SENA.get(programa)
    if not codigo:
        return []
    filas = _todas_las_filas(
        lambda: supabase.table(TABLA_ATR).select("nombre")
        .eq("tipo", "denominacion").eq("codigo_ocupacion", codigo)
    )
    return sorted({f["nombre"] for f in filas})


def catalogo_fuente() -> list[dict]:
    """El CNO del SENA como fuente seleccionable de skills."""
    if not hay_datos():
        return []
    return [{
        "id": "sena:cno",
        "fuente": "sena",
        "pais": None,
        "tipo": "normativo",
        "naturaleza": "normativo",
        "label": "CNO 2025 — SENA",
        "sublabel": "habilidades y conocimientos oficiales de Colombia",
        "dimensiones": ["skill"],
    }]
