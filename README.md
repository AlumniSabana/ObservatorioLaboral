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
┌─────────────────────────────┐         ┌───────────────────────────────────┐
│  FRONTEND (Next.js)          │  HTTP   │  BACKEND (FastAPI / Python)       │
│  src/app, src/lib            │ ──────► │  src/backend                      │
│  Exportación estática        │         │                                   │
│  (GitHub Pages, basePath     │         │  Recolección de vacantes:         │
│   /ObservatorioLaboral)      │         │   • Adzuna (EE.UU.) → vacantes    │
│                              │         │   • Google Jobs + Careerjet (CO)  │
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
  Supabase (PostgreSQL gestionado); el lector de PDF NO persiste nada.
- **Base de datos**: Supabase (PostgreSQL). **Una tabla por fuente**, porque cada
  fuente entrega campos distintos y mezclarlas obligaba a columnas en NULL:
  `vacantes` (Adzuna, EE.UU.) y `vacantes_google` (Colombia: Google Jobs +
  agregadores como Careerjet).

---

## 2. Estructura de carpetas

```
src/
├── app/                      # Páginas del frontend (Next.js App Router)
│   ├── layout.tsx            # Layout raíz (fuentes, <html>, metadata)
│   ├── page.tsx              # Página de inicio (/)
│   ├── globals.css           # Estilos globales + paleta de colores de La Sabana
│   ├── analytics/page.tsx    # ⭐ Dashboard principal: combo box de fuentes + lector de PDF
│   ├── api/chat/route.ts     # Proxy (streaming) hacia Claude para el chat flotante
│   ├── trends/               # ──┐
│   ├── skills/               #   │ Páginas informativas con contenido ESTÁTICO
│   ├── salaries/             #   │ (placeholders, aún no conectadas al backend)
│   ├── sectors/              #   │
│   ├── conditions/           #   │
│   └── demand/               # ──┘
├── lib/
│   ├── sidebar.tsx           # Barra lateral de navegación + PageLayout reutilizable
│   ├── floating-chat.tsx     # Widget de chat flotante (asistente Claude, streaming)
│   ├── markdown.tsx          # Render de Markdown + tablas (compartido por chat y lector)
│   └── document-reader.tsx   # Modo "Leer un documento": subir PDF → Claude lo lee
└── backend/                  # API en Python (NO es parte del build de Next.js)
    ├── main.py               # Punto de entrada FastAPI: define los endpoints
    ├── config.py             # Carga de variables de entorno y keywords por programa
    ├── requirements.txt      # Dependencias de Python
    ├── migrations/
    │   └── 001_vacantes_google.sql      # SQL para crear la tabla vacantes_google
    ├── Adzuna/
    │   └── adzuna_service.py            # Recolección de Adzuna + analíticas (compartido)
    ├── GoogleJobs/
    │   └── google_jobs_service.py       # Recolección de Google Jobs (vía SerpApi)
    ├── Agregadores/
    │   └── aggregator_service.py        # Careerjet/Talent/WhatJobs → nutren vacantes_google (dedup)
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
   métricas (cargos más demandados, sectores, salarios, empresas, etc.) y las devuelve.
4. Para **recolectar nuevos datos**, el usuario pulsa "Actualizar Análisis", lo que
   dispara `POST /scrape?fuente=<fuente>&borrar=true`. El backend consulta la API
   externa correspondiente, guarda en Supabase y recalcula.

El scraping recorre `PROGRAMAS_KEYWORDS` (ver `config.py`): por cada programa
académico de La Sabana, busca varias *keywords* en la API externa y asocia cada
vacante encontrada a ese programa (`programa_relacionado`).

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
| Variable               | Requerida | Descripción                                          |
|------------------------|-----------|------------------------------------------------------|
| `SUPABASE_URL`         | Sí        | URL del proyecto Supabase.                           |
| `SUPABASE_SERVICE_KEY` | Sí        | Service key de Supabase (acceso de escritura).       |
| `ADZUNA_APP_ID`        | Adzuna    | Credencial de la API de Adzuna (mercado EE.UU.).     |
| `ADZUNA_APP_KEY`       | Adzuna    | Credencial de la API de Adzuna.                      |
| `SERPAPI_KEY`          | Colombia  | API key de SerpApi (Google Jobs, mercado Colombia).  |
| `ANTHROPIC_API_KEY`    | Documentos| API key de Anthropic para el lector de PDFs (puede ser la misma que `CLAUDE_API_KEY`). |
| `CAREERJET_AFFILIATE_ID`| Opcional | Affiliate ID de Careerjet; **nutre** la tabla de Colombia con más vacantes. |
| `CAREERJET_LOCALE`     | Opcional  | País/idioma del índice Careerjet. Por defecto `es_CO` (Colombia). |
| `TALENT_PUBLISHER_ID`  | Opcional  | Credencial de *publisher* de Talent.com (ver §9). Sin ella, el adaptador se omite. |
| `WHATJOBS_PUBLISHER_ID`| Opcional  | Credencial de *publisher* de WhatJobs (ver §9). Sin ella, el adaptador se omite. |

> Los archivos `.env` están en `.gitignore` y **no** se versionan. Cada fuente es
> independiente: si falta una credencial, esa fuente simplemente se omite y el
> resto sigue funcionando.

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

### `vacantes_google` — Mercado Colombia (multi-fuente)
Definida en `src/backend/migrations/001_vacantes_google.sql` (ejecutar ese script
en el SQL Editor de Supabase para crearla). Aunque el nombre dice "google", esta
tabla es el **dataset unificado de Colombia**: la nutren Google Jobs (SerpApi) y
los agregadores (Careerjet/Talent/WhatJobs — ver §9), todos con el mismo esquema:

| Columna                          | Notas                                              |
|----------------------------------|----------------------------------------------------|
| `job_id` (text, PK)              | Google Jobs: id real. Agregadores: `"<fuente>:<hash>"` derivado de la clave de dedup. |
| `title`, `company`               | Cargo y empresa.                                   |
| `location`, `city`               | Ubicación cruda y ciudad ya separada.              |
| `via`                            | Plataforma de origen (LinkedIn, Computrabajo…). Careerjet no la informa → queda como `'careerjet'`. |
| `schedule_type`, `work_from_home`| Modalidad/jornada y si es remoto.                  |
| `salary_raw`                     | Salario en TEXTO (cuando viene); sin estructurar.  |
| `qualifications`/`responsibilities`/`benefits` | Secciones destacadas (las llena Google Jobs; insumo para extracción con IA). |
| `description`                    | Texto completo de la oferta.                       |
| `keyword`, `programa_relacionado`| Trazabilidad de la recolección.                    |

> Importante: estas fuentes **no** entregan salario ni sector estructurados; por
> eso el dashboard de Colombia no incluye esas gráficas (se abordarán con un paso
> de extracción con IA en una fase posterior).

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
  producción. (El **lector de PDF** NO tiene este problema: va por el backend
  FastAPI `/documento/*`, que sí es un servidor siempre activo.)
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

---

## 9. Fuentes adicionales (agregadores) para Colombia

Para traer **más** vacantes de Colombia sin crear tablas nuevas, hay adaptadores
que escriben en `vacantes_google` (ver `src/backend/Agregadores/aggregator_service.py`).
Se ejecutan junto con Google Jobs cuando se pulsa "Actualizar Análisis" en la
pestaña *Google Jobs — Colombia* (`/scrape?fuente=google_jobs` → `procesar_colombia`).

| Fuente | Estado | Credencial |
|--------|--------|------------|
| **Careerjet** | Funcional (API pública, índice CO vía `es_CO`) | `CAREERJET_AFFILIATE_ID` |
| **Talent.com** | Adaptador listo; falta confirmar endpoint de *publisher* | `TALENT_PUBLISHER_ID` |
| **WhatJobs** | Adaptador listo; falta confirmar endpoint de *publisher* | `WHATJOBS_PUBLISHER_ID` |

Cada fuente que no tenga su credencial **se omite automáticamente** (no rompe el
resto). Talent.com/WhatJobs son programas de *publisher*: su endpoint y nombres de
campo dependen de tu cuenta, así que están marcados con `TODO(publisher)` en el
código para que los ajustes con la documentación que te entreguen al registrarte.

> **Careerjet — notas de integración** (ya resueltas en el adaptador, pero útiles
> si algo falla): su API pública sirve por **HTTP**, no HTTPS (el puerto 443
> rechaza la conexión), y **exige un header `Referer`** o responde *"Undeclared
> referrer"*. Ambos están fijados en `aggregator_service.py` (`_CAREERJET_URL`,
> `_CAREERJET_REFERER`). El campo `site` (bolsa de origen) suele venir vacío, por
> eso esas vacantes quedan con `via = 'careerjet'`.

**Deduplicación**: como estos agregadores re-indexan las mismas bolsas que Google
Jobs, antes de insertar se compara contra lo ya guardado con una clave normalizada
(cargo + empresa + ciudad, sin acentos/mayúsculas/puntuación). Si ya existe, no se
duplica. Por eso la tabla crece sin inflar los conteos.

### Cómo obtener cada credencial (backend)

| Credencial | Dónde se obtiene |
|------------|------------------|
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | Supabase → Project Settings → API. |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | https://developer.adzuna.com/ → registrarse → crear app. |
| `SERPAPI_KEY` | https://serpapi.com/manage-api-key (cuenta SerpApi; plan gratis ~100 búsquedas/mes). |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ → Settings → API Keys → Create Key. |
| `CAREERJET_AFFILIATE_ID` | https://www.careerjet.com/partners/api/ → crear cuenta de partner (gratis); entregan un Affiliate ID. Usa `CAREERJET_LOCALE=es_CO` para Colombia. |
| `TALENT_PUBLISHER_ID` | https://www.talent.com/publishers → registrarse como publisher; ellos entregan credencial + spec del feed. |
| `WHATJOBS_PUBLISHER_ID` | https://www.whatjobs.com/affiliates → programa de publisher; entregan credencial + spec del feed. |

> Recuerda: tras agregar o cambiar cualquier variable en `src/backend/.env`, hay
> que **reiniciar `uvicorn`** (las variables se leen al arrancar el proceso).
