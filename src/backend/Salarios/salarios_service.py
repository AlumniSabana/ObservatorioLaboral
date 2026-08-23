"""
salarios_service.py — capa de servicio del análisis salarial (pivote por programa).

Lee el JSON precomputado por load_geih_salarios.py (salarios de la GEIH agregados
por ocupación CNO) y lo traduce al eje del observatorio: el PROGRAMA académico.

Idea central: la GEIH no conoce "programas", conoce OCUPACIONES (CNO). Cada
programa de La Sabana se mapea al subgrupo CNO de 2 dígitos que agrupa a sus
egresados profesionales (ver PROGRAMA_CNO). El salario de referencia del programa
es la mediana de ese subgrupo.

Granularidad honesta: a 2 dígitos, varias ingenierías comparten el subgrupo 21 y
varias carreras sociales el 26. Es la resolución fiable de la GEIH; bajar a 4
dígitos deja muestras demasiado pequeñas por programa. El frontend lo comunica
como "gran grupo ocupacional", no como un salario exacto del cargo.

El JSON se cachea en memoria: se lee del disco una sola vez por proceso.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_JSON_PATH = Path(__file__).resolve().parent / "data" / "geih_salarios.json"

# ─────────────────────────────────────────────────────────────────────────────
# Mapa PROGRAMA (Sabana) -> subgrupo CNO-2020 de 2 dígitos.
# El código debe existir como clave en `por_cno_subgrupo` del JSON. Elegimos el
# subgrupo PROFESIONAL (2x) que mejor representa al egresado de cada programa.
# Referencia de subgrupos (ver CNO_SUBGRUPOS en load_geih_salarios.py):
#   21 Ciencias e ingeniería · 22 Salud · 23 Enseñanza · 24 Finanzas y admin.
#   25 TIC · 26 Derecho, ciencias sociales y culturales · 14 Gerentes hotelería.
# ─────────────────────────────────────────────────────────────────────────────
PROGRAMA_CNO: dict[str, str] = {
    # Administración / negocios / economía -> Profesionales en finanzas y admin.
    "Administración de Empresas": "24",
    "Administración & Servicio": "24",
    "Administración de Mercadeo y Logística Internacionales": "24",
    "Administración de Negocios Internacionales": "24",
    "Economía y Finanzas Internacionales": "24",
    "Economía y Finanzas Internacionales Virtual": "24",
    "Comportamiento Organizacional": "24",
    # Gastronomía -> Gerentes de hotelería, comercio y otros servicios.
    "Gastronomía": "14",
    # Ciencias sociales, humanas, comunicación y derecho -> subgrupo 26.
    "Psicología": "26",
    "Comunicación Audiovisual y Multimedios": "26",
    "Comunicación Corporativa": "26",
    "Comunicación Social y Periodismo": "26",
    "Ciencias Políticas": "26",
    "Derecho": "26",
    "Relaciones Internacionales": "26",
    "Filosofía": "26",
    # Educación -> Profesionales de la enseñanza.
    "Licenciatura en Educación Infantil": "23",
    # Salud -> Profesionales de la salud.
    "Enfermería": "22",
    "Fisioterapia": "22",
    "Medicina": "22",
    # TIC / datos / IA -> Profesionales de tecnología de la información.
    "Ciencia de Datos": "25",
    "Ingeniería Informática": "25",
    "Ingeniería en Inteligencia Artificial": "25",
    # Resto de ingenierías -> Profesionales de las ciencias y de la ingeniería.
    "Ingeniería Civil": "21",
    "Ingeniería de Bioproducción": "21",
    "Ingeniería de Diseño e Innovación": "21",
    "Ingeniería Industrial": "21",
    "Ingeniería Mecánica": "21",
    "Ingeniería Química": "21",
}

# Cache en memoria del JSON (None = aún no cargado).
_cache: dict[str, Any] | None = None


def _cargar() -> dict[str, Any]:
    """Lee el JSON de disco una vez y lo cachea. Nunca lanza: si falta, degrada."""
    global _cache
    if _cache is None:
        try:
            with open(_JSON_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {
                "meta": {"periodo": "—", "fuente": "sin datos", "mediana_nacional": None,
                         "nota": "Ejecuta load_geih_salarios.py para generar el JSON."},
                "por_cno_grupo": {}, "por_cno_subgrupo": {},
                "spe_rangos": [], "tiene_geih": False,
            }
    return _cache


def limpiar_cache() -> None:
    """Fuerza la relectura del JSON en la próxima llamada (tras regenerarlo)."""
    global _cache
    _cache = None


def _rango_spe(mediana: int | None, spe_rangos: list[dict]) -> dict | None:
    """Devuelve el rango SPE (con min/max) que contiene la mediana dada."""
    if mediana is None:
        return None
    for r in spe_rangos:
        if r.get("min_cop") is not None and r["min_cop"] <= mediana <= r["max_cop"]:
            return r
    return None


def programas_disponibles() -> list[str]:
    """Programas que tienen un salario resoluble (su subgrupo CNO trae datos)."""
    data = _cargar()
    subgrupos = data.get("por_cno_subgrupo", {})
    return [p for p, cod in PROGRAMA_CNO.items() if cod in subgrupos]


def salario_por_programa(programa: str) -> dict[str, Any]:
    """
    Análisis salarial resuelto para un programa: KPIs del subgrupo CNO asociado,
    comparativa contra todos los subgrupos profesionales, y el rango SPE en el
    que cae la mediana. El frontend solo pinta lo que aquí se devuelve.
    """
    data = _cargar()
    meta = data.get("meta", {})
    subgrupos = data.get("por_cno_subgrupo", {})
    spe_rangos = data.get("spe_rangos", [])

    codigo = PROGRAMA_CNO.get(programa)
    stats = subgrupos.get(codigo) if codigo else None

    # Comparativa: todos los subgrupos PROFESIONALES usados por algún programa
    # (los que aparecen en PROGRAMA_CNO), ordenados por mediana. Marca el actual.
    codigos_programa = set(PROGRAMA_CNO.values())
    comparativa = sorted(
        (
            {
                "codigo": cod,
                "nombre": subgrupos[cod]["nombre"],
                "mediana": subgrupos[cod]["mediana"],
                "n": subgrupos[cod]["n"],
                "es_actual": (cod == codigo),
            }
            for cod in codigos_programa
            if cod in subgrupos
        ),
        key=lambda x: x["mediana"],
    )

    mediana = stats["mediana"] if stats else None

    # Escalera educativa DENTRO del grupo ocupacional del programa. Si el subgrupo
    # tiene menos de 2 niveles con muestra fiable, se cae a la escalera nacional
    # (mejor un dato general que uno de una sola barra) y se marca con la bandera.
    por_sub = data.get("por_subgrupo_educacion", {})
    escalera_sub = sorted(por_sub.get(codigo, {}).values(),
                          key=lambda x: x.get("orden", 0)) if codigo else []
    if len(escalera_sub) >= 2:
        nivel_educativo = escalera_sub
        educ_nacional = False
    else:
        nivel_educativo = nivel_educativo_nacional()
        educ_nacional = True

    return {
        "programa": programa,
        "encontrado": stats is not None,
        "cno": {"codigo": codigo, "nombre": stats["nombre"]} if stats else None,
        "kpis": stats,               # mediana/media/p25/p75/p10/p90/n o None
        "comparativa": comparativa,  # para el bar chart horizontal
        "rango_spe": _rango_spe(mediana, spe_rangos),
        "spe_rangos": spe_rangos,
        "nivel_educativo": nivel_educativo,       # escalera del programa (o nacional)
        "nivel_educativo_nacional": educ_nacional,  # True si fue fallback nacional
        "meta": meta,
        "tiene_geih": data.get("tiene_geih", False),
    }


def nivel_educativo_nacional() -> list[dict]:
    """
    Escalera salarial por nivel educativo (agregado NACIONAL, no por programa),
    ordenada de menor a mayor nivel. Responde "cuánto sube el salario con estudios".
    """
    data = _cargar()
    niveles = data.get("por_nivel_educativo", {})
    return sorted(niveles.values(), key=lambda x: x.get("orden", 0))


def resumen_salarios() -> dict[str, Any]:
    """Payload base para la página: meta, programas, rangos SPE y nivel educativo."""
    data = _cargar()
    return {
        "meta": data.get("meta", {}),
        "programas": programas_disponibles(),
        "spe_rangos": data.get("spe_rangos", []),
        "nivel_educativo": nivel_educativo_nacional(),
        "tiene_geih": data.get("tiene_geih", False),
    }
