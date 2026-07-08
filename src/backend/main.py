"""
Backend FastAPI del Observatorio Laboral de Alumni Sabana.

Este archivo es el punto de entrada de la API: define todos los endpoints HTTP
que consume el frontend (Next.js). La lógica real vive en los servicios:
  - Adzuna/adzuna_service.py     -> recolección Adzuna + cálculo de analíticas
  - GoogleJobs/google_jobs_service.py -> recolección Google Jobs (SerpApi)
  - Documentos/document_service.py -> lectura de PDFs subidos por el usuario (Claude)

Para correrlo en local:  uvicorn main:app --reload --port 8000
Documentación interactiva: http://localhost:8000/docs
"""

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from Adzuna.adzuna_service import (
    procesar_todas_vacantes,
    fetch_jobs_from_db,
    get_analytics,
    get_salary_by_title,
    get_salary_by_category,
    get_vacantes_por_cargo,
)
from GoogleJobs.google_jobs_service import (
    procesar_vacantes_google,
    get_analytics_google,
    get_vacantes_por_cargo_google,
)
from Documentos.document_service import subir_documento, stream_respuesta
from ONet.onet_service import obtener_competencias, listar_programas
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
    """Recolecta vacantes de la fuente indicada (todo hacia su tabla).

    fuente='adzuna'      -> Adzuna (Estados Unidos) -> tabla `vacantes`
    fuente='google_jobs' -> Google Jobs (Colombia, SerpApi con round-robin
                            dentro del presupuesto) -> tabla `vacantes_google`
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
async def get_job_analytics(
    fuente: str = "adzuna",
    seniority: str = None,
    programa: str = None,
    category: str = None,
    contract_time: str = None,
    salary_min: float = None,
    salary_max: float = None,
    city: str = None,
    schedule_type: str = None,
    remote: bool = None,
):
    """Analíticas según la fuente. Cada fuente tiene su propia tabla y su propia
    forma de analíticas (Google Jobs no incluye salario/sector; Adzuna sí).

    fuente='adzuna'      -> analíticas desde la tabla `vacantes`
    fuente='google_jobs' -> analíticas desde la tabla `vacantes_google`

    Los demás parámetros (opcionales) filtran las vacantes ANTES de agregar. Cada
    fuente usa solo los que le aplican (Adzuna: category/contract_time/salario;
    Google: city/schedule_type/remote); seniority y programa aplican a ambas.
    """
    try:
        filtros = {
            "seniority": seniority,
            "programa": programa,
            "category": category,
            "contract_time": contract_time,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "city": city,
            "schedule_type": schedule_type,
            "remote": remote,
        }
        if fuente == "google_jobs":
            return get_analytics_google(filtros=filtros)
        return get_analytics(fuente="adzuna", filtros=filtros)
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/vacantes/por-cargo")
async def vacantes_por_cargo(
    cargo: str,
    fuente: str = "adzuna",
    seniority: str = None,
    programa: str = None,
    category: str = None,
    contract_time: str = None,
    salary_min: float = None,
    salary_max: float = None,
    city: str = None,
    schedule_type: str = None,
    remote: bool = None,
):
    """Vacantes individuales para un cargo (título normalizado), con su enlace.

    Alimenta la ventana emergente que aparece al hacer clic en una barra de
    'Cargos más demandados'. Aplica los mismos filtros que el dashboard, para que
    el detalle coincida con lo que se está viendo.
    """
    try:
        filtros = {
            "seniority": seniority,
            "programa": programa,
            "category": category,
            "contract_time": contract_time,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "city": city,
            "schedule_type": schedule_type,
            "remote": remote,
        }
        if fuente == "google_jobs":
            return get_vacantes_por_cargo_google(cargo, filtros=filtros)
        return get_vacantes_por_cargo(cargo, fuente="adzuna", filtros=filtros)
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


# ---------------------------------------------------------------------------
# Lector de documentos (PDF) con Claude
# ---------------------------------------------------------------------------

class DocChatRequest(BaseModel):
    file_id: str   # id devuelto por /documento/subir
    message: str   # pregunta del usuario (o el prompt inicial de insights)


@app.get("/competencias/programas")
def competencias_programas():
    """Lista los programas que tienen mapeo a una ocupación O*NET (para el selector)."""
    return {"programas": listar_programas()}


@app.get("/competencias")
def competencias(programa: str):
    """Competencias y tecnologías (de O*NET) para un programa académico.

    Devuelve {"programa", "habilidades": [...], "tecnologias": [...]}. Si O*NET no
    está configurado o no devuelve datos, las listas vienen vacías y el frontend
    muestra un aviso.
    """
    datos = obtener_competencias(programa)
    return {"programa": programa, **datos}


@app.post("/documento/subir")
async def documento_subir(file: UploadFile = File(...)):
    """Recibe un PDF, lo sube a la Files API de Claude y devuelve su file_id.

    No se guarda nada en la base de datos: el archivo vive temporalmente en el
    almacenamiento de Anthropic y el frontend conserva el file_id solo en sesión.
    """
    try:
        contenido = await file.read()
        file_id = subir_documento(
            contenido,
            file.filename or "documento.pdf",
            file.content_type or "application/pdf",
        )
        return {"file_id": file_id, "filename": file.filename}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/documento/chat")
def documento_chat(req: DocChatRequest):
    """Responde (en streaming) sobre el documento previamente subido.

    Sirve tanto para el resumen inicial de insights como para preguntas de
    seguimiento; en ambos casos referencia el documento por su file_id.
    """
    try:
        generador = stream_respuesta(req.file_id, req.message)
        # Forzamos el primer fragmento para capturar errores tempranos (key
        # inválida, dependencia faltante, file_id inexistente) y responder un
        # error limpio en vez de cortar el stream a la mitad.
        primero = next(generador, "")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    def cuerpo():
        if primero:
            yield primero
        yield from generador

    return StreamingResponse(cuerpo(), media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)