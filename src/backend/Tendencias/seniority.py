"""
Detección del nivel de experiencia (seniority) a partir del título de la vacante.

Por qué desde el título y no desde la descripción: Adzuna trunca las
descripciones a 500 caracteres (ver README §9.7), pero el título sí lleva el
nivel cuando existe. Medido sobre 8.336 vacantes históricas reales:

    senior            17.5%   (sr, senior, lead, principal, staff, head, director…)
    graduado           3.9%   (entry level, graduate, intern, trainee…)
    junior             3.4%   (jr, junior, associate)
    no especificado   76.2%

OJO: `no_especificado` NO es "sin dato". La inmensa mayoría de las vacantes
mid-level simplemente no ponen nivel en el título. Se etiqueta como tal y no se
reparte ni se imputa: inventar un nivel sería peor que no tenerlo.

IMPORTANTE: hay que llamar a `detectar_seniority()` sobre el título CRUDO. La
función `normalize_title()` de Adzuna/adzuna_service.py borra justamente estas
palabras para poder agrupar cargos ('Senior Software Engineer' y 'Software
Engineer II' -> 'software engineer'), así que si se ejecuta antes, la señal
desaparece.
"""

from __future__ import annotations

import re
from typing import Final

SENIOR: Final = "senior"
JUNIOR: Final = "junior"
GRADUADO: Final = "graduado"
NO_ESPECIFICADO: Final = "no_especificado"

NIVELES: Final = (SENIOR, JUNIOR, GRADUADO, NO_ESPECIFICADO)

# Etiquetas legibles para el frontend.
ETIQUETAS: Final = {
    SENIOR: "Senior",
    JUNIOR: "Junior",
    GRADUADO: "Recién graduado",
    NO_ESPECIFICADO: "No especificado",
}

# El orden importa: se evalúa de menos a más experiencia, porque un título como
# "Graduate Engineer, Senior Programme" debe ganar 'graduado' (el nivel del
# puesto) antes que 'senior' (que ahí califica al programa, no a la persona).
_PATRONES: Final = (
    (
        GRADUADO,
        re.compile(
            r"\b(entry[\s\-]?level|new[\s\-]?grad(uate)?|grad(uate)?\s+(program|scheme|role|trainee)"
            r"|graduate|intern|internship|trainee|apprentice(ship)?|practicante|pasante)\b",
            re.IGNORECASE,
        ),
    ),
    (
        JUNIOR,
        re.compile(r"\b(jr\.?|junior|associate|assoc\.?)\b", re.IGNORECASE),
    ),
    (
        SENIOR,
        re.compile(
            r"\b(sr\.?|senior|lead|principal|staff|head\s+of|chief|director|vp"
            r"|vice\s+president|manager\s+iii|expert|iii|iv)\b",
            re.IGNORECASE,
        ),
    ),
)


def detectar_seniority(titulo: str | None) -> str:
    """Nivel de experiencia inferido del título crudo.

    Devuelve uno de NIVELES. Nunca lanza: un título vacío es NO_ESPECIFICADO.
    """
    if not titulo or not isinstance(titulo, str):
        return NO_ESPECIFICADO

    for nivel, patron in _PATRONES:
        if patron.search(titulo):
            return nivel

    return NO_ESPECIFICADO
