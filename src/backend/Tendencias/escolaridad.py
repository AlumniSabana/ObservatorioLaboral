"""
Nivel de escolaridad — clasificación OCUPACIONAL (no de experiencia) inferida
del título de la vacante.

Es un filtro DISTINTO de "Nivel de experiencia" (Tendencias/seniority.py):
aquel mide SENIORITY (¿cuánta experiencia pide el puesto?, título con
"senior"/"junior"...); este mide a qué TIPO de ocupación pertenece el cargo,
usando los Grandes Grupos de la Clasificación Internacional Uniforme de
Ocupaciones (CIUO-08 / CNO colombiana) —la misma taxonomía que ya usa
Salarios/salarios_service.py para pivotar GEIH por programa, y de la que ya
hay tablas CNO 2025 del SENA en Supabase—, más dos categorías propias del
observatorio (Junior y Recién Graduado) que sí son de experiencia y se
mantienen porque el título las señala igual de bien que el nivel ocupacional.

Se excluyen a propósito los Grandes Grupos 0 (fuerzas armadas) y 6
(agropecuario/pesquero) de CIUO-08: no aplican a los programas académicos de
la Sabana.

Alcance: solo alimenta `Tendencias/demanda_actual.py` (las 4 gráficas "más
demandados" de Tendencias), NO el motor de tendencias temporales
(`tendencias_service.py`/`tendencias_observaciones`) — cruzar un quinto eje
ahí multiplicaría las combinaciones precalculadas sin necesidad, cuando el
pedido original era sobre esas gráficas de demanda actual.

Como en seniority.py: es heurística sobre el TÍTULO crudo (Adzuna trunca la
descripción a 500 caracteres), así que hay margen de error y un título que no
matchea ningún patrón queda en NO_ESPECIFICADO — no se fuerza a los 10 grupos
ni se reparte (ver la nota de seniority.py sobre por qué "no especificado" no
es "sin dato").
"""

from __future__ import annotations

import re
from typing import Final

DIRECTIVO: Final = "directivo"
PROFESIONAL: Final = "profesional"
TECNICO: Final = "tecnico"
APOYO_ADMIN: Final = "apoyo_administrativo"
SERVICIOS_VENTAS: Final = "servicios_ventas"
OFICIOS: Final = "oficios"
OPERADORES: Final = "operadores"
ELEMENTAL: Final = "elemental"
JUNIOR: Final = "junior"
GRADUADO: Final = "graduado"
NO_ESPECIFICADO: Final = "no_especificado"

# Los 10 seleccionables en el dropdown. NO_ESPECIFICADO existe como fallback de
# clasificación (ver detectar_escolaridad) pero no se ofrece como opción.
NIVELES: Final = (
    DIRECTIVO, PROFESIONAL, TECNICO, APOYO_ADMIN, SERVICIOS_VENTAS,
    OFICIOS, OPERADORES, ELEMENTAL, JUNIOR, GRADUADO,
)

ETIQUETAS: Final = {
    DIRECTIVO: "Directores y gerentes",
    PROFESIONAL: "Profesionales, científicos e intelectuales",
    TECNICO: "Técnicos y profesionales de nivel medio",
    APOYO_ADMIN: "Personal de apoyo administrativo",
    SERVICIOS_VENTAS: "Trabajadores de los servicios y vendedores de comercios y mercados",
    OFICIOS: "Oficiales, operarios, artesanos y oficios relacionados",
    OPERADORES: "Operadores de instalaciones y máquinas y ensambladores",
    ELEMENTAL: "Ocupaciones elementales",
    JUNIOR: "Junior",
    GRADUADO: "Recién graduado",
    NO_ESPECIFICADO: "No especificado",
}

