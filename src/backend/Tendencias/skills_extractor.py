"""
Extracción de skills a partir del texto de una vacante.

Portado del proyecto Reto-Alumni (`extract_skills.py` + `build_tendencias.py`),
adaptado para leer de Supabase en vez de CSVs.

Cómo funciona
-------------
`diccionario_skills.json` (copiado de Reto-Alumni) contiene cuatro grupos:
  - blandas       : 35 competencias O*NET, con `mapping_en` (español -> inglés)
  - tecnicas      : 171 herramientas/tecnologías (iguales en ambos idiomas)
  - conocimientos : 70 áreas de conocimiento (Ocupacol, español)
  - destrezas     : 40 destrezas (Ocupacol, español)

Se construye un regex con límites de palabra por término y se busca sobre el
texto normalizado (minúsculas, sin tildes). Cada skill se cuenta UNA vez por
vacante: nos interesa "cuántas vacantes la piden", no cuántas veces la repiten.

Los nombres se canonicalizan a español: las vacantes de Adzuna están en inglés,
así que `Critical Thinking` se guarda como `pensamiento crítico`. Así una futura
fuente en español (Google Jobs Colombia) agrega sobre la MISMA skill.

Extensión futura (Claude)
-------------------------
`extraer_skills()` recibe el texto y devuelve un set de nombres canónicos. Para
cambiar a extracción con IA basta con implementar otra función con esa misma
firma y enrutarla en `extraer_skills_lote()`. La capa de tendencias no cambia.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

DICT_PATH = Path(__file__).parent / "diccionario_skills.json"

# Categorías que expone el dashboard (mismas que en Reto-Alumni)
CATEGORIAS = ("técnica", "blanda", "conocimiento", "destreza")


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar de forma robusta."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def cargar_diccionario() -> dict:
    with open(DICT_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Nombre canónico (inglés -> español) y categoría
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _mapa_canonico() -> Dict[str, str]:
    """Mapa 'cualquier variante en minúsculas' -> 'nombre canónico'.

    Las soft skills se canonicalizan al español (es el idioma del dashboard);
    las técnicas conservan su nombre original con la capitalización del
    diccionario. Réplica de `construir_mapping_en_es()` de build_tendencias.py.
    """
    d = cargar_diccionario()
    mapa: Dict[str, str] = {}

    # mapping_en = {término_es: término_en}. Ambos apuntan al término en español.
    for es_term, en_term in d["blandas"]["mapping_en"].items():
        mapa[en_term.lower()] = es_term
        mapa[es_term.lower()] = es_term

    for skill in d["tecnicas"]["terminos"]:
        mapa[skill.lower()] = skill

    for skill in d["ocupacol"]["conocimientos"] + d["ocupacol"]["destrezas"]:
        mapa[skill.lower()] = skill

    return mapa


def canonicalizar(skill: str) -> str:
    return _mapa_canonico().get(skill.lower().strip(), skill)


@lru_cache(maxsize=1)
def _mapa_categorias() -> Dict[str, str]:
    """Nombre canónico normalizado -> categoría."""
    d = cargar_diccionario()
    cats: Dict[str, str] = {}

    for skill in d["tecnicas"]["terminos"]:
        cats[normalizar(skill)] = "técnica"
    for skill in d["ocupacol"]["conocimientos"]:
        cats[normalizar(skill)] = "conocimiento"
    for skill in d["ocupacol"]["destrezas"]:
        cats[normalizar(skill)] = "destreza"
    # Las blandas van al final: si una palabra aparece en varios grupos,
    # la clasificación O*NET (competencia) es la más específica.
    for skill in d["blandas"]["terminos_es"]:
        cats[normalizar(skill)] = "blanda"

    return cats


def get_categoria(skill: str) -> str:
    return _mapa_categorias().get(normalizar(skill), "destreza")


# ---------------------------------------------------------------------------
# Motor de extracción por diccionario
# ---------------------------------------------------------------------------

@lru_cache(maxsize=2)
def _patrones(idioma: str) -> Tuple[Tuple[str, re.Pattern], ...]:
    """Patrones (término, regex) para el idioma dado.

    idioma='en' -> nombres O*NET en inglés + tecnologías (vacantes de Adzuna US)
    idioma='es' -> lista completa en español (Ocupacol + O*NET traducido + tech)
    """
    d = cargar_diccionario()

    if idioma == "en":
        terminos = sorted(set(
            list(d["blandas"]["mapping_en"].values()) + d["tecnicas"]["terminos"]
        ))
    else:
        terminos = d["busqueda_rapida"]

    compilados = []
    for termino in terminos:
        # \b evita falsos positivos: "R" no debe encajar dentro de "trabajar".
        patron = re.compile(r"\b" + re.escape(normalizar(termino)) + r"\b")
        compilados.append((termino, patron))
    return tuple(compilados)


def extraer_skills(texto: str, idioma: str = "en") -> Set[str]:
    """Skills canónicas presentes en el texto. Una skill cuenta una sola vez."""
    if not isinstance(texto, str) or not texto.strip():
        return set()

    texto_norm = normalizar(texto)
    return {
        canonicalizar(termino)
        for termino, patron in _patrones(idioma)
        if patron.search(texto_norm)
    }


def extraer_skills_lote(
    textos: Iterable[str],
    idioma: str = "en",
    metodo: str = "diccionario",
) -> List[Set[str]]:
    """Extrae skills de varios textos.

    `metodo` existe como punto de extensión: hoy solo 'diccionario'. Cuando se
    implemente la extracción con Claude, se añade aquí sin tocar el resto.
    """
    if metodo != "diccionario":
        raise NotImplementedError(
            f"Método de extracción '{metodo}' no implementado. "
            "Hoy solo está disponible 'diccionario'."
        )
    return [extraer_skills(t, idioma) for t in textos]
