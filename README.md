# Observatorio Laboral — Alumni Sabana

Plataforma web que analiza el mercado laboral para los egresados de la Universidad
de La Sabana. Recolecta ofertas de empleo de fuentes externas, las almacena en una
base de datos y las presenta en dashboards con gráficos, junto con un asistente de
IA (Claude) que ayuda a interpretar lo que se ve en cada página y a leer documentos.

> Este README es el punto de partida para entender el proyecto. Cada archivo
> importante además tiene comentarios explicativos en su cabecera.

---

## 1. Arquitectura general

El proyecto tiene **dos partes independientes** que se despliegan por separado:

```
┌─────────────────────────────┐         ┌───────────────────────────────────┐
│  FRONTEND (Next.js)          │  HTTP   │  BACKEND (FastAPI / Python)       │
│  src/app, src/lib            │ ──────► │  src/backend                      │
│  Exportación estática        │         │                                   │
│  (GitHub Pages, basePath     │         │  Recolección de vacantes:         │
│   /ObservatorioLaboral)      │         │   • Adzuna (EE.UU.) → vacantes    │
│                              │         │   • Google Jobs (Colombia)        │
│                              │         │       → vacantes_google           │
│                              │         │  Lector de PDF (Claude, efímero)  │
└──────────────┬──────────────┘         │              │                    │
               │                         │              ▼                    │
               │                         │        ┌───────────┐              │
               │                         │        │ Supabase  │              │
               │                         │        │ (Postgres)│              │
               │                         │        └───────────┘              │
               │                         └───────────────────────────────────┘
               │
               │  El chat flotante (streaming) llama a /api/chat (Next),
               ▼  que a su vez consulta la API de Anthropic (Claude).
        ┌──────────────┐
        │ Anthropic API│
        └──────────────┘
```

- **Frontend**: Next.js (App Router) en TypeScript. Se compila como sitio
  **estático** (`output: 'export'`) y se publica en GitHub Pages. Consume el
  backend vía `fetch` usando la variable `NEXT_PUBLIC_BACKEND_URL`.
- **Backend**: API REST en FastAPI (Python). Recolecta las vacantes (APIs
  externas), calcula las analíticas y lee PDFs con Claude. Guarda las vacantes en
  Supabase; el lector de PDF NO persiste nada.
- **Base de datos**: Supabase (PostgreSQL). **Una tabla por fuente**, porque cada
  fuente entrega campos distintos y mezclarlas obligaba a columnas en NULL:
  `vacantes` (Adzuna, EE.UU.) y `vacantes_google` (Google Jobs, Colombia).

---

## 2. Estructura de carpetas

```
src/
├── app/                      # Páginas del frontend (Next.js App Router)
│   ├── layout.tsx            # Layout raíz (fuentes, <html>, metadata)
│   ├── page.tsx              # Página de inicio (/)
│   ├── globals.css           # Estilos globales + paleta de colores de La Sabana
│   ├── analytics/page.tsx    # ⭐ Dashboard principal: combo box de fuentes + lector de PDF
│   ├── skills/page.tsx       # Competencias y habilidades (datos de O*NET)
│   ├── cursos/page.tsx       # Buscador de cursos (abre Google Skills / IBM Training)
│   ├── api/chat/route.ts     # Proxy (streaming) hacia Claude para el chat flotante
│   ├── salaries/             # ──┐
│   ├── sectors/              #   │ Páginas informativas con contenido ESTÁTICO
│   ├── conditions/           #   │ (placeholders, aún no conectadas al backend)
│   └── demand/               # ──┘
├── lib/
│   ├── sidebar.tsx           # Barra lateral de navegación + PageLayout reutilizable
│   ├── floating-chat.tsx     # Widget de chat flotante (asistente Claude, streaming)
│   ├── markdown.tsx          # Render de Markdown + tablas (compartido por chat y lector)
│   └── document-reader.tsx   # Modo "Leer un documento": subir PDF → Claude lo lee
└── backend/                  # API en Python (NO es parte del build de Next.js)
    ├── main.py               # Punto de entrada FastAPI: define los endpoints
    ├── config.py             # Variables de entorno + keywords por programa (inglés y español)
    ├── requirements.txt      # Dependencias de Python
    ├── migrations/
    │   └── 001_vacantes_google.sql      # SQL para crear la tabla vacantes_google
    ├── Adzuna/
    │   └── adzuna_service.py            # Recolección de Adzuna + analíticas (compartido)
    ├── GoogleJobs/
    │   └── google_jobs_service.py       # Recolección de Google Jobs (SerpApi) + analíticas CO
    ├── ONet/
    │   └── onet_service.py              # Competencias por programa (O*NET) para la página /skills
    └── Documentos/
        └── document_service.py          # Lectura de PDFs con Claude (Files API)
```

> **Importante**: `src/backend` es código Python. Next.js NO lo compila ni lo
> despliega; el backend se ejecuta en un servidor aparte.

---

## 3. Flujo de datos (cómo se llena el dashboard)

1. El usuario abre **Análisis de mercado** (`/analytics`) y elige una opción en el
   combo box: *Adzuna EE.UU.*, *Google Jobs Colombia* o *📄 Leer un documento*.
