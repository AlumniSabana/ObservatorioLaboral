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
    get_salary_by_title,
    get_salary_by_category,
    get_vacantes_por_cargo,
)
from GoogleJobs.google_jobs_service import (
    procesar_vacantes_google,
    get_vacantes_por_cargo_google,
)
from Documentos.document_service import subir_documento, stream_respuesta
from Tendencias.historical_collector import (
    recolectar_historico,
    leer_historico,
    leer_volumenes,
)
from Tendencias.tendencias_service import (
    construir_tendencias,
    recalcular_todo,
    opciones_disponibles,
)
from Tendencias.skills_demandadas import (
    skills_demandadas,
    evolucion_skills,
    limpiar_cache as limpiar_cache_skills,
)
from Tendencias.google_jobs_sync import sincronizar as sincronizar_google_jobs
from Tendencias.linkedin_sync import sincronizar as sincronizar_linkedin
from Tendencias.demanda_actual import demanda_actual, salario_vacantes_cop, invalidar_cache as invalidar_demanda
from Salarios.salarios_service import (
    salario_por_programa,
    resumen_salarios,
)
from Perfil.perfil_service import construir_perfil_ocupacional
from LinkedIn.linkedin_service import (
    recolectar_linkedin,
    estado_linkedin,
    LinkedInDesactivado,
)
from Asistente.contexto_service import resumen_contexto
from Informes import informes_service
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


@app.get("/analytics/salarios")
async def get_salarios(programa: str = None, paises: str = None):
    """
    Análisis salarial en COP pivotado por programa académico (GEIH DANE + SPE).

    Sin `programa`: devuelve el resumen base (meta, lista de programas con datos,
    rangos SPE). Con `programa`: devuelve KPIs (mediana/percentiles), la
    comparativa por subgrupo ocupacional CNO y el rango SPE donde cae la mediana.

    Si además se pasa `paises` (los mismos códigos de Tendencias, ej. "us,gb,co"),
    se agrega `salario_vacantes`: el promedio mensual en COP de las vacantes de
    Adzuna seleccionadas (convertido con la TRM del momento), para comparar el
    salario oficial de GEIH contra lo que de verdad ofrecen las vacantes de esas
    fuentes. Google Jobs y LinkedIn no aportan aquí (no traen salario estructurado).
    """
    try:
        if programa:
            resultado = salario_por_programa(programa)
            if paises:
                resultado["salario_vacantes"] = salario_vacantes_cop(programa, paises.split(","))
            return resultado
        return resumen_salarios()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/perfil-ocupacional")
async def get_perfil_ocupacional(programa: str, paises: str = "us"):
    """
    Perfil ocupacional completo de un programa académico: salario, skills, perfil
    O*NET (RIASEC/job zone), seniority óptimo, tendencia de demanda y sectores que
    contratan. Compone todo en un único JSON (lo consumen la página y el PDF).
    """
    try:
        lista_paises = [p.strip() for p in paises.split(",") if p.strip()] or ["us"]
        return construir_perfil_ocupacional(programa, lista_paises)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Informes PDF de terceros como fuente de skills.
# Flujo: extraer (no guarda) -> el usuario revisa -> guardar -> validar.
# Nada aparece en el selector de fuentes hasta que alguien lo valida.
# ---------------------------------------------------------------------------

class InformeGuardar(BaseModel):
    catalogo: dict
    items: list


@app.post("/informes/extraer")
async def informes_extraer(file: UploadFile = File(...)):
    """
    Extrae las skills de un informe PDF y las VERIFICA contra el texto del propio
    documento (cada cifra debe traer una cita literal localizable). No guarda nada:
    devuelve un borrador para que el usuario lo revise.
    """
    try:
        from Informes.informe_extractor import procesar_pdf

        contenido = await file.read()
        # Un PDF ya ingerido no se reprocesa: gasta tokens y duplicaría el informe.
        import hashlib
        existente = informes_service.existe_hash(hashlib.sha256(contenido).hexdigest())
        if existente:
            return JSONResponse(
                status_code=400,
                content={"error": f"Ese informe ya fue ingerido: {existente}"},
            )
        return procesar_pdf(contenido, file.filename or "informe.pdf")
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/informes")
async def informes_guardar(req: InformeGuardar):
    """Persiste el informe revisado (queda en estado 'borrador')."""
    try:
        return informes_service.guardar_informe(req.catalogo, req.items)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/informes")
