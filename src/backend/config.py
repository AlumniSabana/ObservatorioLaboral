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
    "Economía y Finanzas Internacionales Virtual": ["financial analyst", "fintech", "remote financial analyst"],
    "Gastronomía": ["chef", "executive chef", "food and beverage manager", "restaurant manager"],
    "Comportamiento Organizacional": ["organizational development", "talent management", "hr business partner"],
    "Psicología": ["organizational psychologist", "hr psychologist", "talent acquisition"],
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
    "Economía y Finanzas Internacionales Virtual": ["analista financiero", "analista fintech", "analista económico"],
    "Gastronomía": ["chef", "jefe de cocina", "administrador de restaurante"],
    "Comportamiento Organizacional": ["desarrollo organizacional", "analista de gestión del talento", "analista de recursos humanos"],
    "Psicología": ["psicólogo organizacional", "analista de selección", "psicólogo"],
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