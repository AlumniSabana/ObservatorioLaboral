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
# API key de Anthropic (Claude) para el lector de documentos del backend.
# Puede ser la misma key que usa el chat del frontend (CLAUDE_API_KEY).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Mapeo completo de programas académicos -> términos de búsqueda.
#
# Por cada programa, el scraper recorre esta lista de keywords y busca cada una
# en la API externa (Adzuna / Google Jobs). Las vacantes encontradas se asocian
# a ese programa mediante la columna `programa_relacionado` en Supabase.
#
# Para afinar la recolección de un programa, agrega o ajusta sus keywords aquí.
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