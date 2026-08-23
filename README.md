# Observatorio Laboral — Alumni Sabana

Plataforma web que analiza el mercado laboral para los egresados de la Universidad
de La Sabana. Combina vacantes reales, fuentes normativas (O*NET, SENA) y estudios
oficiales (GEIH, OLE) en un conjunto de dashboards, más dos asistentes de IA (uno
por Claude, otro por Gemini) que ayudan a interpretar los datos.

> Este README es el punto de partida para entender el proyecto. Cada módulo
> importante además tiene comentarios explicativos en su cabecera — léelos antes
> de tocar el código, sobre todo en `Tendencias/` y `config.py`.

---

## 1. Arquitectura general

Dos partes independientes que se despliegan por separado:

```
┌──────────────────────────────┐         ┌────────────────────────────────────┐
│  FRONTEND (Next.js)          │  HTTP   │  BACKEND (FastAPI / Python)        │
│  src/app, src/lib            │ ──────► │  src/backend                       │
│  Exportación estática        │         │                                    │
│  (GitHub Pages, basePath     │         │  Recolecta vacantes (Adzuna,       │
│   /ObservatorioLaboral)      │         │  Google Jobs, LinkedIn) y agrega   │
│                              │         │  fuentes normativas y estudios     │
│                              │         │  oficiales (O*NET, SENA, OLE, SPE, │
│                              │         │  GEIH) sobre la misma taxonomía    │
│                              │         │  de programas académicos.          │
└──────────────┬───────────────┘         │              │                     │
               │                          │              ▼                     │
               │                          │        ┌───────────┐               │
               │                          │        │ Supabase  │               │
               │                          │        │ (Postgres)│               │
               │                          │        └───────────┘               │
               │                          └────────────────────────────────────┘
               │
               │  Chat flotante (todas las páginas) → /api/chat (Next) → Claude
               │  Chat "Empresas" (/asistente)       → /api/chat (Next) → Gemini
               ▼
        ┌───────────────────────┐
        │ Anthropic API / Gemini│
        └───────────────────────┘
```

- **Frontend**: Next.js (App Router) en TypeScript, exportado como sitio
  **estático** (`output: 'export'`) y publicado en GitHub Pages
  (`basePath: '/ObservatorioLaboral'`). Consume el backend vía `fetch` usando
  `NEXT_PUBLIC_BACKEND_URL`.
- **Backend**: API REST en FastAPI (Python). Recolecta vacantes, calcula
  analíticas, sirve las fuentes normativas/oficiales y lee PDFs con Claude.
  Guarda todo en Supabase; el lector de PDF ad-hoc (`/documento/*`) no persiste
  nada.
- **⚠️ Caveat de despliegue**: en modo `output: 'export'` las rutas
  `src/app/api/*` de Next (incluida `/api/chat`, que sirve **ambos** chats) NO
  corren como servidor — GitHub Pages no las ejecuta. En producción, el chat
  necesita un entorno que sí las sirva (o un despliegue distinto al export
  estático solo para esa ruta). Ver `next.config.ts`.

---

## 2. Estructura de carpetas

