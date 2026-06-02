import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Mapeo completo de programas
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