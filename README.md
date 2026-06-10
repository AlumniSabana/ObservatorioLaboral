# Observatorio Laboral — Alumni Sabana

Plataforma web que analiza el mercado laboral para los egresados de la Universidad
de La Sabana. Recolecta ofertas de empleo de fuentes externas, las almacena en una
base de datos y las presenta en dashboards con gráficos, junto con un asistente de
IA (Claude) que ayuda a interpretar lo que se ve en cada página.

> Este README es el punto de partida para entender el proyecto. Cada archivo
> importante además tiene comentarios explicativos en su cabecera.

---

## 1. Arquitectura general

El proyecto tiene **dos partes independientes** que se despliegan por separado:

```
┌─────────────────────────────┐         ┌──────────────────────────────┐
│  FRONTEND (Next.js)          │  HTTP   │  BACKEND (FastAPI / Python)  │
│  src/app, src/lib            │ ──────► │  src/backend                 │
│  Exportación estática        │         │                              │
│  Desplegado en GitHub Pages  │         │  ┌────────────────────────┐  │
│  bajo /ObservatorioLaboral   │         │  │ Adzuna  (EE.UU.)       │  │
└──────────────┬──────────────┘         │  │ Google Jobs (Colombia) │  │
               │                         │  └───────────┬────────────┘  │
               │                         │              │ guardan       │
               │                         │              ▼               │
               │                         │        ┌───────────┐         │
               │                         │        │ Supabase  │         │
               │                         │        │ (Postgres)│         │
               │                         │        └───────────┘         │
               │                         └──────────────────────────────┘
               │
               │  El chat flotante llama a una ruta API de Next (/api/chat)
               ▼  que a su vez consulta la API de Anthropic (Claude).
        ┌──────────────┐
        │ Anthropic API│
        └──────────────┘
```

- **Frontend**: Next.js (App Router) en TypeScript. Se compila como sitio
  **estático** (`output: 'export'`) y se publica en GitHub Pages. Consume el
  backend vía `fetch` usando la variable `NEXT_PUBLIC_BACKEND_URL`.
- **Backend**: API REST en FastAPI (Python). Se encarga de recolectar las vacantes
  (scraping vía APIs externas) y de calcular las analíticas. Guarda todo en
  Supabase (PostgreSQL gestionado).
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
│   ├── analytics/page.tsx    # ⭐ Dashboard principal con datos REALES del backend
│   ├── api/chat/route.ts     # Proxy hacia Claude para el asistente de IA
│   ├── trends/               # ──┐
│   ├── skills/               #   │ Páginas informativas con contenido ESTÁTICO
│   ├── salaries/             #   │ (placeholders, aún no conectadas al backend)
│   ├── sectors/              #   │
│   ├── conditions/           #   │
│   └── demand/               # ──┘
├── lib/
│   ├── sidebar.tsx           # Barra lateral de navegación + PageLayout reutilizable
│   └── floating-chat.tsx     # Widget de chat flotante (asistente Claude)
└── backend/                  # API en Python (NO es parte del build de Next.js)
    ├── main.py               # Punto de entrada FastAPI: define los endpoints
    ├── config.py             # Carga de variables de entorno y keywords por programa
    ├── requirements.txt      # Dependencias de Python
    ├── Adzuna/
    │   └── adzuna_service.py # Recolección de Adzuna + cálculo de analíticas (compartido)
    └── GoogleJobs/
        └── google_jobs_service.py  # Recolección de Google Jobs (vía SerpApi)
```

> **Importante**: `src/backend` es código Python. Next.js NO lo compila ni lo
> despliega; el backend se ejecuta en un servidor aparte.

---

## 3. Flujo de datos (cómo se llena el dashboard)

1. El usuario abre **Análisis de mercado** (`/analytics`) y elige una fuente en el
   combo box (Adzuna EE.UU. o Google Jobs Colombia).
2. El frontend pide `GET /analytics?fuente=<fuente>` al backend.
3. El backend lee de Supabase **solo** las vacantes de esa fuente, calcula las
   métricas (cargos más demandados, sectores, salarios, empresas, etc.) y las devuelve.
4. Para **recolectar nuevos datos**, el usuario pulsa "Actualizar Análisis", lo que
   dispara `POST /scrape?fuente=<fuente>&borrar=true`. El backend consulta la API
   externa correspondiente, guarda en Supabase y recalcula.

El scraping recorre `PROGRAMAS_KEYWORDS` (ver `config.py`): por cada programa
académico de La Sabana, busca varias *keywords* en la API externa y asocia cada
vacante encontrada a ese programa (`programa_relacionado`).

---

## 4. Variables de entorno

### Frontend (`.env.local` en la raíz)
| Variable                  | Descripción                                            |
|---------------------------|--------------------------------------------------------|
| `NEXT_PUBLIC_BACKEND_URL` | URL del backend FastAPI. Por defecto `http://localhost:8000`. |
| `CLAUDE_API_KEY`          | API key de Anthropic, usada por `src/app/api/chat/route.ts`.  |

