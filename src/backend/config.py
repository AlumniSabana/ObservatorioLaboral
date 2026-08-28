"""
Configuración central del backend.

Aquí se cargan todas las variables de entorno (credenciales de Supabase, Adzuna
y SerpApi) y se define el diccionario PROGRAMAS_KEYWORDS, que es el "mapa" que
relaciona cada programa académico de La Sabana con los términos de búsqueda que
se usan para recolectar vacantes en las APIs externas.

Las variables se leen desde el archivo src/backend/.env (no versionado).
"""

import os
from dotenv import load_dotenv

# Lee el archivo .env y expone sus valores como variables de entorno
load_dotenv()

# --- Credenciales de servicios externos ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
# SerpApi key para recolectar vacantes de Google Jobs (Colombia)
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
# Presupuesto de búsquedas de SerpApi por corrida. CADA PÁGINA = 1 búsqueda.
# El plan gratuito da ~250/mes; dejamos un pequeño margen (240) por defecto.
# La recolección reparte este presupuesto entre TODAS las keywords (round-robin)
# para maximizar la cantidad y diversidad de vacantes sin exceder la cuota.
try:
    SERPAPI_MAX_BUSQUEDAS = int(os.getenv("SERPAPI_MAX_BUSQUEDAS", "240"))
except ValueError:
    SERPAPI_MAX_BUSQUEDAS = 240
# API key de Anthropic (Claude) para el lector de documentos del backend.
# Puede ser la misma key que usa el chat del frontend (CLAUDE_API_KEY).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# API key de O*NET Web Services para la sección "Competencias y habilidades".
# Regístrate (gratis) en https://services.onetcenter.org/developer/signup
# Sin ella, la sección de competencias muestra un aviso de "no configurado".
ONET_API_KEY = os.getenv("ONET_API_KEY")

# --- Google Document AI (OCR de informes PDF) -------------------------------
# Se usa para leer los informes PDF que se ingieren como fuente de skills
# (ver Informes/informe_extractor.py). Si no está configurado, el extractor cae a
# pypdf, que funciona bien con PDFs nativos pero NO con escaneos.
#
# Para configurarlo:
#   1. En Google Cloud, crear un procesador de tipo "Document OCR".
#   2. Poner en src/backend/.env:
#        GCP_PROJECT_ID=<id-del-proyecto>
#        GCP_LOCATION=us            # o 'eu'
#        DOCAI_PROCESSOR=<id-del-procesador>
#        GOOGLE_APPLICATION_CREDENTIALS=<ruta al json de la service account>
#   3. pip install google-cloud-documentai
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us")
DOCAI_PROCESSOR = os.getenv("DOCAI_PROCESSOR")


# --- LinkedIn (endpoints públicos "jobs-guest") -----------------------------
# INTERRUPTOR DE APROBACIÓN. La infraestructura está lista pero DESACTIVADA a
# propósito: recolectar de LinkedIn va contra sus Términos de Uso como asunto
# CONTRACTUAL (ver LinkedIn/linkedin_service.py). Solo se activa cuando la
# Dirección de Alumni / jurídica de la Universidad lo apruebe explícitamente,
# poniendo LINKEDIN_HABILITADO=true en src/backend/.env.
#
# Alcance aprobado (no ampliar sin volver a consultar):
#   - SOLO ofertas de empleo públicas. NUNCA perfiles de personas (serían datos
#     personales sujetos a la Ley 1581 de 2012 de habeas data).
#   - Frecuencia trimestral, no comercial, con fines académicos.
LINKEDIN_HABILITADO = os.getenv("LINKEDIN_HABILITADO", "false").strip().lower() in ("1", "true", "si", "sí", "yes")

# Tope de páginas por keyword en cada corrida. LinkedIn limita a ~10 páginas por
# IP; nos quedamos MUY por debajo a propósito (huella mínima, sin proxies).
try:
    LINKEDIN_MAX_PAGINAS = int(os.getenv("LINKEDIN_MAX_PAGINAS", "3"))
except ValueError:
    LINKEDIN_MAX_PAGINAS = 3

