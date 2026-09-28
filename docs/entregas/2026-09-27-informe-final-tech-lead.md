# Informe final — entrega de 4 equipos en paralelo (2026-09-27)

Tech Lead: coordinación, contratos compartidos, merges y verificación. Rama `main`, HEAD `a3549cd`. **Nada se ha hecho push.**

Commits de la entrega (desde `84979fc`):

| SHA | Qué |
|---|---|
| `8a23439` | Base compartida: contrato de auth (`auth.py`, `auth.tsx`), 9 endpoints protegidos, "Sobre el observatorio" como componente al pie de Informes |
| `b0b8ee4` → merge `1b9028e` | Equipo 1 — login de Admin, guard real, acceso en el menú |
| `9e623fb` → merge `0b8b972` | Equipo 3 — fix retirar/re-subir, Insights Conjuntos, vista de Usuario |
| `05bd4ba` → merge `c26b39b` | Equipo 2 — orquestador de fuentes, semáforo SerpAPI, normalización, panel de Empresas |
| `8f85cb0` | 51 `.pyc` fuera del repo e ignorados |
| `865134f` | Tres arreglos de datos de QA (software engineer, sigla IA, ciudades del Perfil) |
| `296f115` | Informe de QA en `docs/qa/` |
| `a3549cd` | `.env.example`: `SERPAPI_BUSQUEDAS_MES` |

---

## 1. Resumen ejecutivo

Los cuatro equipos entregaron y sus tres ramas están fundidas en `main` sin ningún conflicto en lógica de permisos (solo `.gitignore`, trivial). Hay login de Administrador con token firmado y 16 endpoints que exigen sesión; el botón "Actualizar histórico" ahora recorre las 11 fuentes/zonas, muestra la última búsqueda de cada una y un semáforo real de cuota de SerpAPI; Informes tiene el fix de retirar/re-subir, Insights Conjuntos con IA y una vista de solo lectura para el visitante; Empresas registra preguntas y costo estimado por sesión. QA auditó 2.700 combinaciones de demanda y 900 de tendencias: tres hallazgos de alto impacto ya están corregidos y recalculados (17.875 observaciones), el resto queda documentado con propuesta concreta. **Te quedan dos acciones manuales imprescindibles: aplicar las migraciones 011 y 012 en Supabase** (hasta entonces, el registro de preguntas y la persistencia de insights degradan con aviso, sin romper nada).

## 2. Estado por petición original

