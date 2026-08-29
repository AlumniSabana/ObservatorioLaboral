"""
Clasificación de habilidades de un informe en 2 grupos: "Habilidades técnicas"
y "Power Skills". Usada SOLO por el pie chart de `detalle_informe()` (la vista
de un informe individual en /informes) — no toca el esquema de 4 categorías
(técnica/blanda/conocimiento/destreza) de Tendencias/skills_extractor.py, que
sigue alimentando el resto del sistema (extracción de vacantes, contraste).

POR QUÉ NO REUSAR ESE ESQUEMA DE 4 CATEGORÍAS
----------------------------------------------
Se probó primero remapear directamente `categoria` (técnica→técnicas,
blanda+conocimiento+destreza→power skills) y falló con datos reales: sobre el
informe "Coursera Job Skills Report 2025" ya ingerido, 25 de 35 skills cayeron
en "destreza" — no porque sean genéricas, sino porque `get_categoria()` usa
"destreza" como VALOR POR DEFECTO cuando el término no está en ninguno de los
diccionarios (línea 116 de skills_extractor.py). Ahí terminaron mezcladas
"Cybersecurity", "Machine Learning" y "Data Science" (técnicas, sin duda) junto
con "Leadership" y "Empathy" (soft skills reales). Un informe de tendencias
tecnológicas usa jerga (Prompt Engineering, Generative AI) que nuestros
diccionarios de O*NET/Ocupacol —pensados para vacantes, no para este tipo de
reporte— no cubren, así que el remapeo heredaba ese ruido.

Además la propia categoría "blanda" (de la lista de 35 "Skills" de O*NET) no es
homogénea: incluye "Programming", "Installation", "Repairing", "Equipment
Maintenance" — habilidades técnicas de O*NET clasificadas ahí porque su
taxonomía de "Skills" no distingue igual que la noción moderna de soft/hard
skill.

ENFOQUE
-------
Clasificador propio por palabras clave, sobre el término ORIGINAL (en el
idioma del informe, normalmente inglés). Lista corta y curada de términos que
son genuinamente interpersonales o de autogestión (comunicación, liderazgo,
adaptabilidad, resolución de conflictos...) — el mismo tipo de lista que usan
los propios informes de la industria (Coursera llama "Power Skills" a un
conjunto acotado y nombrado, todo lo demás es "Technical/Business Skills").
Lo que NO matchea cae en "Habilidades técnicas" por defecto: en un informe de
demanda laboral la inmensa mayoría de lo listado son herramientas, tecnologías
o dominios de conocimiento, así que ese es el catch-all seguro.

Verificado sobre el informe real: de 35 skills, 8 caen en Power Skills
(Resilience, Innovation, Communication, Leadership, Active Listening, Writing,
Adaptability, Empathy) y 27 en Habilidades técnicas — proporción consistente
con cómo el propio Coursera reporta esa distinción.
"""

from __future__ import annotations

import re
import unicodedata

TECNICA = "Habilidades técnicas"
POWER_SKILL = "Power Skills"

# Términos interpersonales / de autogestión, en inglés y español (los informes
# llegan mayormente en inglés; el español cubre informes o citas ya traducidas).
# Frases de una palabra o compuestas: el matching es por límite de palabra,
# tolerante a mayúsculas y tildes.
_POWER_SKILLS: frozenset[str] = frozenset({
    # Comunicación
    "communication", "comunicacion", "active listening", "escucha activa",
    "writing", "redaccion", "speaking", "comunicacion oral",
    "public speaking", "presentation", "presentacion",
    # Liderazgo y gestión de personas
    "leadership", "liderazgo", "management of personnel resources",
    "gestion de personal", "coaching", "mentoring", "mentoria",
    "team building", "people management", "gestion de equipos",
    # Colaboración y relación
    "teamwork", "trabajo en equipo", "collaboration", "colaboracion",
    "conflict resolution", "resolucion de conflictos",
    "negotiation", "negociacion", "persuasion",
    "interpersonal skills", "habilidades interpersonales",
    # Adaptabilidad y resiliencia
    "adaptability", "adaptabilidad", "resilience", "resiliencia",
    "flexibility", "flexibilidad", "stress management",
    "manejo del estres", "manejo del estrés",
    # Pensamiento e inteligencia emocional
    "critical thinking", "pensamiento critico",
    "problem solving", "resolucion de problemas",
    "emotional intelligence", "inteligencia emocional",
    "empathy", "empatia", "creativity", "creatividad",
    "innovation", "innovacion", "decision making", "toma de decisiones",
    "judgment", "juicio y toma de decisiones",
    # Autogestión
    "time management", "gestion del tiempo", "self management",
    "autogestion", "work ethic", "etica laboral", "self awareness",
    "autoconocimiento", "growth mindset",
    # Orientación social / servicio / aprendizaje
    "customer service", "servicio al cliente", "service orientation",
    "orientacion al servicio", "social perceptiveness", "percepcion social",
    "cultural awareness", "diversity", "diversidad e inclusion",
    "active learning", "aprendizaje activo", "learning agility",
    "coordination", "coordinacion",
})

# Compilado una vez: alternación de frases, cada una con límites de palabra.
_PATRON = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(_POWER_SKILLS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar de forma robusta."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def clasificar_habilidad(termino: str | None) -> str:
    """TECNICA o POWER_SKILL. Por defecto técnica (ver docstring del módulo)."""
    if not termino:
        return TECNICA
    return POWER_SKILL if _PATRON.search(_plegar(termino)) else TECNICA
