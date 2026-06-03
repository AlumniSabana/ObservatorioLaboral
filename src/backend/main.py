"""
FastAPI backend for AlumniSabana job listings and analytics
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# CORREGIDO: Import correcto
from Adzuna.adzuna_service import (
    buscar_vacantes_adzuna,
    guardar_vacante,
    fetch_jobs_from_db,
    get_analytics,
    get_salary_by_title,
    get_salary_by_category,
)
from config import PROGRAMAS_KEYWORDS

app = FastAPI(title="AlumniSabana Job API")

# Scraping automático al iniciar (solo la primera vez o cada vez que reinicies)
@app.on_event("startup")
async def startup_event():
    print("🚀 Iniciando scraping automático de vacantes...")
    await scrape_jobs()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/vacantes")
async def get_vacantes():
    """Get all job listings from database"""
    try:
        jobs = fetch_jobs_from_db()
        return jobs
    except Exception as e:
        return {"error": str(e)}, 500


@app.post("/scrape")
async def scrape_jobs():
    """Trigger Adzuna scraping for all programs"""
    total_vacantes = 0
    total_guardadas = 0

    try:
        for programa, keywords in PROGRAMAS_KEYWORDS.items():
            keyword = keywords[0]  # Usamos solo la primera keyword
            try:
                print(f"Buscando vacantes para {programa} con keyword: {keyword}")
                jobs = buscar_vacantes_adzuna(keyword, num_pages=2)
                total_vacantes += len(jobs)

                for job in jobs:
                    if guardar_vacante(job, programa):
                        total_guardadas += 1

            except Exception as e:
                print(f"Error con {programa} ({keyword}): {str(e)}")
                continue

        return {
            "status": "completed",
            "total": total_vacantes,
            "saved": total_guardadas,
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}, 500


@app.get("/analytics")
async def get_job_analytics():
    """Get comprehensive analytics"""
    try:
        analytics = get_analytics()
        return analytics
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/analytics/salary/{job_title}")
async def get_salary_by_job_title(job_title: str):
    try:
        salary_info = get_salary_by_title(job_title)
        return salary_info
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/analytics/salary-by-category/{category}")
async def get_salary_by_job_category(category: str):
    try:
        salary_info = get_salary_by_category(category)
        return salary_info
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/programas")
async def get_programas():
    """Get list of all programs"""
    return {
        "programas": [
            {"name": programa, "keywords": keywords}
            for programa, keywords in PROGRAMAS_KEYWORDS.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)