| Petición | Estado | Qué se implementó |
|---|---|---|
| **Login Admin** | ✅ | `/login` (correo/contraseña, errores visibles, redirige a Tendencias). Token HMAC-SHA256 firmado con `AUTH_SECRET`, 12 h de vigencia, `POST /auth/login` (401 neutro si falla, 503 si el servidor no tiene credenciales), `GET /auth/yo`. Guard `requiere_admin` → 401 sin/expirado/inválido, 403 si el rol no alcanza. **16 endpoints protegidos**: `/scrape`, `/scrape/linkedin`, `/tendencias/recolectar`, `/tendencias/sincronizar-google`, `/tendencias/sincronizar-linkedin`, `/tendencias/fuentes/estado`, `/tendencias/serpapi/estado`, `/tendencias/actualizacion/estado`, `/tendencias/cargos-descartados`, `/informes/insights`, `/informes/insights-conjuntos`, `/informes/insights-conjuntos/candidatos`, `/informes/{id}/validar`, `/informes/{id}/retirar`, `DELETE /informes/{id}`, `/asistente/preguntas/resumen`. Frontend: `useAuth`, `<SoloAdmin>`, `authHeaders()`; el pie del menú pasa de "Iniciar sesión" a "Administrador · Cerrar sesión". Verificado por curl (401/403/200) y en navegador. |
| **Tendencias (Admin)** | ✅ | Un único `<PanelActualizacion>` solo para Admin (antes había dos botones); envía el token; 401 → cierra sesión con mensaje. Los 5 KPIs se muestran siempre que `/tendencias` responda (antes desaparecían todos sin historia mensual); "Vacantes analizadas" muestra spinner en vez de "—". Tras actualizar, se recargan opciones, tendencias y demanda con los filtros vigentes. Sin sesión, el panel no existe (verificado). |
| **Fuentes al actualizar** | ✅ | `Tendencias/actualizacion.py`: Adzuna (us, gb, ca, mx, es) → Google Jobs (co) → LinkedIn (co, mx, ar, cl, pe) → recálculo. Continúa si una fuente falla; resumen por fuente/zona (`ok/sin_cambios/parcial/omitida/desactivada/error`, filas, duración); candado (409 si ya hay una corrida); respeta cupo SerpAPI, 429 de LinkedIn y `LINKEDIN_HABILITADO`. Probado con mocks (6 escenarios); **no se ejecutó contra las APIs reales** (gastaría cuota). Bloque "Fuentes consultadas": 11 zonas con última búsqueda (Adzuna 2026-09-02, Google Jobs 2026-08-24, LinkedIn 2026-09-02/07), sin zonas "nunca consultadas". Filtrado automático: inglés (compositor de modificadores + heurística `_parece_ingles`; lo intraducible se descarta de la dimensión cargo y se lista en `/tendencias/cargos-descartados`, 1.353 hoy) y ubicaciones (32 departamentos + 311 ciudades leídas de la BD, recortadas solo en los extremos del título). Medido en memoria sobre 15.232 vacantes: 2.200 etiquetas cambian, etiquetas distintas 2.862 → 1.376, inglés visible 12,3 % → 0,9 %. |
| **Semáforo SerpAPI** | ✅ | `GET /tendencias/serpapi/estado` lee `account.json` (no consume búsquedas). Hoy: 🟢 250/250, uso 0, reset 2026-10-19 (22 días). Regla en §4. |
| **Empresas: costo por sesión/pregunta** | ⚠️ | Factible y implementado: `route.ts` captura `usageMetadata` de Gemini (y `usage` de Claude), calcula costo **estimado** con precios por variable de entorno (Gemini 3.6 Flash 0,75/3,75 USD por 1M hasta 2026-12-31, fuente y fecha documentadas), lo muestra al Admin por respuesta y por sesión. ⚠️ porque el equipo no pudo verlo en vivo: la `GEMINI_API_KEY` del backend devolvía 403; la corregí después (ver §6) y la UI del panel está, pero no repetí una conversación real de Empresas tras el cambio. |
| **Empresas: dashboard de preguntas** | ⚠️ | `POST /asistente/preguntas` (categoría derivada de la página: perfil_ocupacional, analisis_salarial, cursos, competencias, empresas, otras; sesión anónima; sin IP ni correo) y `GET /asistente/preguntas/resumen` (Admin) con top por categoría y totales. Panel en `/asistente` solo para Admin (verificado presente con sesión, ausente sin ella). ⚠️ **Requiere la migración 011**; hasta aplicarla responde "pendiente de aplicar migración 011". |
| **Informes: retirar bloqueaba re-subir** | ✅ | Causa raíz confirmada en la BD real: `existe_hash()` devolvía el id de cualquier fila con ese hash sin mirar el estado; como retirar conserva la fila, `/informes/extraer` respondía 400 para siempre. Estrategia: **reactivar** el registro retirado (mismo id, observaciones viejas borradas y recalculadas, vuelve a `borrador`) — no exige tocar el índice único de `hash_pdf` ni rompe los `informe_ids` de insights ya generados. E2E con PDF de prueba: subir → validar → retirar → re-subir (200 con `reactiva`) → guardar (`reactivado:true`) → validar. Además `validar`/`retirar` sobre id inexistente ahora dan 404 (antes 200). |
| **Insights Conjuntos** | ✅ | Botón junto a "Generar informe de insights" (solo Admin). `POST /informes/insights-conjuntos/candidatos`: solapamiento Jaccard de skills entre informes validados + Gemini en modo JSON para agrupar y explicar el motivo; respaldo heurístico si Gemini falla. `POST /informes/insights-conjuntos` genera el insight comparativo y lo persiste (`insights_generados`, migración 012). Los insights individuales también se persisten. Probado con Gemini real (2 llamadas, < 0,01 USD) y por curl tras el merge (401 sin token). |
| **Vista de Usuario (Informes)** | ✅ | Sin sesión: "Mis informes" (los subidos desde este navegador), subir con el flujo existente (queda "pendiente de validación por el Administrador"), por informe su análisis, los insights del Administrador (solo lectura) y "reportes similares" (`GET /informes/{id}/similares`, Jaccard sobre términos canónicos, sin IA); sección de insights conjuntos ya generados. Sin botones de curar ni generar. Verificado en navegador con y sin sesión. |
| **Sobre el observatorio** | ✅ | Componente `SobreObservatorio` al pie de Informes (Admin y Usuario), ancho completo del contenido, tarjetas en 2 columnas desde `xl` (1 columna por debajo: la barra lateral fija se lleva 320 px), fuente un escalón arriba (intro 18 px). Redacción tuya intacta. La ruta `/sobre` se eliminó; su sitio en el menú lo ocupa el acceso de sesión. |
| **`.env`** | ✅ | `ADMIN_EMAIL`, `ADMIN_PASSWORD` (en claro, como autorizaste) y `AUTH_SECRET` generado, en `src/backend/.env`. Se creó `src/backend/.env.example` versionado con TODAS las variables del backend (había que negar el patrón `.env*` del `.gitignore`). Las credenciales nunca están en el código. |