### Backend (`src/backend/.env`)
| Variable               | Descripción                                          |
|------------------------|------------------------------------------------------|
| `SUPABASE_URL`         | URL del proyecto Supabase.                           |
| `SUPABASE_SERVICE_KEY` | Service key de Supabase (acceso de escritura).       |
| `ADZUNA_APP_ID`        | Credencial de la API de Adzuna.                      |
| `ADZUNA_APP_KEY`       | Credencial de la API de Adzuna.                      |
| `SERPAPI_KEY`          | API key de SerpApi (para recolectar de Google Jobs). |

> Los archivos `.env` están en `.gitignore` y **no** se versionan.

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
en el SQL Editor de Supabase para crearla). Guarda TODO lo que Google Jobs provee:

| Columna                          | Notas                                              |
|----------------------------------|----------------------------------------------------|
| `job_id` (text, PK)              | Id real de Google Jobs (no requiere hash).         |
| `title`, `company`               | Cargo y empresa.                                   |
| `location`, `city`               | Ubicación cruda y ciudad ya separada.              |
| `via`                            | Plataforma de origen (LinkedIn, Computrabajo…).    |
| `schedule_type`, `work_from_home`| Modalidad/jornada y si es remoto.                  |
| `salary_raw`                     | Salario en TEXTO (cuando viene); sin estructurar.  |
| `qualifications`/`responsibilities`/`benefits` | Secciones destacadas (insumo para extracción con IA). |
| `description`                    | Texto completo de la oferta.                       |
| `keyword`, `programa_relacionado`| Trazabilidad de la recolección.                    |

> Importante: Google Jobs **no** entrega salario ni sector estructurados; por eso
> su dashboard no incluye esas gráficas (se abordarán con un paso de extracción
> con IA en una fase posterior).

---

## 7. Despliegue

- El **frontend** se despliega automáticamente a **GitHub Pages** con el workflow
  `.github/workflows/nextjs.yml` en cada push a `main`. Por eso `next.config.ts`
  tiene `output: 'export'` y `basePath: '/ObservatorioLaboral'`.
- El **backend** debe desplegarse aparte (servidor/host de Python) y su URL pública
  configurarse en `NEXT_PUBLIC_BACKEND_URL`.

---

## 8. Notas / pendientes para quien continúe

- Las páginas `trends`, `skills`, `salaries`, `sectors`, `conditions` y `demand`
  muestran **contenido estático de ejemplo**. Aún no consumen el backend; son
  candidatas naturales para conectarse a datos reales en el futuro.
- El asistente de chat usa la ruta de Next `src/app/api/chat/route.ts`. Ten en
  cuenta que en modo exportación estática (`output: 'export'`) las rutas API de
  Next no se ejecutan como servidor; verifica el entorno donde corre el chat en
  producción.
- Para **agregar una nueva fuente** de vacantes:
  1. Crea su tabla con un script en `src/backend/migrations/`.
  2. Crea un servicio análogo a `GoogleJobs/google_jobs_service.py` (recolección
     + su propia función `get_analytics_*`).
  3. Enruta la fuente en los endpoints `/scrape` y `/analytics` de `main.py`.
  4. Añade la opción en `FUENTES` y un dashboard propio en
     `src/app/analytics/page.tsx`.
- Sobre el `id` de Google Jobs: usamos el `job_id` real (texto) como clave
  primaria de `vacantes_google`. (En `vacantes`/Adzuna el id es el numérico de
  Adzuna.) Cada fuente maneja su propia clave en su propia tabla.