# Segundos de espera entre peticiones (cortesía; evita parecer un bot agresivo).
try:
    LINKEDIN_PAUSA_SEG = float(os.getenv("LINKEDIN_PAUSA_SEG", "3"))
except ValueError:
    LINKEDIN_PAUSA_SEG = 3.0


# Mapeo de programas académicos -> términos de búsqueda EN INGLÉS.
# Se usa para ADZUNA (mercado de Estados Unidos), donde las vacantes están en inglés.
#
# Por cada programa, el scraper recorre esta lista de keywords y busca cada una.
# Las vacantes encontradas se asocian a ese programa mediante la columna
# `programa_relacionado` en Supabase.
PROGRAMAS_KEYWORDS = {
    "Administración de Empresas": ["business administration", "business manager", "operations manager", "management trainee"],
    "Administración & Servicio": ["customer service manager", "service operations", "customer experience"],
    "Administración de Mercadeo y Logística Internacionales": ["marketing manager", "digital marketing", "supply chain", "logistics manager"],
    "Administración de Negocios Internacionales": ["international business", "global business development", "export manager"],
    "Economía y Finanzas Internacionales": ["financial analyst", "investment analyst", "international finance", "risk analyst"],
    # OJO: la PRIMERA keyword de cada programa debe ser ÚNICA en todo el diccionario.
    # El backfill de tendencias usa solo la primera (una llamada por programa) y hace
    # upsert de las vacantes por su id: si dos programas comparten la primera keyword,
    # la última escritura gana y uno de los dos programas desaparece de la etiqueta
    # `programa_relacionado`. Por eso 'fintech' va antes que 'financial analyst' aquí.
    "Economía y Finanzas Internacionales Virtual": ["fintech", "remote financial analyst", "financial analyst"],
    "Gastronomía": ["chef", "executive chef", "food and beverage manager", "restaurant manager"],
    "Comportamiento Organizacional": ["organizational development", "talent management", "hr business partner"],
    "Psicología": [
        "organizational psychologist", "hr psychologist", "talent acquisition",
        "clinical psychologist", "school psychologist", "psychotherapist",
    ],
    "Comunicación Audiovisual y Multimedios": ["video producer", "multimedia specialist", "content creator"],
    "Comunicación Corporativa": ["corporate communications", "public relations manager", "communications manager"],
    "Comunicación Social y Periodismo": ["journalist", "content writer", "social media manager"],
    "Licenciatura en Educación Infantil": ["early childhood teacher", "preschool teacher", "education coordinator"],
    "Enfermería": ["registered nurse", "clinical nurse", "nursing manager"],
    "Fisioterapia": ["physical therapist", "physiotherapist", "rehabilitation specialist"],
    "Ciencias Políticas": ["political analyst", "public policy", "government relations"],
    "Derecho": ["lawyer", "corporate lawyer", "legal counsel", "compliance officer"],
    "Relaciones Internacionales": ["international relations", "diplomat", "foreign affairs"],
    "Filosofía": ["ethics officer", "policy analyst", "philosophy researcher"],
    "Medicina": ["medical doctor", "physician", "general practitioner"],
    "Ciencia de Datos": ["data scientist", "data analyst", "machine learning engineer", "business intelligence"],
    "Ingeniería Civil": ["civil engineer", "structural engineer", "project engineer civil"],
    "Ingeniería de Bioproducción": ["bioprocess engineer", "biotechnology engineer"],
    "Ingeniería de Diseño e Innovación": ["product designer", "design engineer", "innovation engineer"],
    "Ingeniería Industrial": ["industrial engineer", "process engineer", "lean manufacturing"],
    "Ingeniería Informática": ["software engineer", "full stack developer", "backend developer"],
    "Ingeniería Mecánica": ["mechanical engineer", "maintenance engineer"],
    "Ingeniería Química": ["chemical engineer", "process engineer chemical"],
    "Ingeniería en Inteligencia Artificial": ["ai engineer", "artificial intelligence engineer", "machine learning engineer"],
}