async def informes_listar(estado: str = "todos"):
    """Catálogo de informes ingeridos (estado: borrador | validado | retirado | todos)."""
    try:
        return {"informes": informes_service.listar_informes(estado)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/informes/{informe_id}/validar")
async def informes_validar(informe_id: str, validado_por: str = "alumni@unisabana.edu.co"):
    """
    Valida el informe: a partir de aquí aparece como fuente en el selector.

    Invalida las cachés que listan fuentes; si no, la fuente nueva no se vería.
    """
    try:
        r = informes_service.validar_informe(informe_id, validado_por)
        try:
            from Tendencias.skills_demandadas import limpiar_cache as limpiar_skills
            limpiar_skills()
        except Exception:
            pass
        # El catálogo de opciones se cachea en disco: hay que borrarlo.
        try:
            from pathlib import Path
            cache = Path(__file__).resolve().parent / "Tendencias" / "_cache_opciones.json"
            if cache.exists():
                cache.unlink()
        except Exception:
            pass
        return r
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/informes/{informe_id}/retirar")
async def informes_retirar(informe_id: str):
    """Saca el informe del selector sin borrar sus datos."""
    try:
        return informes_service.retirar_informe(informe_id)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/informes/{informe_id}")
async def informes_eliminar(informe_id: str):
    """Elimina un informe. Solo si sigue en borrador."""
    try:
        return informes_service.eliminar_informe(informe_id)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/spe/competencias")
async def spe_competencias(programa: str = "TODOS", tipo: str = "competencia", top: int = 20):
    """
    Competencias OBSERVADAS en vacantes colombianas (anexos del SPE).

    A diferencia del ranking derivado de O*NET, estas son las que los empleadores
    pidieron de verdad. `tipo`: 'competencia' (blandas/digitales) o 'tecnologia'
    (herramientas, lenguajes, prácticas).
    """
    try:
        from SPE.spe_service import competencias
        return competencias(programa, tipo, top)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/spe/tendencias")
async def spe_tendencias(dimension: str = "transversal", top: int = 8):
    """
    Serie mensual del SPE (Colombia): la primera tendencia OBSERVADA del país en
    el Observatorio. `dimension`: ocupacion | transversal | digital.
    """
    try:
        from SPE.spe_service import tendencias
        return tendencias(dimension, top)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/spe/ocupaciones")
async def spe_ocupaciones(top: int = 15, departamento: str = None):
    """Ocupaciones con más ofertas registradas en el SPE (Colombia)."""
    try:
        from SPE.spe_service import ocupaciones_top
        return ocupaciones_top(top, departamento)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/ole/ingreso")
async def ole_ingreso(programa: str, nivel: str = "Universitario"):
    """
    Ingreso de los GRADUADOS de un programa (OLE, MinEducación).

    Complementa —no sustituye— el salario de la GEIH: aquel mide a quien ejerce
    la ocupación, este a quien se graduó del programa, y distingue a los de La
    Sabana del resto del país. Viene en rangos de SMMLV; la mediana es estimada.
    """
    try:
        from OLE.ole_service import ingreso_por_programa
        return ingreso_por_programa(programa, nivel)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/ole/posgrados")
async def ole_posgrados(top: int = 12):
    """
    Posgrados de La Sabana ordenados por el ingreso de sus graduados.

    No depende del programa de pregrado: el OLE registra cada posgrado como un
    programa aparte y no permite saber de qué pregrado venía cada graduado.
    """
    try:
        from OLE.ole_service import posgrados_sabana
        return {"posgrados": posgrados_sabana(top)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/sena/skills")
async def sena_skills(programa: str, tipo: str = "habilidad"):
    """
    Habilidades o conocimientos OFICIALES del CNO 2025 (SENA) para un programa.

    Es la contraparte colombiana y en español de O*NET: normativo (lo que la
    ocupación exige), no observado (lo que el mercado pide hoy).
    `tipo`: habilidad | conocimiento | funcion.
    """
    try:
        from SENA.sena_service import skills_de_programa
        return skills_de_programa(programa, tipo)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/sena/denominaciones")
async def sena_denominaciones(programa: str):
    """Sinónimos oficiales del cargo asociado al programa (CNO 2025)."""
    try:
        from SENA.sena_service import denominaciones
        return {"programa": programa, "denominaciones": denominaciones(programa)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/informes/comparativa")
async def informes_comparativa(top: int = 12):
    """
    Compara la posición de las skills entre TODOS los informes validados.
    Vacío si hay menos de dos: con uno solo no hay nada que comparar.
    """
    try:
        return informes_service.comparativa_informes(top)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/informes/{informe_id}/detalle")
async def informe_detalle(informe_id: str, top: int = 20):
    """Cifras de un informe concreto, para pintar sus gráficas propias."""
    try:
        return informes_service.detalle_informe(informe_id, top)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/informes/contraste")
async def informes_contraste(informes: str, dimension: str = "skill", top: int = 25):
    """
    Cifras de los informes elegidos, para mostrarlas COMO CONTRASTE junto al ranking
    de skills. No se promedian con las vacantes: son magnitudes distintas.
    """
    try:
        ids = [i.strip() for i in informes.split(",") if i.strip()]
        return informes_service.contraste(ids, dimension, top)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/asistente/contexto")
async def asistente_contexto():
    """
    Resumen factual del Observatorio (empresas, sectores, cargos, programas y
    salarios) en texto plano, para alimentar al chatbot de empresas y cultura.
    Incluye de forma explícita los LÍMITES de los datos, para que el asistente no
    atribuya al Observatorio cosas que no mide (cultura, clima, GPTW).
    """
    try:
        return resumen_contexto()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/linkedin/estado")
async def linkedin_estado():
    """
    Estado de la fuente LinkedIn: si está habilitada, cuántas ofertas hay y bajo
    qué condiciones puede activarse. Es solo lectura: no recolecta nada.
    """
    try:
        return estado_linkedin()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/scrape/linkedin")
async def scrape_linkedin(keywords_por_programa: int = 1):
    """
    Recolecta OFERTAS DE EMPLEO públicas de LinkedIn (Colombia). Cadencia prevista:
    TRIMESTRAL con `keywords_por_programa=1` (comportamiento por defecto). Un
    valor mayor amplía puntualmente el footprint (más tráfico contra un endpoint
    cubierto por los Términos de Uso de LinkedIn) — usar con criterio, no como
    ajuste habitual.

    Devuelve 403 mientras la fuente esté desactivada, que es el estado por defecto:
    hacerlo va contra los Términos de Uso de LinkedIn (asunto contractual), así que
    requiere aprobación de la Universidad y poner LINKEDIN_HABILITADO=true en .env.
    Solo ofertas; nunca perfiles de personas.
    """
    try:
        return recolectar_linkedin(keywords_por_programa=keywords_por_programa)
    except LinkedInDesactivado as e:
        return JSONResponse(status_code=403, content={"error": str(e), "habilitado": False})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


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
# Tendencias temporales
# ---------------------------------------------------------------------------

@app.get("/skills-demandadas")
def skills_mas_demandadas(
    tipo: str = "tecnologia",
    programa: str = "TODOS",
    seniority: str = "TODOS",
    top: int = 25,
    paises: str = "us",
):
    """Ranking de competencias o tecnologías más demandadas.

    Cruza la demanda real de cada programa (share de vacantes, Adzuna) con la
    importancia O*NET de cada skill en la ocupación. NO es una tendencia temporal
    ni skills observadas en el texto: es una vista derivada de nivel de demanda.
    Ver Tendencias/skills_demandadas.py.

    tipo='competencia' | 'tecnologia'
    """
    if tipo not in ("competencia", "tecnologia"):
        return JSONResponse(
            status_code=400,
            content={"error": "tipo debe ser 'competencia' o 'tecnologia'"},
        )
    if top < 1:
        return JSONResponse(status_code=400, content={"error": "top debe ser >= 1"})
    lista_paises = [p.strip() for p in paises.split(",") if p.strip()]
    if not lista_paises:
        return JSONResponse(status_code=400, content={"error": "paises no puede estar vacío"})
    try:
        return skills_demandadas(
            tipo=tipo, programa=programa, seniority=seniority, top=top, paises=lista_paises
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/skills-demandadas/evolucion")
def skills_evolucion(
    tipo: str = "tecnologia",
    programa: str = "TODOS",
    seniority: str = "TODOS",
    top: int = 8,
    paises: str = "us",
):
    """Serie temporal (suavizada) de la demanda de las top skills.

    Con TODOS los programas, cada skill se mueve distinto (cambia el mix). Con un
    programa concreto, todas siguen la demanda de esa carrera (líneas paralelas,
    marcado con `paralelas`). `paises` acepta varios separados por coma y se
    combinan promediando cada mercado. Ver Tendencias/skills_demandadas.
    """
    if tipo not in ("competencia", "tecnologia"):
        return JSONResponse(
            status_code=400,
            content={"error": "tipo debe ser 'competencia' o 'tecnologia'"},
        )
    if top < 1:
        return JSONResponse(status_code=400, content={"error": "top debe ser >= 1"})
    lista_paises = [p.strip() for p in paises.split(",") if p.strip()]
    if not lista_paises:
        return JSONResponse(status_code=400, content={"error": "paises no puede estar vacío"})
    try:
        return evolucion_skills(
            tipo=tipo, programa=programa, seniority=seniority, top=top, paises=lista_paises
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/tendencias/sincronizar-google")
def tendencias_sincronizar_google():
    """Lleva las vacantes de Google Jobs al módulo de Tendencias y recalcula.

    Copia `vacantes_google` -> `vacantes_historicas` convirtiendo la fecha
    relativa ("hace 3 días") en absoluta y extrayendo las SKILLS del texto
    completo (lo que Adzuna no permite). Luego recalcula todas las series.

    Ejecutar después de un `POST /scrape?fuente=google_jobs`. Es idempotente.
    """
    try:
        resumen = sincronizar_google_jobs()
        filas = leer_historico()
        volumenes = leer_volumenes()
        resumen["recalculo"] = recalcular_todo(filas, volumenes)
        invalidar_demanda()  # el histórico cambió: refrescar las gráficas de demanda
        limpiar_cache_skills()
        return resumen
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/tendencias/sincronizar-linkedin")
def tendencias_sincronizar_linkedin():
    """Lleva las vacantes de LinkedIn al módulo de Tendencias y recalcula.

    Copia `vacantes_linkedin` -> `vacantes_historicas`. Solo aporta dimensión
    'cargo': LinkedIn no entrega sector estructurado y el recolector actual no
    trae el texto de la descripción, así que no hay de dónde extraer skills.

    Ejecutar después de `POST /scrape/linkedin`. Es idempotente.
    """
    try:
        resumen = sincronizar_linkedin()
        filas = leer_historico()
        volumenes = leer_volumenes()
        resumen["recalculo"] = recalcular_todo(filas, volumenes)
        invalidar_demanda()
        limpiar_cache_skills()
        return resumen
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/tendencias/opciones")
def tendencias_opciones():
    """Valores de filtro que tienen datos precalculados (para poblar los selectores)."""
    try:
        return opciones_disponibles()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/tendencias/demanda")
def tendencias_demanda(
    programa: str = "TODOS",
    seniority: str = "TODOS",
    escolaridad: str = "TODOS",
    paises: str = "us",
    top: int = 15,
):
    """
    Top-N de demanda (cargos, sectores, empresas, programas) sobre la muestra
    histórica, respetando los filtros de la página de Tendencias (país, programa,
    seniority, escolaridad). Alimenta las 4 gráficas "más demandados".

    `escolaridad` (directivo|profesional|tecnico|apoyo_administrativo|
    servicios_ventas|oficios|operadores|elemental|junior|graduado) es un eje
    distinto de `seniority`: agrupa por TIPO de ocupación (Grandes Grupos
    CIUO-08 + Junior/Recién Graduado), no por experiencia. Ver
    Tendencias/escolaridad.py.
    """
    try:
        lista_paises = [p.strip() for p in paises.split(",") if p.strip()] or ["us"]
        return demanda_actual(programa, seniority, lista_paises, top, escolaridad)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/tendencias")
def tendencias(
    dimension: str = "cargo",
    programa: str = "TODOS",
    seniority: str = "TODOS",
    desde: str | None = None,
    hasta: str | None = None,
    top: int | None = None,
    fuente: str = "adzuna",
    paises: str = "us",
):
    """Serie temporal + clasificación creciente/estable/decreciente + insights.

    dimension='cargo'  -> títulos de cargo normalizados
    dimension='sector' -> categorías de Adzuna

    `paises` acepta VARIOS separados por coma (ej. 'us,gb,ca'). Se combinan
    promediando el share de cada mercado —cada país pesa igual—, no sumando
    volúmenes (EE.UU. concentra el ~93% y haría invisibles al resto). Ver
    Tendencias/tendencias_service.construir_tendencias.

    Otros filtros (opcionales): `programa` académico, `seniority`
    (senior|junior|graduado|no_especificado), rango de meses `desde`/`hasta`
    ('YYYY-MM-01') y `top` N términos por fuerza de señal.

    Lee de `tendencias_observaciones`, que llena POST /tendencias/recolectar.
    Si aún no hay datos devuelve meta.sin_datos=true (no es un error).
    """
    lista_paises = [p.strip() for p in paises.split(",") if p.strip()]
    if not lista_paises:
        return JSONResponse(
            status_code=400, content={"error": "paises no puede estar vacío"}
        )
    if dimension not in ("cargo", "sector", "skill"):
        return JSONResponse(
            status_code=400,
            content={"error": "dimension debe ser 'cargo', 'sector' o 'skill'"},
        )
    if top is not None and top < 1:
        return JSONResponse(status_code=400, content={"error": "top debe ser >= 1"})
    try:
        return construir_tendencias(
            dimension, programa, seniority, desde, hasta, top, fuente, lista_paises
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/tendencias/recolectar")
def tendencias_recolectar(
    meses: int = 24, presupuesto: int = 250, pais: str = "us", keywords_por_programa: int = 1
):
    """Backfill histórico contra Adzuna y recálculo de la serie agregada.

    Muestrea los últimos `meses` meses usando max_days_old + sort_direction=up
    (ver Tendencias/historical_collector.py) sin gastar más de `presupuesto`
    llamadas a la API. Luego reagrega todo en `tendencias_observaciones`.

    Es idempotente: se puede reejecutar para ampliar/refrescar la muestra.
    """
    try:
        resumen = recolectar_historico(
            meses_atras=meses,
            presupuesto=presupuesto,
            pais=pais,
            keywords_por_programa=keywords_por_programa,
        )
        filas = leer_historico()
        volumenes = leer_volumenes()
        resumen["recalculo"] = recalcular_todo(filas, volumenes)
        invalidar_demanda()  # el histórico cambió: refrescar las gráficas de demanda
        resumen["vacantes_historicas_totales"] = len(filas)
        # La demanda por programa cambió: invalida el caché del ranking de skills.
        limpiar_cache_skills()
        return resumen
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Lector de documentos (PDF) con Claude
# ---------------------------------------------------------------------------

class DocChatRequest(BaseModel):
    file_id: str   # id devuelto por /documento/subir
    message: str   # pregunta del usuario (o el prompt inicial de insights)


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