2. El frontend pide `GET /analytics?fuente=<fuente>` al backend.
3. El backend lee de Supabase **solo** las vacantes de esa fuente, calcula las
   métricas (cargos más demandados, ciudades, empresas, etc.) y las devuelve. Cada
   fuente tiene su propio dashboard, porque entrega campos distintos.
4. Para **recolectar nuevos datos**, el usuario pulsa "Actualizar Análisis", que
   dispara `POST /scrape?fuente=<fuente>&borrar=true`. El backend consulta la API
   externa, guarda en Supabase y recalcula.

El scraping recorre las keywords por programa académico (ver `config.py`) y asocia
cada vacante al programa correspondiente (`programa_relacionado`). **Las keywords
son distintas por mercado**: inglés para Adzuna (EE.UU.) y español para Google Jobs
(Colombia) — ver §8.

**Lector de documentos** (opción "📄 Leer un documento"): no consulta analíticas.
El usuario sube un PDF, que se manda al backend (`POST /documento/subir` →
`/documento/chat`), Claude lo lee y devuelve insights + responde preguntas en
streaming. **No se guarda nada en la base de datos** (es efímero; el archivo vive
temporalmente en la Files API de Claude). Ver `src/backend/Documentos/`.

---

## 4. Variables de entorno

### Frontend (`.env.local` en la raíz)
| Variable                  | Descripción                                            |
|---------------------------|--------------------------------------------------------|
| `NEXT_PUBLIC_BACKEND_URL` | URL del backend FastAPI. Por defecto `http://localhost:8000`. |
| `CLAUDE_API_KEY`          | API key de Anthropic, usada por `src/app/api/chat/route.ts`.  |

### Backend (`src/backend/.env`)
| Variable                | Requerida  | Descripción                                          |
|-------------------------|------------|------------------------------------------------------|
| `SUPABASE_URL`          | Sí         | URL del proyecto Supabase.                           |
| `SUPABASE_SERVICE_KEY`  | Sí         | Service key de Supabase (acceso de escritura).       |
| `ADZUNA_APP_ID`         | Adzuna     | Credencial de la API de Adzuna (mercado EE.UU.).     |
| `ADZUNA_APP_KEY`        | Adzuna     | Credencial de la API de Adzuna.                      |
| `SERPAPI_KEY`           | Colombia   | API key de SerpApi (Google Jobs, mercado Colombia).  |
| `SERPAPI_MAX_BUSQUEDAS` | Opcional   | Presupuesto de búsquedas por corrida (def. `240`). Ver §8. |
| `ANTHROPIC_API_KEY`     | Documentos | API key de Anthropic para el lector de PDFs (puede ser la misma que `CLAUDE_API_KEY`). |
| `ONET_API_KEY`          | Competencias | API key de O*NET Web Services (gratis) para la página de competencias (`/skills`). |

> Los archivos `.env` están en `.gitignore` y **no** se versionan. Cada fuente es
> independiente: si falta una credencial, esa fuente simplemente se omite y el
> resto sigue funcionando.

### Cómo obtener cada credencial
| Credencial | Dónde se obtiene |
|------------|------------------|
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | Supabase → Project Settings → API. |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | https://developer.adzuna.com/ → registrarse → crear app. |
| `SERPAPI_KEY` | https://serpapi.com/manage-api-key (cuenta SerpApi; plan gratis ~250 búsquedas/mes). |
| `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` | https://console.anthropic.com/ → Settings → API Keys → Create Key. |
| `ONET_API_KEY` | https://services.onetcenter.org/developer/signup (gratis; sin costo de uso). |

---

## 5. Cómo ejecutar en local

### Frontend
```bash
npm install
npm run dev        # http://localhost:3000
```

### Backend
```bash
cd src/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000   # http://localhost:8000
```
Documentación interactiva de la API (Swagger) en `http://localhost:8000/docs`.

> Tras cambiar cualquier variable en `.env`, **reinicia el proceso** (`uvicorn` lee
> las variables al arrancar; `--reload` solo vigila archivos `.py`, no el `.env`).

---

## 6. Base de datos: una tabla por fuente

Cada fuente tiene su propia tabla con exactamente los campos que esa fuente
entrega (así evitamos columnas en NULL forzadas y dashboards "rotos").

### `vacantes` — Adzuna (Estados Unidos)
| Columna               | Notas                                                          |
|-----------------------|----------------------------------------------------------------|
| `id` (bigint, PK)     | Id real de la vacante en Adzuna.                              |
| `title`, `company`    | Cargo y empresa.                                               |
| `category`            | Sector.                                                        |
| `contract_time`       | `full_time` / `part_time` / etc.                              |
| `salary_min/max`      | Salario anual.                                                 |
| `programa_relacionado`| Programa académico de La Sabana al que se asoció la vacante.   |
| `fuente`              | Histórico (siempre `'adzuna'`); ya no se usa para filtrar.    |

### `vacantes_google` — Google Jobs (Colombia)
Definida en `src/backend/migrations/001_vacantes_google.sql` (ejecutar ese script
en el SQL Editor de Supabase para crearla). La nutre Google Jobs (SerpApi):