```
src/
├── app/                        # Páginas del frontend (Next.js App Router)
│   ├── page.tsx                # ⭐ PORTADA "Tendencias" — crece/estable/decrece por cargo o sector
│   ├── skills-demandadas/      # "Competencias" — skills/tecnologías ponderadas por demanda real
│   ├── cursos/                 # "Cursos y formación" — busca y abre catálogos externos (Coursera, IBM…)
│   ├── salaries/               # "Análisis salarial" — GEIH + SPE pivotado por programa
│   ├── perfil-ocupacional/     # "Perfil ocupacional" — agregador por programa (salario+skills+O*NET+PDF)
│   ├── asistente/              # "Empresas" (nav) — chatbot de empresas/cultura, Gemini
│   ├── informes/               # "Informes" — ingesta de PDFs de terceros como fuente de skills
│   ├── conditions/, demand/    # Páginas legacy con contenido ESTÁTICO, sin conectar y fuera del nav
│   ├── api/chat/route.ts       # Proxy de streaming: Claude (chat flotante) o Gemini (Empresas)
│   ├── layout.tsx              # Layout raíz
│   └── globals.css             # Paleta de colores de La Sabana
├── lib/
│   ├── sidebar.tsx              # Navegación + PageLayout reutilizable
│   ├── floating-chat.tsx        # Chat flotante (Claude) presente en todas las páginas
│   ├── selector-fuentes.tsx     # Desplegable de fuentes (checkboxes, agrupado por naturaleza)
│   ├── markdown.tsx             # Render de Markdown (sin remark-gfm, parser propio)
│   ├── document-reader.tsx      # "Leer un documento": subir PDF → Claude lo lee
│   └── perfil-pdf.ts            # Exporta el Perfil ocupacional a PDF (jsPDF)
└── backend/                     # API en Python (NO la compila Next.js; corre aparte)
    ├── main.py                  # Todas las rutas FastAPI — ver §3
    ├── config.py                # Env vars + PROGRAMAS_KEYWORDS (EN/Adzuna) y _CO (ES/Google Jobs, LinkedIn)
    ├── traducciones.py          # Diccionarios EN→ES de cargos y sectores
    ├── requirements.txt
    ├── migrations/               # SQL versionado — ver §7
    ├── Adzuna/                  # Vacantes EE.UU. + utilidades compartidas (cliente Supabase, normalize_title)
    ├── GoogleJobs/               # Vacantes Colombia (SerpApi) → vacantes_google
    ├── LinkedIn/                 # Vacantes Colombia — DESACTIVADO por defecto, ver §4
    ├── ONet/                     # Skills/tecnologías normativas (O*NET, EE.UU., en inglés)
    ├── SENA/                     # Skills/conocimientos CNO 2025 (Colombia, español, taxonomía propia)
    ├── SPE/                      # Competencias observadas + tendencia mensual (SPE, ~1.8M vacantes reales)
    ├── OLE/                      # Ingreso de egresados por programa (Observatorio Laboral MEN)
    ├── Salarios/                 # GEIH (DANE) pivotado por programa vía CNO
    ├── Perfil/                   # Agregador: Salarios + O*NET + seniority + tendencia + ciudades/sectores
    ├── Informes/                 # Ingesta y validación de PDFs de terceros como fuente de skills
    ├── Asistente/                # Contexto factual para el chat "Empresas"
    ├── Tendencias/               # Motor de tendencias — backfill, ponderación, regresión (ver §6)
    └── Documentos/               # Lector de PDF ad-hoc con Claude (efímero, sin persistir)
```

---

## 3. Endpoints del backend (`main.py`)

| Grupo | Rutas |
|---|---|
| **Salud / vacantes crudas** | `GET /health` · `POST /scrape` (Adzuna/Google Jobs) · `GET /vacantes` · `GET /vacantes/por-cargo` |
| **Analítica Adzuna** | `GET /analytics/salary/{job_title}` · `GET /analytics/salary-by-category/{category}` |
| **Salarios (GEIH+SPE)** | `GET /analytics/salarios?programa=` |
| **Perfil ocupacional** | `GET /perfil-ocupacional?programa=&paises=` |
| **Informes (PDF)** | `POST /informes/extraer` · `POST /informes` · `GET /informes?estado=` · `POST /informes/{id}/validar` · `POST /informes/{id}/retirar` · `DELETE /informes/{id}` · `GET /informes/comparativa` · `GET /informes/{id}/detalle` · `GET /informes/contraste?informes=&dimension=` |
| **SPE** | `GET /spe/competencias?programa=&tipo=&top=` · `GET /spe/tendencias?dimension=&top=` · `GET /spe/ocupaciones?top=&departamento=` |
| **OLE** | `GET /ole/ingreso?programa=&nivel=` · `GET /ole/posgrados?top=` |
| **SENA** | `GET /sena/skills?programa=&tipo=` · `GET /sena/denominaciones?programa=` |
| **Empresas (chat)** | `GET /asistente/contexto` |
| **LinkedIn** | `GET /linkedin/estado` · `POST /scrape/linkedin?keywords_por_programa=` (403 si no está habilitado) |
| **Programas** | `GET /programas` |
| **Tendencias / Competencias** | `GET /tendencias?dimension=&programa=&seniority=&paises=&desde=&hasta=&top=` · `GET /tendencias/opciones` · `GET /tendencias/demanda?programa=&seniority=&paises=&top=` · `POST /tendencias/recolectar` · `GET /skills-demandadas?tipo=&programa=&seniority=&paises=&top=` · `GET /skills-demandadas/evolucion?...` · `POST /tendencias/sincronizar-google` · `POST /tendencias/sincronizar-linkedin` |
| **Documentos (chat PDF)** | `POST /documento/subir` · `POST /documento/chat` (streaming) |

Documentación interactiva completa (Swagger) en `http://localhost:8000/docs`.

---

