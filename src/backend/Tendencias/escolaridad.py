"""
Nivel de escolaridad — clasificación OCUPACIONAL (no de experiencia) inferida
del título de la vacante.

Es un filtro DISTINTO de "Nivel de experiencia" (Tendencias/seniority.py):
aquel mide SENIORITY (¿cuánta experiencia pide el puesto?, título con
"senior"/"junior"...); este mide a qué TIPO de ocupación pertenece el cargo,
según los Grandes Grupos de la Clasificación Internacional Uniforme de
Ocupaciones (CIUO-08 / CNO colombiana) —la misma taxonomía que ya usa
Salarios/salarios_service.py para pivotar GEIH por programa—.

CATEGORÍAS ACTIVAS (5)
----------------------
Se ofrecen los Grandes Grupos 1 a 5, que son los que corresponden a los
programas académicos de la Sabana:

    1. Directores y gerentes
    2. Profesionales, científicos e intelectuales
    3. Técnicos y profesionales de nivel medio
    4. Personal de apoyo administrativo
    5. Trabajadores de los servicios y vendedores

Se dejaron FUERA a propósito los grupos 6 a 9 (agropecuario, oficios,
operadores de máquinas y ocupaciones elementales): no corresponden a la
oferta académica. También se quitaron "Junior" y "Recién graduado", que no
son grupos de CIUO-08 sino niveles de experiencia y ya los cubre el filtro
"Nivel de experiencia" — tenerlos en los dos sitios era redundante.

Consecuencia asumida: una vacante de oficios u operarios (electricista,
soldador, conductor) queda en NO_ESPECIFICADO. Sigue contando en "Todos",
pero no es alcanzable por ningún filtro concreto. Es el efecto directo de
reducir las categorías, no un error.

Como en seniority.py: es heurística sobre el TÍTULO crudo (Adzuna trunca la
descripción a 500 caracteres), así que hay margen de error y un título que no
matchea ningún patrón queda en NO_ESPECIFICADO — no se fuerza ni se reparte
(ver la nota de seniority.py sobre por qué "no especificado" no es "sin dato").

Alcance: solo alimenta `Tendencias/demanda_actual.py` (las 4 gráficas "más
demandados"), NO el motor de tendencias temporales, para no multiplicar las
combinaciones precalculadas.
"""

from __future__ import annotations

import re
from typing import Final

DIRECTIVO: Final = "directivo"
PROFESIONAL: Final = "profesional"
TECNICO: Final = "tecnico"
APOYO_ADMIN: Final = "apoyo_administrativo"
SERVICIOS_VENTAS: Final = "servicios_ventas"
NO_ESPECIFICADO: Final = "no_especificado"

# Los seleccionables en el dropdown. NO_ESPECIFICADO existe como resultado de
# la clasificación pero no se ofrece como opción.
NIVELES: Final = (
    DIRECTIVO, PROFESIONAL, TECNICO, APOYO_ADMIN, SERVICIOS_VENTAS,
)

ETIQUETAS: Final = {
    DIRECTIVO: "Directores y gerentes",
    PROFESIONAL: "Profesionales, científicos e intelectuales",
    TECNICO: "Técnicos y profesionales de nivel medio",
    APOYO_ADMIN: "Personal de apoyo administrativo",
    SERVICIOS_VENTAS: "Trabajadores de los servicios y vendedores de comercios y mercados",
    NO_ESPECIFICADO: "No especificado",
}


# ── 1. Dirección real (Gran Grupo 1) ────────────────────────────────────────
# Cargos que dirigen una organización o un área.
_DIRECTIVO_FUERTE: Final = re.compile(
    r"\b(director|directora|gerente|ceo|cfo|coo|cto|cio|chief|"
    r"vice\s?president|vicepresidente|vp|president|presidente|"
    r"head\s+of|jefe|decano|dean)\b"
    # CIUO-08 1412/1420: quien administra un restaurante, hotel o punto de
    # venta es gerente aunque el título no lleve la palabra.
    r"|\badministrador[a]?\s+(de\s+)?(restaurante|hotel|tienda|almac[eé]n|"
    r"punto\s+de\s+venta)\b",
    re.IGNORECASE,
)

