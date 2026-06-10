"""
Backend FastAPI del Observatorio Laboral de Alumni Sabana.

Este archivo es el punto de entrada de la API: define todos los endpoints HTTP
que consume el frontend (Next.js). La lógica real vive en los servicios:
  - Adzuna/adzuna_service.py     -> recolección Adzuna + cálculo de analíticas
  - GoogleJobs/google_jobs_service.py -> recolección Google Jobs (SerpApi)

Para correrlo en local:  uvicorn main:app --reload --port 8000
Documentación interactiva: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Adzuna.adzuna_service import (
    procesar_todas_vacantes,
    fetch_jobs_from_db,
    get_analytics,
    get_salary_by_title,
    get_salary_by_category,
)
from GoogleJobs.google_jobs_service import (
    procesar_vacantes_google,
    get_analytics_google,
)
from config import PROGRAMAS_KEYWORDS

app = FastAPI(title="AlumniSabana Job API")

# CORS abierto a cualquier origen: el frontend estático (GitHub Pages) vive en un
# dominio distinto al del backend, por lo que necesita permiso para llamarlo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Endpoint de salud: útil para verificar que el backend está vivo."""
    return {"status": "ok"}


@app.post("/scrape")
async def scrape_jobs(borrar: bool = False, fuente: str = "adzuna"):
    """Recolecta vacantes de la fuente indicada.

    fuente='adzuna'      -> Adzuna (Estados Unidos)
    fuente='google_jobs' -> Google Jobs (Colombia, vía SerpApi)
    """
    try:
        if fuente == "google_jobs":
            resultado = procesar_vacantes_google(borrar=borrar)
        else:
            resultado = procesar_todas_vacantes(borrar=borrar)
        return {"status": "completed", "fuente": fuente, **resultado}
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/vacantes")
async def get_vacantes():
    """Devuelve la lista completa de vacantes almacenadas en Supabase (todas las fuentes)."""
    try:
        jobs = fetch_jobs_from_db()
        return jobs
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/analytics")
async def get_job_analytics(fuente: str = "adzuna"):
    """Analíticas según la fuente. Cada fuente tiene su propia tabla y su propia
    forma de analíticas (Google Jobs no incluye salario/sector; Adzuna sí).

    fuente='adzuna'      -> analíticas desde la tabla `vacantes`
    fuente='google_jobs' -> analíticas desde la tabla `vacantes_google`
    """
    try:
        if fuente == "google_jobs":
            return get_analytics_google()
        return get_analytics(fuente="adzuna")
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/analytics/salary/{job_title}")
async def get_salary_by_job_title(job_title: str):
    """Estadísticas salariales (promedio, mínimo, máximo) para un cargo concreto."""
    try:
        salary_info = get_salary_by_title(job_title)
        return salary_info
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/analytics/salary-by-category/{category}")
async def get_salary_by_job_category(category: str):
    """Estadísticas salariales agregadas para una categoría/sector concreto."""
    try:
        salary_info = get_salary_by_category(category)
        return salary_info
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/programas")
async def get_programas():
    """Lista los programas académicos y las keywords usadas para buscarlos."""
    return {
        "programas": [
            {"name": programa, "keywords": keywords}
            for programa, keywords in PROGRAMAS_KEYWORDS.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)