# Mapeo de programas -> términos de búsqueda EN ESPAÑOL, para GOOGLE JOBS (Colombia).
# En Colombia la mayoría de vacantes están tituladas/descritas en español, así que
# buscar en inglés perdía muchas ofertas. Estas keywords aprovechan mejor cada
# búsqueda de SerpApi. (Si quieres afinar un programa, ajusta su lista aquí.)
PROGRAMAS_KEYWORDS_CO = {
    "Administración de Empresas": ["administrador de empresas", "gerente de operaciones", "analista administrativo"],
    "Administración & Servicio": ["jefe de servicio al cliente", "coordinador de experiencia del cliente", "analista de servicio al cliente"],
    "Administración de Mercadeo y Logística Internacionales": ["analista de mercadeo", "marketing digital", "analista de logística", "jefe de cadena de suministro"],
    "Administración de Negocios Internacionales": ["negocios internacionales", "analista de comercio exterior", "coordinador de importaciones y exportaciones"],
    "Economía y Finanzas Internacionales": ["analista financiero", "analista de inversiones", "analista de riesgos"],
    # Primera keyword única, por el mismo motivo que en PROGRAMAS_KEYWORDS.
    "Economía y Finanzas Internacionales Virtual": ["analista fintech", "analista económico", "analista financiero"],
    "Gastronomía": ["chef", "jefe de cocina", "administrador de restaurante"],
    "Comportamiento Organizacional": ["desarrollo organizacional", "analista de gestión del talento", "analista de recursos humanos"],
    # Antes solo se buscaba la rama organizacional, así que el programa se veía
    # como si el mercado solo contratara psicólogos de selección. Las ramas
    # clínica, educativa y social son las que faltaban.
    "Psicología": [
        "psicólogo organizacional", "analista de selección", "psicólogo",
        "psicólogo clínico", "psicólogo educativo", "psicólogo social",
        "psicoterapeuta", "neuropsicólogo", "psicólogo infantil",
    ],
    "Comunicación Audiovisual y Multimedios": ["productor audiovisual", "editor de video", "creador de contenido"],
    "Comunicación Corporativa": ["comunicaciones corporativas", "relaciones públicas", "jefe de comunicaciones"],
    "Comunicación Social y Periodismo": ["periodista", "redactor de contenido", "community manager"],
    "Licenciatura en Educación Infantil": ["docente de preescolar", "educador infantil", "auxiliar pedagógico"],
    "Enfermería": ["enfermero", "auxiliar de enfermería", "jefe de enfermería"],
    "Fisioterapia": ["fisioterapeuta", "terapeuta físico", "especialista en rehabilitación"],
    "Ciencias Políticas": ["analista político", "analista de políticas públicas", "analista de asuntos públicos"],
    "Derecho": ["abogado", "asesor jurídico", "oficial de cumplimiento"],
    "Relaciones Internacionales": ["relaciones internacionales", "analista de cooperación internacional", "analista de asuntos internacionales"],
    "Filosofía": ["docente de filosofía", "investigador", "analista de ética"],
    "Medicina": ["médico general", "médico", "médico especialista"],
    "Ciencia de Datos": ["científico de datos", "analista de datos", "ingeniero de machine learning", "analista de inteligencia de negocios"],
    "Ingeniería Civil": ["ingeniero civil", "ingeniero estructural", "residente de obra"],
    "Ingeniería de Bioproducción": ["ingeniero de bioprocesos", "ingeniero en biotecnología"],
    "Ingeniería de Diseño e Innovación": ["diseñador de producto", "ingeniero de diseño", "ingeniero de innovación"],
    "Ingeniería Industrial": ["ingeniero industrial", "ingeniero de procesos", "ingeniero de producción"],
    "Ingeniería Informática": ["ingeniero de software", "desarrollador full stack", "desarrollador backend"],
    "Ingeniería Mecánica": ["ingeniero mecánico", "ingeniero de mantenimiento"],
    "Ingeniería Química": ["ingeniero químico", "ingeniero de procesos químicos"],
    "Ingeniería en Inteligencia Artificial": ["ingeniero de inteligencia artificial", "ingeniero de machine learning", "especialista en inteligencia artificial"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Pertinencia: qué NO puede ser una vacante de cada programa
# ─────────────────────────────────────────────────────────────────────────────
# Las fuentes (Adzuna, Google Jobs, LinkedIn) resuelven la búsqueda por full-text
# match, así que pedir "registered nurse" devuelve también "Registered Veterinary
# Nurse". El pipeline etiqueta `programa_relacionado` con el programa de la
# keyword buscada, SIN mirar el título, de modo que esas ofertas entraban a
# Enfermería y salían en la vista como el cargo "Auxiliar veterinario(a)".
#
# No hay forma de pedirle a la API que afine la búsqueda, así que el descarte se
# hace aquí y se aplica DOS veces, a propósito:
#   - al RECOLECTAR, para que la tabla deje de acumular ruido nuevo;
#   - al LEER, porque las filas ya guardadas conservan su etiqueta vieja y
#     re-recolectar todo el histórico no es viable cada vez.
#
# Las cadenas se comparan en minúscula y sin tildes contra el título del cargo,
# como subcadena: "veterinar" cubre veterinary / veterinario / veterinaria.
# Mantener la lista corta y basada en casos observados, no en sospechas: cada
# entrada de más es una vacante legítima que se deja de contar.
EXCLUSIONES_PROGRAMA: dict[str, list[str]] = {
    "Enfermería": ["veterinar"],
    "Medicina": ["veterinar"],
}


def _plegar(texto: str) -> str:
    """minúsculas y sin tildes, para comparar títulos ES/EN con una sola regla."""
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )


def es_pertinente(programa: str | None, titulo: str | None) -> bool:
    """¿Este título puede pertenecer a este programa?

    Devuelve True cuando no hay regla que lo desmienta: el criterio es descartar
    lo que sabemos que está mal, no exigir que el título demuestre pertenecer.
    Un match por tokens de la keyword descartaría vacantes legítimas en español
    buscadas con keywords en inglés (y viceversa) — para eso está
    `coincide_con_keyword`, que sí hace ese match pero por otro motivo (ver ahí).
    """
    prohibidas = EXCLUSIONES_PROGRAMA.get(programa or "")
    if not prohibidas:
        return True
    plano = _plegar(titulo)
    return not any(p in plano for p in prohibidas)


# Palabras que no cuentan para decidir si el título "contiene" la keyword —
# demasiado cortas o demasiado comunes en ambos idiomas para ser señal.
_STOP_KEYWORD = {"de", "la", "el", "los", "las", "y", "en", "para", "con", "a", "del", "al"}


def coincide_con_keyword(keyword: str | None, titulo: str | None) -> bool:
    """¿El título contiene las palabras de la keyword que se buscó?

    Motivo (encontrado 2026-08-25, auditando por qué salían cargos en inglés
    sin relación con el programa — ver ejemplos abajo): Adzuna hace *full-text*
    sobre título Y descripción, y clasifica por relevancia — pero el backfill
    histórico pide `sort_direction=up` (las más antiguas primero, para poder
    muestrear meses pasados) y ESO desactiva el orden por relevancia. El
    resultado, verificado en vivo contra la API real: para una keyword amplia
    de 1-2 palabras (`business manager`, `organizational development`,
    `public policy`...) el 70-99% de lo que vuelve NO tiene relación real con
    lo buscado (ej.: 'business manager' trajo 'Line Cook', 'Custodian/Bus
    Driver', 'Adjunct Faculty - Music Department'). Se probaron los parámetros
    `title_only` y `what_phrase` de la API: NINGUNO arregla el problema en modo
    `sort_direction=up` (se siguen colando resultados sin relación).

    La única señal fiable que queda es re-verificar del lado de acá: si el
    título no contiene ni una palabra de lo que se buscó, no es del tema.
    Puede perder algún match cruzado de idioma legítimo (un título en español
    para una keyword en inglés) — verificado contra datos reales que es raro:
    los mercados de España/México devuelven casi todo en inglés para roles
    profesionales. Ese costo es mucho menor que dejar pasar 70-99% de ruido.

    Devuelve True si la keyword es None/vacía o no tiene palabras significativas
    (no hay con qué comparar, mejor no descartar).
    """
    palabras = [w for w in _plegar(keyword or "").split() if w not in _STOP_KEYWORD and len(w) > 2]
    if not palabras:
        return True
    titulo_plano = _plegar(titulo or "")
    return all(w in titulo_plano for w in palabras)