# "Manager" a secas sí implica dirección (CIUO-08 1221 gerentes de ventas y
# mercadeo, 1219 de servicios empresariales, 1324 de logística...).
_MANAGER: Final = re.compile(r"\bmanager\b", re.IGNORECASE)

# ...PERO hay títulos que llevan "manager" sin dirigir nada: son especialistas
# con responsabilidad de cartera o de caso, y CIUO-08 los deja en su grupo
# profesional, no en el 1. Detectado sobre datos reales: "Dialysis Clinical
# Manager Registered Nurse", "Care Manager, Registered Nurse" y "RN Case
# Manager" salían como "Directores y gerentes" siendo cargos de enfermería.
_MANAGER_NO_DIRECTIVO: Final = re.compile(
    r"\b(case|care|clinical|account|product|project|program|programme|"
    r"community|content|brand|portfolio|relationship|engagement|"
    r"social\s+media)\s+manager\b",
    re.IGNORECASE,
)

# ── 2. Nivel medio con prioridad (Gran Grupo 3) ─────────────────────────────
# Se evalúa ANTES que "Profesionales" porque son el auxiliar/asistente de una
# profesión: llevan la palabra de la profesión ("nurse", "teacher") y sin esta
# regla se los tragaría el grupo 2. CIUO-08 los sitúa en el 3:
#   3221 enfermería de nivel medio (practical/licensed nurse, RPN, LPN, LVN)
#   3254 asistentes de fisioterapia   3342 asistentes jurídicos
#   Auxiliares de docencia y de enfermería.
_TECNICO_PRIORITARIO: Final = re.compile(
    r"\b(teacher|teaching)\s+(assistant|aide)\b"
    r"|\bassistant\s+teacher\b"
    r"|\b(nursing|nurse)\s+(assistant|aide)\b"
    r"|\bcertified\s+nursing\s+assistant\b|\bcna\b"
    r"|\b(registered\s+)?practical\s+nurse\b|\blpn\b|\blvn\b|\brpn\b"
    r"|\b(physical\s+)?therapist\s+assistant\b|\bpta\b"
    r"|\bmedical\s+assistant\b|\bparalegal\b"
    r"|\b(engineering|laboratory|lab|civil|design)\s+technician\b"
    r"|\bauxiliar\s+de\s+(enfermer[ií]a|fisioterapia|docencia)\b"
    r"|\bt[eé]cnic[oa]\s+(en|de)\b",
    re.IGNORECASE,
)