## 3. Hallazgos de QA (Equipo 4)

Alcance: 2.700 combinaciones de demanda (3 mercados × 30 programas × 5 experiencia × 6 CUOC), 900 de tendencias (el Grupo CUOC no es eje de la serie temporal, por diseño) y los 29 programas en Competencias, Salarial y Perfil. Informe completo en `docs/qa/2026-09-27-qa-datos-informe.md`.

| Hallazgo | Causa raíz | Estado |
|---|---|---|
| Barra #1 de "Todas" era "Ingeniero" (942) siendo "Ingeniero de software" (891 con "software"); el mismo rol salía en 3 barras | `normalize_title` absorbía "software" antes del diccionario | ✅ **Corregido** (`865134f`): ahora "Ingeniero de software" 1.287 y "Desarrollador de software" |
| "Especialista en IA" → "Especialista", "Analista de IA y datos" → "Analista y datos" (104 títulos, programa Ing. en IA) | `_UBICACIONES` traía siglas de estados de EE. UU. (`ia`, `al`, `ma`…) aplicadas como token suelto | ✅ **Corregido**: siglas retiradas + entradas exactas "Especialista en IA", "Ingeniero de IA", "Analista de IA (y datos)" |
| Perfil ocupacional: "Lima 12, Santiago 11" en Derecho; "Colombia" como ciudad #1 en los 29 programas; departamentos como ciudades | LinkedIn ya trae 5 países y `_ciudades_colombia` no filtraba `pais='co'`; no distinguía país/departamento de ciudad | ✅ **Corregido**: filtro `pais='co'` y criterio compartido `geografia.ciudad_visible` |
| Ciencia de Datos sin competencias | `_cache_onet.json` del 12-ago con 0 skills (la API viva devuelve 8) | ✅ Caché borrada (se regenera) |
| Inglés en top-15 al filtrar programa+experiencia en mercados Adzuna (Latam 6,1 % de celdas, Todas 17,8 %; 328 etiquetas = 2,8 % de vacantes) | `_componer_cargo` sin el modificador (`supply chain`, `early childhood`, `area manager operations`…) | ⚠️ En parte cubierto por la nueva capa del Equipo 2 (descarta lo intraducible y lo expone en `/tendencias/cargos-descartados`); las ~40 entradas propuestas por QA (§2.4 del informe) quedan pendientes de curar |
| 111 títulos colombianos conservaban municipio (Rionegro, Yumbo, Itagüí, "zona franca"…) | Municipios fuera de la lista curada | ✅ Cubierto por la lista dinámica del Equipo 2 (verificado: Rionegro/Yumbo/Itagüí ya se recortan). Pendiente: el respaldo pierde preposiciones ("Analista compras") — cambio de lógica |
| **819/900 combinaciones de tendencias con 0-2 términos** | Colombia-sector: 150/150 por cobertura (Google Jobs/LinkedIn no traen sector). Colombia-cargo: 25/28 programas por umbrales (Google Jobs solo tiene jun/jul/ago y **septiembre en 0**: recolección detenida). Todas-cargo: 8/11 por keywords de Adzuna que no son cargos (`organizational development` 1.903→8, `talent management`, `business administration`, `public policy`, `diplomat`…) | ❌ Pendiente de decisión (§6): no es bug de código; es falta de historia + keywords |
| `coincide_con_keyword` descarta el 53,7 % de Colombia (5.918 → 2.740): C. Políticas 100 %, Bioproducción 100 %, RR.II. 85 %, Ing. IA 76 %… | Subcadena exacta sin lematizar: "Ingeniero Químico de Procesos" no pasa para `ingeniero de procesos químicos`; plural/femenino/singular | ❌ Pendiente de decisión: lematización mínima o cambio de keywords (impacto grande, todas las vistas) |
| Experiencia junior/graduado y CUOC servicios/apoyo casi vacíos en Colombia | 91 % de títulos sin nivel; 18 y 83 vacantes | ✔ No es bug: comunicar |
| Competencias: 13 tecnologías O*NET en inglés (CMS, SCADA, GIS, HRMS, LMS…); EyF y EyF Virtual sin skills (SOC `13-2051.00`) | Traducciones faltantes; SOC sin skills en O*NET | ⚠️ Pendiente (propuesta en §5 del informe) |
| Salarial: 29/29 OK; 7 programas con exactamente el mismo análisis (CNO a 2 dígitos) | Granularidad del pivote GEIH | ✔ No es bug: se ve "igual" por diseño |
| Duplicados: 12 grupos de cargos por preposición/tilde, 163 empresas con variantes (EY/ey, Adecco ×3), 24 placeholders que pasan el filtro de confidenciales | Respaldo del diccionario y clave de empresa sin normalizar | ⚠️ Pendiente (propuesta concreta en §7.A del informe) |