## 4. Fuentes de datos

| Fuente | Qué aporta | Mercado / idioma | Estado |
|---|---|---|---|
| **Adzuna** | Recolección de vacantes + analítica salarial | EE.UU., inglés | ✅ Activa — tabla `vacantes` |
| **Google Jobs** (SerpApi) | Recolección de vacantes, ciudades/modalidad | Colombia, español | ✅ Activa — tabla `vacantes_google` |
| **LinkedIn** | Scraping de vacantes públicas | Colombia, español | ⚠️ **Desactivada por defecto** — interruptor `LINKEDIN_HABILITADO` en `.env` (solo ofertas públicas, nunca perfiles; requiere aprobación jurídica de la Universidad) |
| **SPE** (Servicio Público de Empleo) | Competencias observadas + tendencia mensual + top ocupaciones, sobre ~1.8M vacantes reales | Colombia, español | ✅ Activa — única serie de tendencia realmente **observada** en Colombia |
| **O\*NET 27.3** | Taxonomía normativa de skills/tecnologías + RIASEC/job zone | EE.UU., inglés (traducido al mostrarse) | ✅ Activa — requiere `ONET_API_KEY` (gratis); sin ella devuelve listas vacías |
| **SENA / CNO 2025** | Skills y conocimientos por ocupación, taxonomía oficial colombiana | Colombia, español | ✅ Activa — mapeo CNO **propio**, distinto del que usa Salarios/GEIH |
| **OLE** (MinEducación) | Ingreso de egresados por programa (bandas de SMMLV) | Colombia, español | ✅ Activa — complementa, no reemplaza, el salario de GEIH |
| **GEIH** (DANE) | Salario real por ocupación | Colombia, español | ✅ Activa — JSON precalculado, pivotado por programa vía CNO |

`PROGRAMAS_KEYWORDS` (`config.py`) trae las keywords en **inglés** para Adzuna;
`PROGRAMAS_KEYWORDS_CO` trae las de **español** para Google Jobs y LinkedIn.
Cada vacante recolectada se etiqueta con `programa_relacionado` según la keyword
buscada — **no** según el contenido del título — así que hay un filtro de
pertinencia (`es_pertinente()` en `config.py`, sección `EXCLUSIONES_PROGRAMA`)
que descarta coincidencias engañosas del full-text search de las APIs (p. ej.
"registered nurse" trayendo "Registered Veterinary Nurse").

---

## 5. Base de datos (Supabase)

**Tablas crudas por fuente:**

| Tabla | Fuente |
|---|---|
| `vacantes` | Adzuna |
| `vacantes_google` | Google Jobs |
| `vacantes_linkedin` | LinkedIn |
| `spe_ocupaciones`, `spe_competencias` | SPE (anexos) |
| `spe_tendencias` | SPE (serie mensual nacional) |
| `sena_cno_ocupaciones`, `sena_cno_atributos` | SENA CNO 2025 |
| `ole_ibc_sabana`, `ole_ibc_nacional` | OLE |
| `informes`, `informes_observaciones` | PDFs de terceros validados |

**Tablas agregadas/unificadas:**

| Tabla | Qué es |
|---|---|
| `vacantes_historicas` | Muestra histórica unificada (Adzuna backfill + sync de Google Jobs/LinkedIn) — la usan Tendencias, Demanda actual y Skills |
| `muestreo_volumen` | Volumen real por keyword/mes/país, usado para ponderar la muestra (ver §6.3) |
| `tendencias_observaciones` | Serie de tendencia ya calculada — la lee `GET /tendencias` directamente |

---

## 6. Tendencias temporales (portada, ruta `/`)

Responde "¿qué cargos y sectores están creciendo?" usando la **fecha real de
publicación** de cada vacante. Tiene sutilezas necesarias antes de tocar el
código:

### 6.1 El scrape normal no sirve para tendencias
`POST /scrape` trae solo las ~100 vacantes más recientes por keyword — el 91%
cae en un mismo mes. Por eso el backfill (`Tendencias/historical_collector.py`)
vive aparte y escribe en `vacantes_historicas`, que nunca se borra.

### 6.2 Cómo se llega al pasado
Adzuna no tiene filtro "publicado antes de X", pero combinar `max_days_old=D`
con `sort_direction=up` aterriza justo en el borde de edad `D`, permitiendo
muestrear cualquier mes barriendo `D`.

