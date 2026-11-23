# Observatorio Laboral — Alumni Sabana (TalentHub)

Plataforma web que analiza el mercado laboral para los egresados de la Universidad
de La Sabana. Combina vacantes reales, fuentes normativas (O*NET, SENA) y estudios
oficiales (GEIH, OLE) en un conjunto de dashboards, más asistentes de IA (Claude y
Gemini) que ayudan a interpretar los datos.

> **Documentación completa en la [wiki del repositorio](https://github.com/AlumniSabana/ObservatorioLaboral/wiki)**:
> manual del usuario, manual del administrador (con capturas) y guía del
> desarrollador. Este README es el resumen técnico para arrancar; cada módulo
> importante además tiene comentarios explicativos en su cabecera — léelos antes
> de tocar el código, sobre todo en `Tendencias/` y `config.py`.

---

## 1. Arquitectura general

Dos partes independientes que se despliegan por separado:

```
┌──────────────────────────────┐         ┌────────────────────────────────────┐
│  FRONTEND (Next.js)          │  HTTP   │  BACKEND (FastAPI / Python)        │
│  src/app, src/lib            │ ──────► │  src/backend                       │
│  Vercel                      │         │  Render                            │
│                              │         │                                    │
│  Rutas /api/chat (Next)      │         │  Recolecta vacantes (Adzuna,       │
│  corren en servidor          │         │  Google Jobs, LinkedIn) y agrega   │
│                              │         │  fuentes normativas y estudios     │
│                              │         │  oficiales (O*NET, SENA, OLE, SPE, │
│                              │         │  GEIH) sobre la misma taxonomía    │
└──────────────┬───────────────┘         │  de programas académicos.          │
               │                          │              │                     │
               │                          │              ▼                     │
               │                          │        ┌───────────┐               │
               │                          │        │ Supabase  │               │
               │                          │        │ (Postgres)│               │
               │                          │        └───────────┘               │
               │                          └────────────────────────────────────┘
               │
               │  Chat flotante (páginas de análisis) → /api/chat (Next) → Claude
               │  Chat "Empresas" (usuarios)          → /api/chat (Next) → Gemini
               ▼
        ┌───────────────────────┐
        │ Anthropic API / Gemini│
        └───────────────────────┘
```

- **Frontend**: Next.js (App Router) en TypeScript con Tailwind v4 y Recharts, en
  **modo servidor** (no es exportación estática): `next.config.ts` es el de
  Next por defecto, así que las rutas `src/app/api/*` —incluida `/api/chat`, que
  sirve ambos chats— corren en Vercel. Consume el backend con `fetch` usando
  `NEXT_PUBLIC_BACKEND_URL`.
- **Backend**: API REST en FastAPI (Python). Recolecta vacantes, calcula
  analíticas y sirve las fuentes normativas/oficiales. Guarda todo en Supabase.
- **Roles**: *Usuario* (sin inicio de sesión, solo lectura) y *Administrador*
  (inicia sesión; puede recolectar datos, subir informes y ver el dashboard de
  uso). La sesión es un token firmado (HMAC-SHA256, 12 h) y las rutas que
  modifican datos exigen `requiere_admin` en el backend: ocultar un botón en la
  interfaz **no** es la protección. Ver §8.
- **Diseño**: paleta de La Sabana como variables CSS (`--sabana-*`) más tokens
  semánticos (`--ink-*`, `--surface`, `--line`…) con **modo claro y oscuro**
  automáticos según el sistema. Ver `src/app/globals.css`.
- El workflow `.github/workflows/nextjs.yml` es **legado** (despliegue a GitHub
  Pages del esquema anterior) y ya no representa el despliegue real.

---

## 2. Estructura de carpetas

```
src/
├── app/                        # Páginas del frontend (Next.js App Router)
│   ├── page.tsx                # PORTADA "Tendencias" — general o por departamento (mapa de Colombia)
│   ├── skills-demandadas/      # "Competencias" — skills/tecnologías ponderadas por demanda real
│   ├── cursos/                 # "Cursos y formación" — busca y abre catálogos externos
│   ├── salaries/               # "Análisis salarial" — GEIH + SPE + OLE pivotado por programa
│   ├── perfil-ocupacional/     # "Perfil ocupacional" — agregador por programa (salario+skills+O*NET+PDF)
│   ├── asistente/              # "Empresas" — usuario: chat de empresas (Gemini); Admin: dashboard de uso
│   ├── informes/               # "Informes" — usuario: catálogo de solo lectura; Admin: ingesta y validación
│   ├── sobre/                  # "Sobre el observatorio" — qué es y de dónde salen los datos
│   ├── login/                  # Inicio de sesión del Administrador
│   ├── conditions/, demand/    # Páginas legacy con contenido ESTÁTICO, sin conectar y fuera del nav
│   ├── api/chat/route.ts       # Proxy de streaming: Claude (chat flotante) o Gemini (Empresas)
│   ├── layout.tsx              # Layout raíz (fuentes Libre Franklin / Playfair Display)
│   └── globals.css             # Paleta, tokens de modo claro/oscuro
├── lib/
│   ├── auth.tsx                 # useAuth, SoloAdmin, authHeaders (sesión de Admin)
│   ├── sidebar.tsx              # Navegación + PageLayout reutilizable
│   ├── floating-chat.tsx        # Chat flotante (Claude) en las páginas de análisis
│   ├── chat-sesion.ts           # Id anónimo de sesión + lectura del "tráiler de uso" del chat
│   ├── selector-fuentes.tsx     # Desplegable de fuentes (Colombia / Latinoamérica / Todas)
│   ├── seccion-departamentos.tsx, mapa-colombia.tsx   # Análisis por departamento
│   ├── panel-actualizacion.tsx  # Admin: fuentes, semáforo SerpApi, "Actualizar histórico"
│   ├── informe-general.tsx      # Admin: informe general en PDF (todas las fuentes y programas)
│   ├── dashboard-preguntas.tsx  # Admin: uso del asistente de TODOS los usuarios
│   ├── sobre-observatorio.tsx   # Contenido de /sobre
│   ├── spinner.tsx, markdown.tsx
│   └── perfil-pdf.ts            # Exporta el Perfil ocupacional a PDF (jsPDF)
└── backend/                     # API en Python (NO la compila Next.js; corre aparte)
    ├── main.py                  # Todas las rutas FastAPI — ver §3
    ├── auth.py                  # Login de Admin, token HMAC, guardia `requiere_admin`
    ├── config.py                # Env vars + PROGRAMAS_KEYWORDS (EN/Adzuna) y _CO (ES/Google Jobs, LinkedIn)
    ├── traducciones.py          # Diccionarios EN→ES de cargos y sectores; 18 grupos de sector
    ├── actualizar_local.py      # Recolección completa desde la consola (sin pasar por el navegador)
    ├── requirements.txt / requirements-dev.txt
    ├── tests/                   # Pruebas automáticas (pytest) — ver §10
    ├── migrations/              # SQL versionado — ver §7
    ├── Adzuna/                  # Vacantes + utilidades compartidas (cliente Supabase, normalize_title)
    ├── GoogleJobs/              # Vacantes Colombia (SerpApi) + control de cuota
    ├── LinkedIn/                # Vacantes públicas de LinkedIn (CO, MX, AR, CL, PE)
    ├── ONet/                    # Skills/tecnologías normativas (O*NET, EE.UU., en inglés)
    ├── SENA/                    # Skills/conocimientos CNO 2025 (Colombia, español, taxonomía propia)
    ├── SPE/                     # Competencias observadas + tendencia mensual (SPE, ~1.8M vacantes)
    ├── OLE/                     # Ingreso de egresados por programa (Observatorio Laboral MEN)
    ├── Salarios/                # GEIH (DANE) pivotado por programa vía CNO
    ├── Perfil/                  # Agregador: Salarios + O*NET + seniority + tendencia + ciudades/sectores
    ├── Informes/                # Ingesta, validación e insights (Gemini) de PDFs de terceros
    ├── Asistente/               # Contexto factual del chat "Empresas" + registro de preguntas
    ├── Tendencias/              # Motor de tendencias, demanda actual, geografía, orquestador (ver §6)
    └── Documentos/              # Lector de PDF ad-hoc con Claude (solo API; sin interfaz)
```

---

## 3. Endpoints del backend (`main.py`)

Las marcadas **(Admin)** exigen `Authorization: Bearer <token>` y responden 401 sin él.

| Grupo | Rutas |
|---|---|
| **Sesión** | `POST /auth/login` · `GET /auth/yo` |
| **Salud / vacantes crudas** | `GET /health` · `POST /scrape` (Admin) · `GET /vacantes` · `GET /vacantes/por-cargo` |
| **Analítica Adzuna** | `GET /analytics/salary/{job_title}` · `GET /analytics/salary-by-category/{category}` |
| **Salarios (GEIH+SPE)** | `GET /analytics/salarios?programa=` |
| **Perfil ocupacional** | `GET /perfil-ocupacional?programa=&paises=` |
| **Informes** | Lectura (público): `GET /informes` · `/informes/comparativa` · `/informes/{id}/detalle` · `/informes/{id}/similares` · `/informes/contraste` · `/informes/insights-generados`. Escritura (Admin): `POST /informes/extraer` · `POST /informes` · `POST /informes/{id}/validar` · `/retirar` · `DELETE /informes/{id}` · `POST /informes/insights` · `/informes/insights-conjuntos[/candidatos]` |
| **SPE** | `GET /spe/competencias` · `GET /spe/tendencias` · `GET /spe/ocupaciones` |
| **OLE** | `GET /ole/ingreso?programa=&nivel=` · `GET /ole/posgrados` |
| **SENA** | `GET /sena/skills?programa=&tipo=` · `GET /sena/denominaciones` |
| **Asistente** | `GET /asistente/contexto` · `POST /asistente/preguntas` (registro anónimo) · `GET /asistente/preguntas/resumen` (Admin) |
| **LinkedIn** | `GET /linkedin/estado` · `POST /scrape/linkedin` (Admin; 403 si no está habilitado) |
| **Tendencias / Competencias** | `GET /tendencias` · `/tendencias/opciones` · `/tendencias/demanda` · `/tendencias/departamentos` · `GET /skills-demandadas[/evolucion]` |
| **Tendencias (Admin)** | `POST /tendencias/recolectar` (todas las fuentes + recálculo) · `/tendencias/sincronizar-google` · `/tendencias/sincronizar-linkedin` · `GET /tendencias/fuentes/estado` · `/tendencias/serpapi/estado` · `/tendencias/actualizacion/estado` · `/tendencias/cargos-descartados` |
| **Documentos** | `POST /documento/subir` · `POST /documento/chat` (streaming; sin interfaz hoy) |

Documentación interactiva completa (Swagger) en `http://localhost:8000/docs`.

---

## 4. Fuentes de datos

| Fuente | Qué aporta | Mercado / idioma | Estado |
|---|---|---|---|
| **Adzuna** | Vacantes + analítica salarial; único origen de `category` (sector) | EE.UU., Reino Unido, Canadá, México, España | Activa |
| **Google Jobs** (SerpApi) | Vacantes, ciudades/modalidad | Colombia, español | Activa — cupo mensual con semáforo en el panel de Admin |
| **LinkedIn** | Ofertas **públicas** (nunca perfiles) | Colombia, México, Argentina, Chile, Perú | Activa tras aprobación; exige `LINKEDIN_HABILITADO=true`. Se detiene ante un 429 y nunca reintenta |
| **SPE** | Competencias observadas + tendencia mensual + top ocupaciones, ~1.8M vacantes | Colombia, español | Activa — corte congelado (ver §12) |
| **O\*NET 27.3** | Taxonomía de skills/tecnologías + RIASEC/job zone | EE.UU., inglés (traducido al mostrarse) | Activa — requiere `ONET_API_KEY` |
| **SENA / CNO 2025** | Skills y conocimientos por ocupación | Colombia, español | Activa — mapeo CNO **propio** |
| **OLE** (MinEducación) | Ingreso de egresados por programa | Colombia, español | Activa |
| **GEIH** (DANE) | Salario real por ocupación | Colombia, español | Activa — JSON precalculado |
| **Informes PDF** | Skills declaradas por terceros (p. ej. Coursera, WEF) | Mixto | Se muestran como contraste, **nunca** se promedian con las vacantes |

`PROGRAMAS_KEYWORDS` (`config.py`) trae las keywords en **inglés** para Adzuna;
`PROGRAMAS_KEYWORDS_CO` las de **español** para Google Jobs y LinkedIn. Cada
vacante se etiqueta con `programa_relacionado` según la keyword buscada, así que
hay un filtro de pertinencia (`es_pertinente()`, `EXCLUSIONES_PROGRAMA`) que
descarta coincidencias engañosas del full-text search.

**Sectores (18 grupos).** Solo Adzuna entrega categoría; Google Jobs y LinkedIn
no, y a esas vacantes no se les inventa sector. `traducciones.agrupar_sector`
colapsa las categorías en 18 grupos económicos y `sector_de_vacante` refina por
**título** dos grupos que ninguna categoría cubre (Energía/agua/servicios
públicos y Agroindustria). Es una heurística acotada; Agroindustria tiene muy
pocas vacantes en las fuentes actuales.

---

## 5. Base de datos (Supabase)

**Tablas crudas por fuente:**

| Tabla | Fuente |
|---|---|
| `vacantes` | Adzuna |
| `vacantes_google` | Google Jobs |
| `vacantes_linkedin` | LinkedIn |
| `spe_ocupaciones`, `spe_competencias`, `spe_tendencias` | SPE |
| `sena_cno_ocupaciones`, `sena_cno_atributos` | SENA CNO 2025 |
| `ole_ibc_sabana`, `ole_ibc_nacional` | OLE |
| `informes`, `informes_observaciones`, `insights_generados` | Informes de terceros y sus insights |
| `preguntas_asistente` | Registro anónimo de preguntas a los chats |

**Tablas agregadas/unificadas:**

| Tabla | Qué es |
|---|---|
| `vacantes_historicas` | Muestra histórica unificada (Adzuna backfill + sync de Google Jobs/LinkedIn) — la usan Tendencias, Demanda actual, Geografía y Skills |
| `muestreo_volumen` | Volumen real por keyword/mes/país, para ponderar la muestra (§6.3) |
| `tendencias_observaciones` | Serie de tendencia ya calculada — la lee `GET /tendencias` |

> Supabase responde **1000 filas por consulta**: toda lectura grande debe
> paginar. Olvidarlo trunca los datos sin error.

---

## 6. Tendencias temporales (portada, ruta `/`)

Responde "¿qué cargos y sectores están creciendo?" usando la **fecha real de
publicación** de cada vacante. Con filtro Colombia se puede alternar entre la
vista **general** y **por departamento** (mapa + detalle: foto actual, no serie).
Sutilezas necesarias antes de tocar el código:

### 6.1 El scrape normal no sirve para tendencias
`POST /scrape` trae solo las ~100 vacantes más recientes por keyword — el 91%
cae en un mismo mes. Por eso el backfill (`Tendencias/historical_collector.py`)
vive aparte y escribe en `vacantes_historicas`, que nunca se borra.

### 6.2 Cómo se llega al pasado
Adzuna no tiene filtro "publicado antes de X", pero combinar `max_days_old=D`
con `sort_direction=up` aterriza justo en el borde de edad `D`, permitiendo
muestrear cualquier mes barriendo `D`. Google Jobs y LinkedIn solo alcanzan ~2
meses hacia atrás por corrida: sin recolección periódica no hay historia.

### 6.3 Por qué la muestra se pondera
El recolector pide ~50 vacantes por keyword y mes — muestra balanceada por
construcción, no por demanda real. El campo `count` de la API da el volumen
real de la ventana; restando ventanas consecutivas se obtiene el volumen real
por mes, que pondera cada vacante muestreada (se guarda en `muestreo_volumen`).

### 6.4 La métrica es el *share*, no el conteo
Adzuna retira vacantes viejas de su índice (atrición), así que los volúmenes
absolutos no son comparables entre meses. Sí lo es el reparto **dentro** de
cada mes (`share = vacantes del término / vacantes del mes`).

### 6.5 Combinar varios países
`paises` acepta varios mercados a la vez. Se combinan **promediando el share**
de cada uno (cada país pesa igual), nunca sumando volúmenes — EE.UU. concentra
~93% del volumen estimado. Google Jobs Colombia (`pais='co'`) y LinkedIn
(`co_li`, `mx_li`, …) se mantienen como mercados **distintos** a propósito.

### 6.6 Clasificación
Regresión lineal ponderada (más peso a meses recientes) sobre la serie de
shares; la pendiente se normaliza contra la media simple y se clasifica con
umbral simétrico (±0.08) en `creciente` / `estable` / `decreciente` — con
umbrales **asimétricos** para competencias.

### 6.7 Homologación de competencias
Las competencias de O*NET homologables a las **13 habilidades generales** del
estudio "Monitoreo entorno" de Alumni Sabana se marcan en negrilla y muestran su
categoría al pasar el cursor.

### 6.8 Actualizar los datos
El Administrador dispara **Actualizar histórico** desde Tendencias (orquestador
`Tendencias/actualizacion.py`: Adzuna → Google Jobs → LinkedIn → ubicaciones →
recálculo), o corre lo mismo desde la consola, que es más cómodo para corridas
largas:

```bash
cd src/backend
python actualizar_local.py --fuentes linkedin --paises co --keywords 1 --paginas 2 --pausa 5
```

Antes de recolectar Google Jobs revisa el semáforo de cuota de SerpApi.

---

## 7. Migraciones (`src/backend/migrations/`)

| Archivo | Crea |
|---|---|
| `002_tendencias.sql` | `vacantes_historicas`, `tendencias_observaciones` |
| `003_tendencias_filtros.sql` | Columnas de segmentación en `tendencias_observaciones` |
| `004_google_jobs_tendencias.sql` | Integra Google Jobs a Tendencias/Skills |
| `005_linkedin.sql` | `vacantes_linkedin` |
| `006_informes.sql` | `informes`, `informes_observaciones` |
| `007_spe_competencias.sql` | `spe_ocupaciones`, `spe_competencias` |
| `008_spe_tendencias.sql` | `spe_tendencias` |
| `009_sena_cno.sql` | `sena_cno_ocupaciones`, `sena_cno_atributos` |
| `010_ole_ibc.sql` | `ole_ibc_sabana`, `ole_ibc_nacional` |
| `011_preguntas_asistente.sql` | `preguntas_asistente` (privacidad: ver cabecera del SQL) |
| `012_insights_generados.sql` | `insights_generados` (insights de informes, individuales y conjuntos) |

> `GoogleJobs/google_jobs_service.py` menciona un `001_vacantes_google.sql` que no
> existe en la carpeta — la tabla ya existe en producción; si se reconstruye
> desde cero, créala a mano con las columnas de §5 antes de correr `002`.

---

## 8. Variables de entorno

### Backend (`src/backend/.env`, plantilla en `.env.example`)

| Variable | Requerida | Descripción |
|---|---|---|
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | Sí | Proyecto Supabase (Project Settings → API) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Sí (para el login) | Credenciales del Administrador. **Cámbialas en el `.env` real; no las compartas** |
| `AUTH_SECRET` | Recomendada | Cadena aleatoria larga que firma los tokens. Sin ella cada reinicio del backend cierra las sesiones de Admin |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna | developer.adzuna.com |
| `SERPAPI_KEY` | Google Jobs | serpapi.com/manage-api-key |
| `SERPAPI_MAX_BUSQUEDAS` / `SERPAPI_BUSQUEDAS_MES` | Opcional | Presupuesto por corrida (def. `240`) y cupo mensual para estimar el semáforo (def. `250`) |
| `LINKEDIN_HABILITADO` | Opcional | `true` activa la recolección (def. `false`) |
| `LINKEDIN_MAX_PAGINAS` / `LINKEDIN_PAUSA_SEG` | Opcional | Tope de páginas (def. `3`) y pausa entre peticiones (def. `3` s) |
| `ANTHROPIC_API_KEY` | Documentos | Lector de PDF ad-hoc |
| `GEMINI_API_KEY` | Informes | Insights de informes (Gemini) |
| `ONET_API_KEY` | Competencias | services.onetcenter.org/developer/signup (gratis) |
| `GCP_PROJECT_ID` / `GCP_LOCATION` / `DOCAI_PROCESSOR` / `GOOGLE_APPLICATION_CREDENTIALS` | Opcional | Document AI (OCR) para PDFs escaneados |

### Frontend (`.env.local` en la raíz)

| Variable | Descripción |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | URL del backend FastAPI (def. `http://localhost:8000`) |
| `CLAUDE_API_KEY` (o `ANTHROPIC_API_KEY`) | Chat flotante (Claude), en `src/app/api/chat/route.ts` |
| `GEMINI_API_KEY` | Chat de "Empresas" (Gemini), misma ruta con `modo='empresas'` |
| `GEMINI_USD_POR_1M_ENTRADA` / `GEMINI_USD_POR_1M_SALIDA` | Precios para el costo ESTIMADO por pregunta. Def. `0.75` / `3.75` (hasta 2026-12-31; desde 2027-01-01 pasan a 1.50 / 7.50) |
| `CLAUDE_USD_POR_1M_ENTRADA` / `CLAUDE_USD_POR_1M_SALIDA` | Ídem para la burbuja. Def. `3` / `15` |
| `BACKEND_URL` | URL del backend vista desde el SERVIDOR de Next (para registrar preguntas); si falta usa `NEXT_PUBLIC_BACKEND_URL` |

> Los archivos `.env` están en `.gitignore`. Cada fuente es independiente: si
> falta una credencial, esa fuente se omite y el resto sigue funcionando.
> Tras cambiar cualquier variable, **reinicia** el proceso.

---

## 9. Cómo ejecutar en local

### Backend
```bash
cd src/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000   # http://localhost:8000/docs
```
> En Windows, si la consola no es UTF-8 define `PYTHONUTF8=1`: algunos mensajes
> de depuración llevan emojis y, sin eso, ciertas lecturas fallan con un error de `charmap`.

### Frontend
```bash
npm install
npm run dev        # http://localhost:3000
```

---

## 10. Pruebas automáticas

```bash
# Backend (45 pruebas; sin red ni Supabase real)
cd src/backend
pip install -r requirements-dev.txt
python -m pytest

# Frontend (13 pruebas) + tipos + lint
npm test
npx tsc --noEmit
npm run lint
```

- **Backend** (`src/backend/tests/`): taxonomía de sectores y refinamiento por
  título, tokens de Admin (válido, manipulado, caducado), **401 en todas las
  rutas protegidas**, normalización de seniority/escolaridad/cargos y el
  orquestador de actualización con todas sus dependencias simuladas (orden,
  aislamiento de fallos, una corrida a la vez). `conftest.py` fija variables de
  entorno ficticias: **las pruebas nunca tocan la base de datos real**.
- **Frontend** (`src/lib/__tests__/`, Vitest + jsdom): sesión de Admin
  (`authHeaders`, `SoloAdmin`), tráiler de uso del chat y utilidades del PDF.
- **CI**: `.github/workflows/tests.yml` corre todo en cada push y pull request.
- **Qué no cubren**: las páginas completas, las gráficas y las integraciones con
  Adzuna, SerpApi, LinkedIn, Gemini y Claude (se verifican a mano).

---

## 11. Despliegue

- **Frontend**: **Vercel** (Next.js en modo servidor). Define las variables del
  frontend (§8) en el proyecto de Vercel.
- **Backend**: **Render** (servicio web de Python con `uvicorn main:app`). El
  plan gratuito "duerme": la primera petición tras un rato inactivo tarda
  unos segundos. Su URL pública va en `NEXT_PUBLIC_BACKEND_URL`.
- Configura `AUTH_SECRET` en el backend desplegado: sin ella, cada reinicio de
  Render cierra la sesión del Administrador.

---

## 12. Los asistentes de IA

| | Chat flotante (páginas de análisis) | "Empresas" (`/asistente`, usuarios) |
|---|---|---|
| Modelo | Claude (`claude-sonnet-4-5`) | Gemini (`gemini-3.6-flash`) |
| Contexto | Solo los datos visibles en la página actual | `GET /asistente/contexto` — hechos reales del Observatorio |
| Alcance | Estrictamente limitado a esos datos — no inventa cifras | Puede responder más allá del dataset, etiquetando lo que no viene del Observatorio |
| Implementación | `src/lib/floating-chat.tsx` → `/api/chat` | `src/app/asistente/page.tsx` → `/api/chat?modo=empresas` |

Para el **Administrador**, `/asistente` no es un chat: es el **dashboard de uso**
de todos los usuarios (preguntas, sesiones, tokens y costo estimado por
categoría). El registro es anónimo (id aleatorio por pestaña); el texto de las
preguntas es libre y puede contener datos personales, por lo que la Universidad
debe definir una política de retención (Ley 1581 de 2012).

---

## 13. Notas / pendientes para quien continúe

- **`/conditions` y `/demand`** existen pero **no están en el nav** ni conectadas
  al backend — contenido estático, candidatas a eliminar.
- **SPE congelado**: los anexos publicados llegan hasta sep-2023; hay que cargar
  el corte nuevo a mano cuando el SPE lo publique (`SPE/cargar_tendencias.py`).
- **Dimensión `skill` en Tendencias** está reservada pero no expuesta: nunca
  acumuló suficiente historia mensual. La cubre la página **Competencias** con un
  mecanismo independiente.
- **Cursos y formación** es un buscador que abre catálogos externos; no trae
  resultados propios.
- **Fuentes evaluadas y descartadas**: Jooble (solo EE.UU.), Careerjet (datos muy
  pobres para Colombia), Talent.com / WhatJobs (requieren cuenta aprobada).
- **Problemas conocidos** y deuda técnica vigente: ver la página
  [Problemas conocidos](https://github.com/AlumniSabana/ObservatorioLaboral/wiki/Dev-Problemas-conocidos)
  de la wiki.