# El orden importa (se evalúa de arriba a abajo, gana el primer match):
#   1) Graduado/Junior primero: son señal de EXPERIENCIA, no de tipo de puesto,
#      y deben ganarle a la ocupación (p. ej. "Graduate Engineer" es
#      'graduado', no 'profesional' — igual criterio que seniority.py).
#   2) Directivo antes que Profesional/Técnico: "Engineering Manager" es
#      directivo (CIUO-08 clasifica todo cargo "manager"/"gerente" en el Gran
#      Grupo 1, sea cual sea el área), no "profesional" (que atraparía
#      "engineer" primero si fuera antes).
#   3) Apoyo administrativo antes que Profesional/Técnico, para que "Assistant"
#      compuesto ("Administrative Assistant") no caiga en el catch-all
#      genérico de Técnico.
#   4) Oficios/Operadores/Elemental al final: son los patrones más genéricos en
#      inglés ("operator", "worker") y matchearían de más si fueran antes.
_PATRONES: Final = (
    (
        GRADUADO,
        re.compile(
            r"\b(entry[\s\-]?level|new[\s\-]?grad(uate)?|grad(uate)?\s+(program|scheme|role|trainee)"
            r"|graduate|intern|internship|trainee|apprentice(ship)?|practicante|pasante|"
            r"reci[eé]n\s+graduad[oa])\b",
            re.IGNORECASE,
        ),
    ),
    (
        JUNIOR,
        re.compile(r"\b(jr\.?|junior|associate|assoc\.?)\b", re.IGNORECASE),
    ),
    (
        DIRECTIVO,
        re.compile(
            r"\b(director|directora|gerente|ceo|cfo|coo|cto|cio|chief|"
            r"vice\s?president|vicepresidente|vp|president|presidente|"
            r"head\s+of|jefe|manager)\b",
            re.IGNORECASE,
        ),
    ),
    (
        APOYO_ADMIN,
        re.compile(
            r"\b(administrative|administrativ[oa]|clerk|secretary|secretaria|"
            r"receptionist|recepcionista|data\s?entry|office\s+assistant|"
            r"auxiliar\s+administrativ[oa]|asistente\s+administrativ[oa])\b",
            re.IGNORECASE,
        ),
    ),
    (
        PROFESIONAL,
        re.compile(
            r"\b(engineer|ingenier[oa]|scientist|cient[ií]fic[oa]|analyst|analista|"
            r"consultant|consultor[a]?|specialist|especialista|developer|"
            r"desarrollador[a]?|architect|arquitect[oa]|lawyer|attorney|abogad[oa]|"
            r"professor|profesor[a]?|docente|physician|m[eé]dic[oa]|psychologist|"
            r"psic[oó]log[oa]|accountant|contador[a]?|economist|economista|"
            r"researcher|investigador[a]?|nurse|enfermer[oa]|physiotherapist|"
            r"fisioterapeuta|auditor[a]?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        TECNICO,
        re.compile(
            r"\b(technician|t[eé]cnic[oa]|supervisor[a]?|coordinator|"
            r"coordinador[a]?|paralegal|assistant|asistente)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SERVICIOS_VENTAS,
        re.compile(
            r"\b(sales|ventas|vendedor[a]?|cashier|cajer[oa]|waiter|waitress|"
            r"mesero|mesera|retail|comercio\s+minorista|customer\s+service|"
            r"servicio\s+al\s+cliente|chef|cook|cocinero|security\s+guard|"
            r"guardia\s+de\s+seguridad|hairdresser|peluquer[oa]|flight\s+attendant)\b",
            re.IGNORECASE,
        ),
    ),
    (
        OFICIOS,
        re.compile(
            r"\b(electrician|electricista|mechanic|mec[aá]nic[oa]|welder|"
            r"soldador[a]?|carpenter|carpinter[oa]|plumber|plomer[oa]|"
            r"mason|alba[ñn]il|machinist|butcher|carnicer[oa]|baker|panader[oa])\b",
            re.IGNORECASE,
        ),
    ),
    (
        OPERADORES,
        re.compile(
            r"\b(machine\s+operator|operador[a]?\s+de\s+m[aá]quina|assembler|"
            r"ensamblador[a]?|driver|conductor[a]?|forklift|montacargas|"
            r"truck\s+driver|cdl|crane\s+operator|operador[a]?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ELEMENTAL,
        re.compile(
            r"\b(laborer|obrero|cleaner|aseador[a]?|limpieza|helper|ayudante|"
            r"warehouse\s+worker|auxiliar\s+de\s+bodega|delivery|mensajer[oa]|"
            r"packer|empacador[a]?|janitor|conserje|dishwasher)\b",
            re.IGNORECASE,
        ),
    ),
)


def detectar_escolaridad(titulo: str | None) -> str:
    """Grupo ocupacional (CIUO-08 ampliado) inferido del título crudo.

    Devuelve uno de NIVELES, o NO_ESPECIFICADO si el título no matchea ningún
    patrón (nunca se fuerza ni se reparte: ver seniority.py).
    """
    if not titulo or not isinstance(titulo, str):
        return NO_ESPECIFICADO

    for nivel, patron in _PATRONES:
        if patron.search(titulo):
            return nivel

    return NO_ESPECIFICADO