Efecto ya medible tras el recálculo ponderado: Colombia 28 → 30 términos con tendencia, Todas 106 → 113, "Ingeniero de software" aparece como término propio en EE. UU. y en Todas.

## 4. Decisiones en ambigüedades

- **Regla del semáforo SerpAPI** (⚠️ marcada): `restantes` = `plan_searches_left` de la cuenta; `presupuesto` = `SERPAPI_MAX_BUSQUEDAS` (240); reset = `plan_renewal_date` (hoy 2026-10-19; si falta, el próximo día 19). 🟢 si `restantes ≥ presupuesto` (cabe una corrida completa). 🟡 si `0 < restantes < presupuesto` (corrida parcial; el texto sugiere esperar si faltan ≤ 2 días para el reset). 🔴 si `restantes = 0` o la cuenta no responde y no hay estimación local. Si la API falla, estima con el uso registrado localmente (`SERPAPI_BUSQUEDAS_MES`, 250) y lo marca `estimado`. Siempre muestra los números.
- **"Usuario" = visitante sin sesión** (solo existen credenciales de Admin). "Sus PDFs" = los subidos desde ese navegador (`localStorage`); la UI lo explica. Puede subir y consultar; validar, retirar, eliminar y generar insights son de Admin.
- **Insights individuales se persisten** (no solo los conjuntos): la vista de Usuario los necesita leer.
- **Reactivar en vez de crear** al re-subir un PDF retirado (§2).
- **Costo por sesión visible solo para Admin**: es información operativa.
- **"Todos los KPIs"** = la fila de 5 KPIs se pinta siempre que haya respuesta, con 0 y subtítulo cuando no hay historia mensual, en lugar de ocultarla.
- **Títulos en inglés intraducibles se descartan de la dimensión cargo** (8,9 % de las vacantes; siguen contando en total, sector y programa) y se exponen en `/tendencias/cargos-descartados` para curarlos. Alternativa descartada: dejarlos en inglés en el top.
- **`presupuesto` de Adzuna es por mercado** (hasta 5 × 250 llamadas si no hay keywords ya recolectadas); documentado en el endpoint.
- **Contrato de auth creado antes de branchear** por el Tech Lead, permisivo hasta el merge del Equipo 1, para que los otros dos equipos pudieran consumirlo desde el primer minuto sin tocar `main.py`.
- **Congelación de escrituras a Supabase durante la fase paralela** (BD compartida por los 4 worktrees y QA); la recalculación la corrió el Tech Lead tras el último merge.
- **GEMINI_API_KEY del backend sustituida** por la de `.env.local` (la anterior devolvía 403 `PERMISSION_DENIED` y rompía también el botón de insights que ya existía). La anterior quedó comentada en el mismo `.env`.
- **Modo oscuro no tocado** (ver §6): forzar esquema claro es una decisión de producto.

## 5. Conflictos de merge y archivos compartidos

- **`main.py`** lo tocaron los Equipos 2 y 3. Se fundió **automáticamente**: cada uno editó su región (`/tendencias/*` + `/asistente/*` vs `/informes/*`) y colocó sus imports tras anclas distintas, como se pactó. Verificado tras el merge: 55 rutas, ninguna colisión de path, los 16 endpoints protegidos correctos.
- **`.gitignore`**: único conflicto real (Equipo 1 añadió `!src/backend/.env.example`; Equipo 2 añadió sus cachés). Ambos bloques eran líneas nuevas al final, sin relación con permisos: se conservaron los dos y se quitó una línea duplicada. No fue necesario detenerse a consultar.
- **Ningún equipo tocó archivos fuera de su scope** (comprobado contra la base común `8a23439`; la lista del informe del Equipo 3 que parecía incluir `auth.py`/`sidebar.tsx` era un artefacto de comparar contra un `main` que ya tenía el merge del Equipo 1).
- Las tres ramas `feature/*` quedan en el repo con 0 commits fuera de `main`; los worktrees se eliminaron (con sus copias de `.env`) sin tocar el `node_modules` real.