# ── 3. Resto de grupos ──────────────────────────────────────────────────────
# El orden importa: gana el primer patrón que coincida.
_PATRONES: Final = (
    # Gran Grupo 4 — apoyo administrativo. Antes que "Profesionales" para que
    # "Administrative Assistant" no lo capture otro patrón más genérico.
    (
        APOYO_ADMIN,
        re.compile(
            r"\b(administrative\s+(assistant|associate|coordinator)|"
            r"clerk|secretary|secretaria|receptionist|recepcionista|"
            r"data\s?entry|office\s+assistant|"
            # En Colombia "Analista/Auxiliar Administrativo" es un cargo de
            # apoyo, no un analista del grupo 2. Va aquí explícitamente
            # porque APOYO_ADMIN se evalúa antes que PROFESIONAL, que si no
            # se lo llevaría por la palabra "analista".
            r"analista\s+administrativ[oa]|auxiliar\s+administrativ[oa]|"
            r"asistente\s+administrativ[oa])\b",
            re.IGNORECASE,
        ),
    ),
    # Gran Grupo 2 — profesionales, científicos e intelectuales.
    (
        PROFESIONAL,
        re.compile(
            # 'engineering'/'ingeniería' van explícitos: \bengineer\b NO casa
            # con "engineering" (la 'i' siguiente rompe el límite de palabra),
            # y así se perdían títulos como "Chemical Process Engineering".
            r"\b(engineer|engineering|ingenier[oa]|ingenier[ií]a|educator|educador[a]?|"
            r"scientist|cient[ií]fic[oa]|analyst|analista|"
            r"consultant|consultor[a]?|specialist|especialista|developer|"
            r"desarrollador[a]?|architect|arquitect[oa]|lawyer|attorney|abogad[oa]|"
            r"professor|profesor[a]?|docente|teacher|maestr[oa]|physician|m[eé]dic[oa]|"
            r"psychologist|psic[oó]log[oa]|accountant|contador[a]?|economist|economista|"
            r"researcher|investigador[a]?|nurse|enfermer[oa]|physiotherapist|"
            r"fisioterapeuta|therapist|terapeuta|auditor[a]?|journalist|periodista|"
            r"designer|dise[ñn]ador[a]?|programmer|programador[a]?|pharmacist|"
            r"farmac[eé]utic[oa]|dentist|odont[oó]log[oa]|veterinari[oa]|"
            r"veterinarian|surgeon|cirujan[oa]|actuary|actuari[oa]|"
            r"writer|redactor[a]?|editor[a]?|producer|productor[a]?|"
            r"doctor|planner|planificador[a]?|translator|traductor[a]?|"
            r"residente\s+de\s+obra|administrador[a]?)\b",
            re.IGNORECASE,
        ),
    ),
    # Gran Grupo 3 — técnicos y profesionales de nivel medio (resto).
    (
        TECNICO,
        re.compile(
            r"\b(technician|t[eé]cnic[oa]|supervisor[a]?|coordinator|"
            r"coordinador[a]?|assistant|asistente|auxiliar|inspector[a]?|"
            r"agent|agente|broker|representative|representante)\b",
            re.IGNORECASE,
        ),
    ),
    # Gran Grupo 5 — servicios y ventas.
    (
        SERVICIOS_VENTAS,
        re.compile(
            r"\b(sales|ventas|vendedor[a]?|cashier|cajer[oa]|waiter|waitress|"
            r"mesero|mesera|retail|comercio\s+minorista|customer\s+service|"
            r"servicio\s+al\s+cliente|chef|cook|cocinero|barista|bartender|"
            r"security\s+guard|guardia\s+de\s+seguridad|hairdresser|peluquer[oa]|"
            r"flight\s+attendant|camarer[oa]|recepci[oó]n\s+hotel)\b",
            re.IGNORECASE,
        ),
    ),
)


def detectar_escolaridad(titulo: str | None) -> str:
    """Grupo ocupacional (CIUO-08, grupos 1-5) inferido del título crudo.

    Devuelve uno de NIVELES, o NO_ESPECIFICADO si el título no encaja en
    ninguno de los cinco grupos ofrecidos.
    """
    if not titulo or not isinstance(titulo, str):
        return NO_ESPECIFICADO

    # 1. Dirección: un cargo directivo manda sobre su área de origen
    #    ("Director de Enfermería" es dirección, no enfermería).
    if _DIRECTIVO_FUERTE.search(titulo):
        return DIRECTIVO
    if _MANAGER.search(titulo) and not _MANAGER_NO_DIRECTIVO.search(titulo):
        return DIRECTIVO

    # 2. Auxiliares de una profesión, antes de que el grupo 2 los absorba.
    if _TECNICO_PRIORITARIO.search(titulo):
        return TECNICO

    # 3. "Manager" de especialidad (product/project/community/account...):
    #    no dirigen la organización, son especialistas del Gran Grupo 2. Se
    #    resuelve aquí y no en la lista de abajo porque su patrón ya está
    #    escrito arriba; sin esta línea quedaban en NO_ESPECIFICADO al
    #    haberlos excluido de "Directores y gerentes".
    if _MANAGER_NO_DIRECTIVO.search(titulo):
        return PROFESIONAL

    # 4. Resto de grupos, en orden.
    for nivel, patron in _PATRONES:
        if patron.search(titulo):
            return nivel

    return NO_ESPECIFICADO