### 6.3 Por qué la muestra se pondera
El recolector pide ~50 vacantes por keyword y mes — muestra balanceada por
construcción, no por demanda real. El campo `count` de la API da el volumen
real de la ventana; restando ventanas consecutivas se obtiene el volumen real
por mes, que pondera cada vacante muestreada (se guarda en `muestreo_volumen`).

### 6.4 La métrica es el *share*, no el conteo
Adzuna retira vacantes viejas de su índice (atrición), así que los volúmenes
absolutos no son comparables entre meses. Sí lo es el reparto **dentro** de
cada mes (`share = vacantes del término / vacantes del mes`); la atrición
afecta a todas las keywords por igual y se cancela al dividir.

### 6.5 Combinar varios países
`paises` acepta varios mercados a la vez. Se combinan **promediando el share**
de cada uno (cada país pesa igual), nunca sumando volúmenes — EE.UU. concentra
~93% del volumen estimado y sumarlo haría invisibles a México o España. Google
Jobs Colombia (`pais='co'`) y LinkedIn Colombia (`pais='co_li'`) se mantienen
como mercados **distintos** a propósito, para no mezclar fuentes sin darse
cuenta en la lógica de combinación.

### 6.6 Clasificación
Regresión lineal ponderada (más peso a meses recientes) sobre la serie de
shares; la pendiente se normaliza contra la media simple y se clasifica con
umbral simétrico (±0.08) en `creciente` / `estable` / `decreciente` — con
umbrales **asimétricos** para competencias (más fácil bajar a "en declive",
más difícil subir a "emergente").

### 6.7 Homologación de competencias
Las competencias de O*NET que son homologables a las **13 habilidades
generales** del estudio "Monitoreo entorno" de Alumni Sabana se marcan en
negrilla y muestran su categoría al pasar el cursor; la gráfica de evolución
siempre incluye representación de las 13 más "otras".

---

## 7. Migraciones (`src/backend/migrations/`)

| Archivo | Crea |
|---|---|
| `002_tendencias.sql` | `vacantes_historicas`, `tendencias_observaciones` |
| `003_tendencias_filtros.sql` | Columnas de segmentación (`programa`, etc.) en `tendencias_observaciones` |
| `004_google_jobs_tendencias.sql` | Integra Google Jobs a Tendencias/Skills |
| `005_linkedin.sql` | `vacantes_linkedin` (puede quedar vacía mientras la fuente esté desactivada) |
| `006_informes.sql` | `informes`, `informes_observaciones` |
| `007_spe_competencias.sql` | `spe_ocupaciones`, `spe_competencias` |
| `008_spe_tendencias.sql` | `spe_tendencias` |
| `009_sena_cno.sql` | `sena_cno_ocupaciones`, `sena_cno_atributos` |
| `010_ole_ibc.sql` | `ole_ibc_sabana`, `ole_ibc_nacional` |

> Nota: `GoogleJobs/google_jobs_service.py` menciona un `001_vacantes_google.sql`
> en su docstring que no existe en la carpeta — la tabla `vacantes_google` ya
> existe en producción; si se reconstruye desde cero, crearla a mano con las
> columnas de §5 antes de correr `002` en adelante.

---

## 8. Variables de entorno

### Backend (`src/backend/.env`)

| Variable | Requerida | Descripción |
|---|---|---|
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | Sí | Proyecto Supabase (Project Settings → API) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna | developer.adzuna.com |
| `SERPAPI_KEY` | Google Jobs | serpapi.com/manage-api-key |
| `SERPAPI_MAX_BUSQUEDAS` | Opcional | Presupuesto de búsquedas por corrida (def. `240`) |
| `LINKEDIN_HABILITADO` | Opcional | `true` activa la recolección (def. `false`) |
| `LINKEDIN_MAX_PAGINAS` / `LINKEDIN_PAUSA_SEG` | Opcional | Tope de páginas (def. `3`) y pausa entre peticiones (def. `3` s) |
| `ANTHROPIC_API_KEY` | Documentos | console.anthropic.com — lector de PDF ad-hoc |
| `GEMINI_API_KEY` | Empresas | Google AI Studio / Google Cloud — chat de "Empresas" |
| `ONET_API_KEY` | Competencias | services.onetcenter.org/developer/signup (gratis) |
| `GCP_PROJECT_ID` / `GCP_LOCATION` / `DOCAI_PROCESSOR` / `GOOGLE_APPLICATION_CREDENTIALS` | Opcional | Document AI (OCR) para PDFs escaneados en Informes; sin esto cae a `pypdf` (no sirve con escaneos) |

### Frontend (`.env.local` en la raíz)