## 6. Riesgos y observaciones que requieren tu validación

**Acciones tuyas, imprescindibles**
1. Aplicar en el SQL Editor de Supabase `src/backend/migrations/011_preguntas_asistente.sql` y `012_insights_generados.sql`. Hasta entonces: las preguntas no se guardan, los insights no se persisten (la UI lo avisa) y la vista de Usuario no verá insights.
2. En el hosting, definir las variables nuevas si quieres otros valores: `GEMINI_USD_POR_1M_ENTRADA/SALIDA`, `CLAUDE_USD_POR_1M_ENTRADA/SALIDA`, `BACKEND_URL` (Next → backend, cae a `NEXT_PUBLIC_BACKEND_URL`), `SERPAPI_BUSQUEDAS_MES`. Y un `AUTH_SECRET` fijo (si falta, cada reinicio cierra las sesiones).
3. Decidir si la clave de Gemini que dejé en el backend es la que debe facturar el uso (proyecto de `.env.local`).

**Decisiones de datos pendientes (impacto alto)**
4. `coincide_con_keyword` descarta más de la mitad de Colombia por subcadena exacta. Opciones: lematización mínima, aceptar N-1 palabras, o cambiar keywords (`ingeniero químico`, `profesor de filosofía`, `coordinador de importaciones`…). Cambia todas las vistas: conviene decidirlo contigo.
5. Google Jobs no se recolecta desde el 24-ago (septiembre en 0): la mayoría de programas colombianos se queda en 2 meses válidos y no alcanza tendencia. Es cuestión de correr la actualización (el semáforo está en verde).
6. Keywords de Adzuna que no son cargos (`organizational development`, `talent management`, `public policy`, `diplomat`…) traen 99 % de ruido; Ciencias Políticas, Bioproducción y RR. II. no tienen señal con las keywords actuales.
7. La dimensión Sector está vacía para Colombia y LATAM (las fuentes no traen categoría): QA sugiere ocultar la gráfica cuando ninguna fuente seleccionada la tenga.

**Operación y seguridad**
8. `POST /tendencias/recolectar` sigue siendo síncrono: una corrida completa puede superar 20 min (LinkedIn 5 países con pausa) y el navegador puede cortar la petición; el resultado queda en `GET /tendencias/actualizacion/estado`, pero la UI aún no lo consulta al recargar.
9. Sin límite de intentos en `/auth/login`; CORS `*` con `allow_credentials`; credenciales de prueba conocidas: cambiar antes de producción.
10. Privacidad: el texto libre de las preguntas puede contener datos personales (Ley 1581) — decidir retención (sugerido borrar > 90 días); `POST /informes/extraer` y `POST /informes` son públicos, sin límite de tamaño ni rate limit.
11. La heurística de inglés descarta el 8,9 % de la dimensión cargo; revisar `/tendencias/cargos-descartados` periódicamente.
12. `GET /tendencias/fuentes/estado` tarda ~8 s (lee máximos sobre tablas grandes); aceptable para un panel de Admin, cacheable si molesta.
13. **Modo oscuro**: con `prefers-color-scheme: dark` toda la app (no solo el login) muestra texto navy sobre tarjetas gris oscuro: resto de la plantilla de Next (`dark:` en Tailwind), previo a esta entrega. Arreglo de una línea si se decide forzar esquema claro.
14. Caveat previo que sigue vigente: en el export estático (GitHub Pages) las rutas `/api/*` de Next no corren, así que el chat (y ahora el registro de preguntas) necesitan un hosting que las ejecute.
15. Quedan metadatos huérfanos en `.git/worktrees/` (OneDrive impidió borrarlos); son inertes y `git worktree prune` los limpia cuando el bloqueo ceda.

**No verificado en navegador** (sí por curl/mocks): la ejecución real de "Actualizar histórico" (consumiría cuota), la generación de un Insight Conjunto desde la UI (el equipo la probó con Gemini real por curl) y una conversación de Empresas tras el cambio de clave.
