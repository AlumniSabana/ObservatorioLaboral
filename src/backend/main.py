"""
FastAPI backend for AlumniSabana job listings and analytics
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
from config import PROGRAMAS_KEYWORDS

app = FastAPI(title="AlumniSabana Job API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/scrape")
async def scrape_jobs(borrar: bool = False):
    try:
        resultado = procesar_todas_vacantes(borrar=borrar)
        return {"status": "completed", **resultado}
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/vacantes")
async def get_vacantes():
    try:
        jobs = fetch_jobs_from_db()
        return jobs
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/analytics")
async def get_job_analytics():
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