| Variable | Descripción |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | URL del backend FastAPI (def. `http://localhost:8000`) |
| `CLAUDE_API_KEY` (o `ANTHROPIC_API_KEY`) | Chat flotante (Claude), en `src/app/api/chat/route.ts` |
| `GEMINI_API_KEY` | Chat de "Empresas" (Gemini), misma ruta con `modo='empresas'` |

> Los archivos `.env` están en `.gitignore`. Cada fuente es independiente: si
> falta una credencial, esa fuente se omite y el resto sigue funcionando.
> Tras cambiar cualquier variable, **reinicia** el proceso (`--reload` de
> uvicorn solo vigila archivos `.py`, no el `.env`).

---

## 9. Cómo ejecutar en local

### Frontend
```bash
npm install
npm run dev        # http://localhost:3000/ObservatorioLaboral/
```

### Backend
```bash
cd src/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000   # http://localhost:8000
```

---

## 10. Despliegue

- **Frontend**: GitHub Actions (`.github/workflows/nextjs.yml`) despliega a
  **GitHub Pages** en cada push a `main`. `next.config.ts` tiene
  `output: 'export'`, `basePath: '/ObservatorioLaboral'`, `trailingSlash: true`.
- **Backend**: debe desplegarse aparte (servidor Python); su URL pública va en
  `NEXT_PUBLIC_BACKEND_URL`.
- **Chat en producción**: con `output: 'export'`, `src/app/api/chat/route.ts`
  no corre como servidor en GitHub Pages. Verificar en qué entorno se sirve
  esa ruta en producción antes de asumir que el chat funciona igual que en
  `npm run dev`.

---

## 11. Los dos asistentes de IA

| | Chat flotante (todas las páginas) | "Empresas" (`/asistente`) |
|---|---|---|
| Modelo | Claude (`claude-sonnet-4-5`) | Gemini (`gemini-3.6-flash`) |
| Contexto | Solo los datos visibles en la página actual (`pageTitle` + `pageContent`) | `GET /asistente/contexto` — hechos reales del Observatorio (empresas, sectores, salarios) |
| Alcance | Estrictamente limitado a esos datos — no inventa cifras | Puede responder más allá del dataset (p. ej. rankings GPTW), etiquetando lo que no viene del Observatorio como conocimiento general |
| Implementación | `src/lib/floating-chat.tsx` → `/api/chat` (modo por defecto) | `src/app/asistente/page.tsx` → `/api/chat?modo=empresas` |

Un tercer feature de IA, independiente de los dos anteriores: el **lector de
documentos** (`Documentos/document_service.py`, rutas `/documento/*`) deja
subir un PDF ad-hoc para que Claude lo lea vía su Files API — no persiste nada
y no comparte código con los chats de arriba.

---

## 12. Notas / pendientes para quien continúe

- **`/conditions` y `/demand`** existen como archivos pero **no están en el
  nav** ni conectados al backend — contenido estático de ejemplo, candidatas a
  eliminar o a conectar a datos reales.
- **LinkedIn** tiene toda la infraestructura lista pero permanece detrás del
  interruptor `LINKEDIN_HABILITADO`: no activar sin aprobación explícita de la
  Dirección de Alumni / jurídica de la Universidad.
- **Migración `001_vacantes_google.sql` faltante** — ver nota en §7.
- **SPE congelado**: los anexos publicados llegan hasta sep-2023; la serie no
  se actualiza sola, hay que cargar el corte nuevo a mano cuando el SPE lo
  publique (`SPE/cargar_tendencias.py`).
- **Dimensión `skill` en Tendencias** está reservada pero no expuesta en el
  selector del frontend: nunca acumuló suficiente historia mensual en Google
  Jobs/LinkedIn (requiere ≥3 meses de volumen). La cubre la página
  **Competencias**, con un mecanismo independiente (ponderación por demanda ×
  importancia O*NET, no por serie temporal).
- **Cursos y formación**: hoy es un buscador que abre catálogos externos
  (Coursera, LinkedIn Learning, Google Skills, IBM Training) filtrados por un
  término — no trae resultados propios ni distingue cursos técnicos vs. power
  skills en la UI todavía.
- **Fuentes evaluadas y descartadas**: Jooble (solo indexa EE.UU.), Careerjet
  (cubría Colombia con datos muy pobres), Talent.com / WhatJobs (requieren
  cuenta aprobada y endpoint propio). Antes de evaluar una fuente nueva, revisar
  si ya se descartó por esto.