| Columna                          | Notas                                              |
|----------------------------------|----------------------------------------------------|
| `job_id` (text, PK)              | Id real de la vacante en Google Jobs (el upsert por este id evita duplicados). |
| `title`, `company`               | Cargo y empresa.                                   |
| `location`, `city`               | Ubicación cruda y ciudad ya separada.              |
| `via`                            | Plataforma de origen (LinkedIn, Computrabajo…).    |
| `schedule_type`, `work_from_home`| Modalidad/jornada y si es remoto.                  |
| `salary_raw`                     | Salario en TEXTO (cuando viene); sin estructurar.  |
| `qualifications`/`responsibilities`/`benefits` | Secciones destacadas (las llena Google Jobs; insumo para una futura extracción con IA). |
| `description`                    | Texto completo de la oferta.                       |
| `keyword`, `programa_relacionado`| Trazabilidad de la recolección.                    |

> Google Jobs **no** entrega salario ni sector estructurados; por eso el dashboard
> de Colombia no incluye esas gráficas (se abordarían con un paso de extracción con
> IA en una fase posterior).

---

## 7. Despliegue

- El **frontend** se despliega automáticamente a **GitHub Pages** con el workflow
  `.github/workflows/nextjs.yml` en cada push a `main`. Por eso `next.config.ts`
  tiene `output: 'export'` y `basePath: '/ObservatorioLaboral'`.
- El **backend** debe desplegarse aparte (servidor/host de Python) y su URL pública
  configurarse en `NEXT_PUBLIC_BACKEND_URL`.

---

## 8. Recolección de Google Jobs (Colombia): keywords y presupuesto

Detalle importante para entender el costo y la cobertura:

- **Keywords en español.** En Colombia la mayoría de vacantes están en español, así
  que Google Jobs usa el diccionario `PROGRAMAS_KEYWORDS_CO` (`ingeniero de software`,
  `enfermero`, `analista financiero`…). Adzuna sigue con `PROGRAMAS_KEYWORDS` en
  inglés. Buscar en español aprovecha mucho mejor cada búsqueda.
- **Presupuesto de búsquedas.** En SerpApi **cada página = 1 búsqueda** (Google Jobs
  devuelve ~10 vacantes por página). El plan gratuito da ~250/mes. La recolección
  respeta el tope `SERPAPI_MAX_BUSQUEDAS` (def. 240) para no excederlo.
- **Estrategia round-robin (amplitud primero).** En vez de agotar una keyword antes
  de pasar a la siguiente, se pide la **página 1 de TODAS las keywords**, luego la
  página 2 de las que aún tengan resultados, etc., hasta gastar el presupuesto. Así
  los 29 programas quedan cubiertos primero y se maximiza la diversidad de vacantes
  sin pasarse de la cuota. (Ver `procesar_vacantes_google` en `google_jobs_service.py`.)
- Si tienes un plan de SerpApi con más cuota, sube `SERPAPI_MAX_BUSQUEDAS`.

---

## 9. Notas / pendientes para quien continúe

- Las páginas `salaries`, `sectors`, `conditions` y `demand` muestran **contenido
  estático de ejemplo**. Aún no consumen el backend; son candidatas naturales para
  conectarse a datos reales en el futuro. (`skills` ya usa O*NET y `cursos` es un
  buscador que abre Google Skills / IBM Training.)
- El asistente de chat usa la ruta de Next `src/app/api/chat/route.ts`. En modo
  exportación estática (`output: 'export'`) las rutas API de Next no corren como
  servidor; verifica el entorno donde corre el chat en producción. (El **lector de
  PDF** NO tiene este problema: va por el backend FastAPI `/documento/*`, que sí es
  un servidor siempre activo.)
- Las **tablas Markdown** del chat/lector se renderizan con un parser propio en
  `src/lib/markdown.tsx` porque no está instalado `remark-gfm`.
- Posible siguiente fase: un **paso de extracción con IA** que lea las descripciones
  de `vacantes_google` y rellene seniority, skills, experiencia y salario en SMMLV
  (hoy esos datos no vienen estructurados de la fuente).
- Para **agregar una nueva fuente** de vacantes:
  1. Si necesita su propia tabla, crea un script en `src/backend/migrations/`.
  2. Crea un servicio de recolección (+ su propia función de analíticas si aplica).
  3. Enruta la fuente en `/scrape` y `/analytics` de `main.py`.
  4. Añade la opción en `FUENTES` y un dashboard propio en `src/app/analytics/page.tsx`.
- **Fuentes evaluadas y descartadas** (para que no se reintenten en vano): **Jooble**
  (su API solo indexa EE.UU.), **Careerjet** (cubría Colombia pero con datos muy
  pobres) y los agregadores tipo *publisher* **Talent.com / WhatJobs** (requieren
  cuenta aprobada y endpoint propio). Hoy Colombia se nutre **solo de Google Jobs**,
  que es la fuente más completa. Si se quisiera más volumen, el mejor siguiente paso
  sería el de extracción con IA, no sumar agregadores incompletos.
