# QA de Datos — ObservatorioLaboral (Equipo 4)

Fecha: 2026-09-27 · Rama `main` (solo lectura) · Datos leídos de Supabase el 27-sep 17:00 (volcado único, paginado de a 1000).
Alcance: página **Tendencias** (4 gráficas de demanda + serie temporal) en sus 3 conjuntos de mercados, y las páginas **Competencias**, **Análisis salarial** y **Perfil ocupacional** para los 29 programas. Fuera de scope: Empresas/asistente e Informes.

Todo se ejecutó **importando los módulos del backend en proceso** (no se cargó el servidor compartido; 0 escrituras en BD ni en el repo). Los volcados, CSV y scripts están en
`C:\Users\esteb\AppData\Local\Temp\claude\C--Users-esteb-OneDrive-Documentos-GitHub-Reto-Alumni\5a564085-32ac-4a54-bf66-6213efa41112\scratchpad\qa-datos\` (las tablas completas están en `tablas.md`; aquí van las relevantes).

---

## Resumen ejecutivo (lo que más pesa)

| # | Hallazgo | Impacto | Tipo |
|---|---|---|---|
| 1 | **La barra #1 de "Todas" ("Ingeniero", 942 vacantes) es en realidad "Ingeniero de software"**: `normalize_title` colapsa `software engineer` → `engineer` (891/942 títulos traen "software"). El mismo rol aparece en 3 barras ("Ingeniero" 942, "Ingeniero software" 19, "Ingeniero de software" 12). | Alto — es lo primero que ve el usuario | Cambio de lógica (Tech Lead) |
| 2 | **Sector en Colombia está vacío siempre** (150/150 combinaciones sin datos; la gráfica "Sectores" queda en blanco): Google Jobs y LinkedIn no traen `category` (3.987 + 1.931 filas sin sector). En Latinoamérica el sector #1 es "Sin especificar" (412) por el mismo motivo. | Alto | No es bug: cobertura de fuente (documentar/ocultar) |
| 3 | **Perfil ocupacional cuenta ciudades extranjeras como colombianas**: `_ciudades_colombia` suma LinkedIn sin filtrar `pais=='co'` → Derecho muestra "Lima 12, Santiago 11"; Ing. Civil "Santiago 8, Lima 6"; Gastronomía "Santiago 7". Además "Colombia" aparece como ciudad en 29/29 programas (393 filas de Google con `city='Colombia'`) y hay departamentos listados como ciudad (Antioquia, Valle del Cauca, Risaralda). | Alto | Bug de lógica (Tech Lead) |
| 4 | **`_UBICACIONES` incluye siglas de estados de EE. UU. de 2 letras que borran palabras españolas**: `ia` (Iowa) elimina "IA" → `Especialista en IA` → "Especialista", `Ingeniero IA` → "Ingeniero", `Analista de IA y Datos` → "Analista y datos" (104 títulos colombianos afectados). También `al` (178 títulos, "Servicio al Cliente"), `in`, `ma` (M&A), `ok`, `on`, `or`, `to`, `us`. | Medio-alto (programa Ing. IA) | Fix trivial de datos + regla |
| 5 | **Etiquetas de respaldo mutiladas** (sin preposiciones): el 37% de las vacantes colombianas cae al nivel "respaldo" de `traducir_cargo`, y en 682 (25% de Colombia) `normalize_title` ya había quitado "de/la/en/y" → "Analista inversiones", "Analista riesgos", "Ingeniero software", "Jefe seguridad cadena suministro". Parte en dos la misma barra: "Analista de inversiones" (89) vs "Analista inversiones" (4). | Medio | Cambio de lógica + fix de diccionario |
| 6 | **Pocos datos en Tendencias** es sobre todo (c) *umbrales/periodos* en Colombia (Google Jobs solo tiene 3 meses: jun 57, jul 951, ago 1.311; septiembre 0) y (b) *filtro agresivo* en "Todas" (keywords Adzuna amplias: `organizational development` 1.903→8, `talent management` 2.324→15, `business administration` 1.967→14, `international business` 1.568→17). Ciencias Políticas, Ing. de Bioproducción y Relaciones Internacionales quedan en 0 en los 3 mercados. | Alto (percepción "no hay datos") | Mixto: datos (keywords), no-bug (periodos) |
| 7 | **Inglés**: el top-15 principal (Todas / sin filtros) está 100% en español y **Colombia tiene 0 etiquetas en inglés puro** en sus 2.121 celdas. El inglés aparece al filtrar por programa + experiencia/CUOC en Latinoamérica (152 celdas, 6%) y Todas (658 celdas, 18%), con etiquetas de muy bajo volumen (328 etiquetas = 430 vacantes, 2,8% del total). Patrón: `_componer_cargo` no conoce el modificador/núcleo (`supply chain`, `area manager`, `operations`, `early childhood`, `digital marketing`). | Medio | Fix trivial de diccionario |
| 8 | **Ubicaciones en cargos**: 701 títulos colombianos (11,8%) traen ciudad; la canonización quita el 84%; **111 sobreviven** con municipios que no están en `_UBICACIONES` (Rionegro 14, Yumbo 13, "zona franca" 9, Itagüí 6, Pitalito 5, "zona norte/sur" 5+5, Villeta, Buenaventura, Palmira, Tenjo…). En el top-15 visible solo 7 etiquetas (1-2 vacantes c/u). | Bajo-medio | Fix trivial de datos |
| 9 | **Competencias vacías** para Ciencia de Datos (caché en disco `_cache_onet.json` del 12-ago con 0 competencias; la API viva devuelve 8 → borrar caché) y para Economía y Finanzas Internacionales / Virtual (O*NET 13-2051.00 no expone *skills* ni en la API viva → revisar código SOC). | Medio | Fix trivial (caché) + revisión de mapeo |
| 10 | Empresas: 24 nombres placeholder pasan el filtro ("Confidential Careers" 11, "Confidential Jobs" 4, "Our Client", "Importante empresa del sector X" ×8); 163 empresas con variantes de caso/sufijo (EY/ey 45, Adecco ×3 41, MANPOWER ×2 40, Accenture ×3 23). | Bajo | Fix trivial |

---

## 1. Alcance recorrido

### 1.1 Matriz de demanda (`demanda_actual`: cargos + sectores + empresas + programas en cada llamada)

| Mercado | Combinaciones evaluadas | Programas | Experiencia | Grupo CUOC | Con datos (total>0) | Con ≥15 vacantes |
|---|---|---|---|---|---|---|
| Colombia (`co`,`co_li`) | 900 | 30 (29 + TODOS) | 5 (4 + TODOS) | 6 (5 + TODOS) | 300 | 140 |
| Latinoamérica (`mx`,`co`,`co_li`,`mx_li`,`ar_li`,`cl_li`,`pe_li`) | 900 | 30 | 5 | 6 | 332 | 163 |
| Todas (11 mercados con datos) | 900 | 30 | 5 | 6 | 462 | 230 |
| **Total** | **2.700** | | | | | |

Método: se enriqueció el histórico UNA vez con las mismas funciones del backend (`coincide_con_keyword`, `es_pertinente`, `detectar_seniority`, `detectar_escolaridad`, `traducir_cargo(normalize_title())`, `agrupar_sector(traducir_sector())`, `_es_empresa_confidencial`) y se replicó la agregación. **Validación contra `demanda_actual` real en 210 combinaciones**: totales idénticos 210/210; las listas top-15 son idénticas en 89 y en las 121 restantes difieren solo en el orden de empates en la frontera del top-15 (`Counter.most_common` depende del orden de inserción). `validacion_demanda.csv`.

### 1.2 Matriz de tendencias (`construir_tendencias`)

| Mercado | Dimensión | Combinaciones | `sin_datos` | 0-2 términos | Términos con tendencia |
|---|---|---|---|---|---|
| Colombia | cargo | 150 | 94 | 146 | 89 |
| Colombia | sector | 150 | **150** | 150 | 0 |
| Latinoamérica | cargo | 150 | 90 | 142 | 157 |
| Latinoamérica | sector | 150 | 116 | 145 | 46 |
| Todas | cargo | 150 | 85 | 110 | 465 |
| Todas | sector | 150 | 87 | 126 | 193 |
| **Total** | | **900** | | | 950 |

150 = 30 programas × 5 niveles de experiencia. **El Grupo CUOC no es un eje del motor de tendencias** (solo alimenta `demanda_actual`; ver docstring de `Tendencias/escolaridad.py` y `recalcular_todo`), así que Dimensión × Programa × Experiencia × CUOC en la serie no existe: cuando el usuario cambia CUOC, solo cambian las 4 gráficas de demanda, no la serie. Se leyó el volcado de `tendencias_observaciones` (18.027 filas, recalculadas el 2026-09-11 14:09) con el lector parchado en memoria (misma semántica que `leer_observaciones`).

### 1.3 Por programa (29)

Competencias: `skills_demandadas` × {competencia, tecnología} × {us (defecto de la página), Colombia, Latinoamérica, Todas} + `evolucion_skills`; Salarial: `salario_por_programa`; Perfil: `construir_perfil_ocupacional(programa, ['us'])` (como llama la página) + `tendencia_programa` en los 3 conjuntos. **29/29 respondieron sin excepción.** Geografía: `resumen_departamentos` nacional y 3 programas (en vivo: 6 lecturas).

### 1.4 No recorrido

- Filtros de rango de fechas `desde`/`hasta` de la serie (no cambian los términos, solo recortan la serie).
- `top` distinto de 15 en demanda y sin `top` en la serie (la UI manda 15 / ninguno).
- Dimensión `skill` de la serie (Google Jobs) — pertenece a la página Competencias, no a los filtros auditados.
- Perfil con `paises` ≠ `us` (la página no lo envía).

---

## 2. Hallazgos de inglés

### 2.1 Cifras

| Universo | Etiquetas distintas | Inglés puro | Mixto | Anglicismo aceptado | Español |
|---|---|---|---|---|---|
| Cargos visibles en algún top-15 o serie | 1.189 | 328 (27,6%) | 79 | 22 | 760 |

| Mercado | Celdas top-15 de cargos (Programa×Experiencia×CUOC) | Inglés puro | Mixto | Anglicismo |
|---|---|---|---|---|
| Colombia | 2.121 | **0** | 56 | 99 |
| Latinoamérica | 2.502 | 152 (6,1%) | 60 | 152 |
| Todas | 3.693 | 658 (17,8%) | 147 | 214 |

- Vista principal (Todas, sin filtros): top-15 100% español ("Ingeniero", "Enfermero(a) registrado(a)", "Fisioterapeuta", "Analista financiero", "Científico de datos"…).
- **Series de tendencias: 0 términos en inglés** entre los 950 con tendencia (los umbrales de volumen ya filtran la cola).
- **Sectores: 0 en inglés** (18 grupos económicos en español).
- Las 328 etiquetas en inglés representan **430 vacantes** (2,8% de las 15.232 tras filtro): son cola larga que solo aflora al combinar programa + experiencia + CUOC en mercados Adzuna (us/gb/ca/mx/es).
- Combinaciones con más inglés en el top-15 (Experiencia=TODOS, CUOC=TODOS): Latinoamérica/Administración de Empresas 6 (`Area manager operations`, `Ib ob area manager operations`, `Station manager last mile operations`…), Todas/Fisioterapia 6, Latinoamérica/Ing. Mecánica 5, Todas/Lic. Educación Infantil 5, Todas/Relaciones Internacionales 5 (18,8% de sus 32 vacantes), Todas/Ing. Química 4. Con experiencia+CUOC activos llegan a 8-11 etiquetas (Todas / Adm. Mercadeo y Logística / graduado: 11).
- "Mixto" en Colombia (56 celdas) son títulos españoles con tecnicismos: `Desarrollador full stack java angular`, `Ingeniero inteligencia artificial python llms y rag`, `Project marketing digital y redes sociales` (este sí es inglés: `project`).

### 2.2 Tabla: top etiquetas en inglés (por vacantes que representan)

| Etiqueta | Vacantes | Países | Programa |
|---|---|---|---|
| Digital marketing | 7 | ca:4;us:2;gb:1 | Adm. Mercadeo y Logística |
| Graduate engineer structural | 5 | us:5 | Ingeniería Civil |
| Area manager operations | 5 | es:3;mx:2 | Administración de Empresas |
| Robotics engineer | 5 | us:5 | Ing. Informática / Ing. IA |
| Supply chain analyst | 4 | us:3;mx:1 | Adm. Mercadeo y Logística |
| Area manager ixd operations | 4 | mx:4 | Administración de Empresas |
| Flight engineer | 4 | us:3;gb:1 | Ingeniería Informática |
| Tech generalist engineer | 4 | es:4 | Ingeniería Informática |
| Financial plant analyst | 4 | mx:4 | Economía y Finanzas Int. |
| Investment banking mergers acquisitions analyst | 4 | us:4 | Economía y Finanzas Int. |
| Supply chain manager | 4 | gb:2;es:1;mx:1 | Adm. Mercadeo y Logística |
| Net engineer | 4 | us/gb/es/mx | Ing. Informática / Ing. IA |
| Supply chain material analyst | 3 | mx:3 | Adm. Mercadeo y Logística |
| Special education teacher preschool | 3 | us:3 | Lic. Educación Infantil |
| Ib ob area manager operations | 3 | mx:3 | Administración de Empresas |
| Infant toddler preschool school age teachers locations | 3 | us:3 | Lic. Educación Infantil |
| Early childhood teachers teacher assistants | 3 | us:3 | Lic. Educación Infantil |
| Engineering civils construction | 3 | gb:3 | Ingeniería Civil |
| Bank chef manager | 3 | gb:3 | Gastronomía |
| Android engineer | 3 | us:2;mx:1 | Ing. IA / Ing. Informática |

Lista completa (328): `ingles_cargos.csv` (columnas `veredicto`, `paises`, `fuentes`, `programas`, `combos_demanda`, `ejemplo_titulo`); top 60: `ingles_top60.csv`.

### 2.3 Patrón (por qué queda en inglés)

`traducir_cargo` llega a la capa 4 (`_componer_cargo`) y devuelve `None` porque (i) el **modificador no está en `_MODIFICADORES`** o (ii) la **última palabra no está en `_NUCLEOS`**. Núcleos finales más frecuentes de las etiquetas en inglés: `engineer` 47, `analyst` 39, `manager` 28, **`operations` 20**, **`marketing` 11**, `intern` 9, `teachers` 7, `structural` 5 (orden invertido "graduate engineer structural"), `chain` 4, `preschool` 4. Bigramas: **`supply chain` 42**, `early childhood` 19, `digital marketing` 18, `area manager` 16, `manager operations` 14, `vice president` 10, `special education (teacher)` 10, `customer service` 9, `engineering intern` 8, `head of` 8, `export manager` 6, `investment banking` 6, `research analyst` 5, `robotics engineer` 5.

### 2.4 PROPUESTA de entradas (para `traducciones.py`; no aplicadas)

`_MODIFICADORES` (compuestos primero): `"supply chain": "de cadena de suministro"`, `"early childhood": "de primera infancia"` (ya existe como `early childhood`; falta cubrir "early childhood teachers teacher assistants" → añadir `"teacher assistant": "Auxiliar docente"` en CARGOS), `"special education": "de educación especial"` (existe; falla porque el núcleo va antes: ver regla de orden), `"investment banking": "de banca de inversión"`, `"research": "de investigación"`, `"robotics": "de robótica"`, `"flight": "de vuelo"`, `"android": "Android"`, `"net": ".NET"`, `"plant": "de planta"`, `"commissioning": "de puesta en marcha"`, `"reliability": "de confiabilidad"`, `"electromechanical": "electromecánico"`, `"generalist": "generalista"`, `"export": "de exportaciones"`, `"compliance": "de cumplimiento"`, `"last mile": "de última milla"`.
`_NUCLEOS`: `"operations": "Gerente de operaciones"` (solo con `area/station/facility manager` delante → mejor entrada CARGOS `"area manager operations": "Gerente de área (operaciones)"`, `"station manager last mile operations": "Gerente de estación (última milla)"`), `"marketing": "Especialista en marketing"` (para `digital marketing` → CARGOS `"digital marketing": "Marketing digital"`), `"intern": "Practicante"`, `"internship": "Practicante"`, `"apprenticeship": "Aprendiz"`, `"president": "Vicepresidente"` (con `vice`), `"teachers": "Docente"` (existe), `"structural": "Ingeniero estructural"` (para "graduate engineer structural" → CARGOS `"graduate engineer structural": "Ingeniero estructural"`).
CARGOS directos: `"supply chain analyst": "Analista de cadena de suministro"`, `"supply chain manager": "Gerente de cadena de suministro"`, `"supply chain coordinator": "Coordinador de cadena de suministro"`, `"supply chain specialist": "Especialista en cadena de suministro"`, `"supply chain intern": "Practicante de cadena de suministro"`, `"special education teacher preschool": "Docente de educación especial (preescolar)"`, `"preschool classroom teacher": "Docente de preescolar"`, `"preschool vpk teacher": "Docente de preescolar"`, `"bank chef manager": "Chef gerente"`, `"private client lawyer": "Abogado de clientes privados"`, `"corporate tax lawyer": "Abogado tributario corporativo"`, `"software engineering intern": "Practicante de ingeniería de software"`, `"civil engineering intern": "Practicante de ingeniería civil"`, `"mechanical engineering higher apprenticeship": "Aprendiz de ingeniería mecánica"`.
Regla adicional (lógica, Equipo 2): en `_componer_cargo`, si `tokens[-1]` no es núcleo pero `tokens[0]` sí lo es (`graduate engineer structural`, `consulting engineer structural engineering analysis`), probar núcleo al inicio.

---

## 3. Hallazgos de ubicaciones en cargos

### 3.1 Etiquetas visibles con ubicación/modalidad (top-15 de alguna combinación)

| Etiqueta | Ubicación | Vacantes | País | Programa | Patrón del título |
|---|---|---|---|---|---|
| Analista operaciones comercio exterior y operación zona franca | zona franca | 2 | co | Adm. Negocios Internacionales | 'en Ciudad' |
| Asistente marketing digital teletrabajo | (modalidad) teletrabajo | 2 | co | Adm. Mercadeo y Logística | guion ' - ' |
| Ingeniero infraestructura física y mantenimiento palmira | palmira | 1 | co | Ingeniería Mecánica | barra / |
| Ingeniero jefe calidad y produccion tenjo parque san isidro | tenjo | 1 | co | Ingeniería Industrial | barra / |
| Investigador campo santander barrancabermeja | barrancabermeja | 2 | co | Filosofía | barra / |
| Jefe tecnología y comunicaciones yumbo | yumbo | 1 | co | Comunicación Corporativa | guion ' - ' |
| Terapeuta integral fisico y respiratorio ubaté domiciliario ubaté | ubaté | 1 | co | Fisioterapia | guion ' - ' |

Solo 7 etiquetas y de 1-2 vacantes: **la canonización actual funciona bien para las ciudades grandes**; el problema es de cobertura de municipios medianos y de "zonas".

### 3.2 Títulos crudos colombianos con ubicación (5.918 filas `co`+`co_li`)

| Patrón textual | Títulos | Sobreviven en la etiqueta final |
|---|---|---|
| guion ` - Ciudad` (final o medio) | 365 | 55 |
| pegado al final/medio sin separador | 158 | 23 |
| barra `/ Ciudad` | 76 | 20 |
| pipe `| Ciudad` | 32 | 1 |
| paréntesis `(Ciudad)` / `(Híbrido en Bogotá)` | 28 | 1 |
| `en Ciudad` / `para laborar en Ciudad` | 23 | 6 |
| coma `, Ciudad` | 12 | 1 |
| código numérico (`#4821 …`, `… 1626114038-742`) | 5 | 4 |
| `sede Bogota` / `ciudad de cali` | 2 | 0 |
| **Total** | **701 (11,8%)** | **111 (15,8% de ellos)** |

Ejemplos reales: `Analista de Crédito y Cartera/ Bogotá / $2.500.000`, `Científico De Datos (Modelos/ML)- Híbrido en Bogotá`, `Líder de Calidad de Plantas | Centro Productivo de Tocancipá` (sobrevive), `Ingenier@ Mecánico /para laborar en Yumbo` (sobrevive: "Ingenier mecánico laborar yumbo"), `Enfermero/a PYM (ambulatorio) Caucasia` (sobrevive), `307482 Community Manager Itagüí y zonas cercanas` (sobrevive el número no, pero "Itagüí" sí en otros), `Director de logistica sede Bogota` → "Director logistica sede" (queda "sede").

### 3.3 Municipios/zonas que sobreviven (no están en `_UBICACIONES`) — PROPUESTA de entradas

`rionegro` 14, `yumbo` 13, `zona franca` 9, `itagui` 6, `pitalito` 5, `zona norte` 5, `zona sur` 5, `villeta` 4, `buenaventura` 4, `palmira` 4, `fusagasuga` 3, `tenjo` 3, `fontibon` 3, `barrancabermeja` 3, `girardot` 3, `tocancipa` 3, `engativa` 3, `paipa` 3, `caqueta` 2, `girardota` 2, `giron` 2, `sopo` 2, `facatativa` 2, `dosquebradas` 2, `envigado` 2, `ubate` 2, `piedecuesta`, `caucasia`, `galapa`, `sogamoso`, `marinilla`, `gachancipa`. También modalidad: `teletrabajo`, `domiciliario/a`, `sede`, `laborar`, `zonas cercanas`. Bigramas a `_BIGRAMAS_PROTEGIDOS` con valor vacío: `"zona franca"`, `"zona norte"`, `"zona sur"`, `"parque san isidro"`, `"zonas cercanas"`.

### 3.4 Regex sugeridas (para el título crudo, antes de `normalize_title`; para el Equipo 2)

```
# 1. Sufijo de ubicación tras separador (cubre 365+76+32+12 casos):
\s*[-–—|/,]\s*(?:remoto|h[ií]brido|presencial|teletrabajo)?\s*(?:en\s+)?(?:<CIUDAD>|<DEPTO>)(?:\s*[,/-]\s*(?:<DEPTO>|colombia))?\s*$
# 2. Paréntesis con ubicación/modalidad:
\((?:[^)]*\b(?:remoto|h[ií]brido|presencial|en)\b)?[^)]*\b(?:<CIUDAD>)\b[^)]*\)
# 3. "en / para laborar en / sede / ciudad de" + ciudad:
\b(?:para\s+laborar\s+en|sede|ciudad\s+de|en)\s+(?:la\s+)?(?:<CIUDAD>|<DEPTO>)\b
# 4. Zonas: \bzona\s+(?:franca|norte|sur|occidente|oriente|centro)\b
# 5. Códigos de oferta: ^\s*#?\d{4,}\s*|\s*\d{6,}(?:-\d+)?\s*$
# 6. Sigla de estado de EE. UU. SOLO como sufijo: ,\s*(?:[A-Z]{2})\s*$   (no como token suelto: ver 'ia')
```
`<CIUDAD>` = DIVIPOLA (municipios) + localidades de Bogotá; `<DEPTO>` = `geografia.DEPARTAMENTOS`. Ojo con ambiguas: Armenia, Granada, Fundación, Meta, Sucre, Cesar, Honda, Bello, Caldas, Soledad, Florida (pedir separador/posición final).

### 3.5 Efecto colateral de `_UBICACIONES` con siglas de 2 letras (bug reproducido)

`_UBICACIONES` contiene `ia, al, in, or, on, ma, ok, to, us, mi, de…` (estados/provincias). `canonizar_cargo` los borra **como token suelto en cualquier posición**:

| Título | `traducir_cargo(normalize_title())` |
|---|---|
| Especialista en IA | **Especialista** |
| Ingeniero IA | **Ingeniero** |
| Analista de IA y Datos | **Analista y datos** |
| Lider de IA | **Lider** |
| Ingeniero Sr de IA - Cto Fijo 1 ano | Ingeniero cto fijo ano |

104 títulos colombianos con "IA" (programa Ing. en Inteligencia Artificial sobre todo), 178 con "al" (`Servicio al Cliente` → sobrevive gracias al diccionario), 7 con "M&A". **Propuesta**: aplicar las siglas de 2 letras solo cuando van al final precedidas de coma/guion (regla 6 arriba), o sacar de `_UBICACIONES` las que colisionan con español: `ia`, `al`, `in`, `on`, `or`, `to`, `us`, `ma`, `ok`, `de`.

---

## 4. Combinaciones con pocos/ningún dato en Tendencias

### 4.1 Clasificación de causa raíz (819 combinaciones con 0-2 términos, de 900)

| Mercado | Dimensión | a) cobertura de fuente | b) filtro agresivo | c) umbrales/periodos | d) faltan vacantes reales |
|---|---|---|---|---|---|
| Colombia | cargo | 17 | 19 | 55 | 55 |
| Colombia | sector | **150** | 0 | 0 | 0 |
| Latinoamérica | cargo | 11 | 32 | 53 | 46 |
| Latinoamérica | sector | 37 | 29 | 50 | 29 |
| Todas | cargo | 0 | **80** | 26 | 4 |
| Todas | sector | 0 | **107** | 15 | 4 |

Criterio (sobre el histórico enriquecido, replicando `agregar_observaciones`/`terminos_validos_combinados`): a) 0 filas crudas del programa en ese mercado, o la fuente no trae `category` (sector); d) <15 crudas; b) sin `coincide_con_keyword` habría ≥3 términos válidos o tras el filtro quedan <15 filas; c) hay filas pero <3 meses con ≥`min_mes` vacantes por mercado, o ningún cargo llega a 15 apariciones en 3 meses. La réplica reproduce el nº de términos de la tabla precalculada en todas las filas de las tablas de abajo (`terminos_ok_replica` en `causas_raiz.csv`).

### 4.2 Eje Experiencia (Colombia y Todas)

| Mercado | Dimensión | Experiencia | `sin_datos` /30 | 0-2 términos /30 | Términos |
|---|---|---|---|---|---|
| Colombia | cargo | TODOS | 4 | 28 | 48 |
| Colombia | cargo | no_especificado | 5 | 28 | 41 |
| Colombia | cargo | senior | 25 | 30 | 0 |
| Colombia | cargo | junior / graduado | 30 / 30 | 30 / 30 | 0 |
| Todas | cargo | TODOS | 3 | 11 | 226 |
| Todas | cargo | no_especificado | 4 | 13 | 183 |
| Todas | cargo | senior | 19 | 26 | 55 |
| Todas | cargo | junior / graduado | 29 / 30 | 30 / 30 | 1 / 0 |
| Todas | sector | senior / junior / graduado | 18 / 28 / 30 | 27 / 30 / 30 | 31 / 2 / 0 |

Causa: el nivel se infiere del título y el 91% de Colombia (2.485/2.740) y el 75% de Todas queda en `no_especificado`; `junior` 95 y `graduado` 31 vacantes en toda Colombia → **d) faltan vacantes etiquetadas**: ningún programa alcanza 15 en 3 meses. En demanda: con `graduado` el total nacional es 31 y todas las celdas por programa quedan <15.

### 4.3 Eje CUOC (solo demanda)

Totales Colombia (programa TODOS): profesional 2.011, directivo 257, técnico 167, apoyo administrativo 83, servicios/ventas **18**, no clasificado 204. Celdas con <15 vacantes por CUOC en Colombia: servicios_ventas 148/150, apoyo_administrativo 146/150, técnico 142/150, directivo 138/150. Es la consecuencia documentada de ofrecer los grupos 1-5 sobre vacantes profesionales; no es bug.

### 4.4 Cargo × Programa (Experiencia=TODOS) — Colombia

| Programa | Términos | Crudas | Tras filtro | % desc. | Meses c/datos | Meses válidos | Cargo top (apar./meses) | Causa |
|---|---|---|---|---|---|---|---|---|
| Administración & Servicio | 1 | 335 | 103 | 69 | 3 | 3 | Analista de servicio al cliente (41/3) | c |
| Administración de Empresas | 0 | 377 | 160 | 58 | 3 | 2 | Analista administrativo (74/2) | c |
| Adm. Mercadeo y Logística Int. | 0 | 391 | 205 | 48 | 3 | 2 | Analista de mercadeo (68/2) | c |
| Adm. Negocios Internacionales | 1 | 320 | 121 | 62 | 4 | 3 | Analista de comercio exterior (38/3) | c |
| Ciencia de Datos | 2 | 238 | 127 | 47 | 5 | 3 | Científico de datos (62/3) | c |
| **Ciencias Políticas** | 0 | 29 | **0** | 100 | 0 | 0 | — | **b** |
| Comportamiento Organizacional | 1 | 210 | 90 | 57 | 3 | 3 | Analista de recursos humanos (23/3) | c |
| Com. Audiovisual y Multimedios | 2 | 167 | 123 | 26 | 5 | 3 | Editor de video (65/3) | c |
| Comunicación Corporativa | 1 | 144 | 44 | 69 | 3 | 3 | Relaciones públicas (28/3) | c |
| Com. Social y Periodismo | 0 | 170 | 80 | 53 | 3 | 2 | Community Manager (53/2) | c |
| Derecho | 0 | 193 | 121 | 37 | 5 | 3 | Asesor jurídico (15/2) | c |
| Economía y Finanzas Int. | 0 | 244 | 85 | 65 | 5 | 2 | Analista financiero (5/2) | c |
| Economía y Finanzas Int. Virtual | 0 | 255 | 66 | 74 | 3 | 2 | Analista financiero (9/2) | c |
| Enfermería | 2 | 264 | 214 | 19 | 9 | 3 | Auxiliar de enfermería (70/3) | c |
| Filosofía | 0 | 165 | 78 | 53 | 2 | 2 | Docente de filosofía (10/1) | c |
| Fisioterapia | 0 | 109 | 38 | 65 | 4 | 2 | Fisioterapeuta (13/2) | c |
| Gastronomía | 0 | 164 | 89 | 46 | 4 | 2 | Administrador(a) de restaurante (36/2) | c |
| Ingeniería Industrial | 2 | 225 | 136 | 40 | 3 | 3 | Ingeniero de procesos (49/3) | c |
| Ingeniería Informática | 0 | 252 | 115 | 54 | 3 | 2 | Desarrollador full stack (14/2) | c |
| Ingeniería Mecánica | 0 | 193 | 124 | 36 | 4 | 2 | Ingeniero mecánico (60/2) | c |
| Ingeniería Química | 0 | 152 | 53 | 65 | 2 | 2 | Ingeniero químico (49/2) | c |
| **Ingeniería de Bioproducción** | 0 | 40 | **0** | 100 | 0 | 0 | — | **b** |
| Ing. de Diseño e Innovación | 0 | 224 | 110 | 51 | 3 | 2 | Diseñador de producto (17/2) | c |
| Ing. en Inteligencia Artificial | 0 | 208 | 50 | 76 | 2 | 2 | Ingeniero de machine learning (15/2) | c |
| Lic. Educación Infantil | 2 | 189 | 74 | 61 | 3 | 3 | Docente de preescolar (33/3) | c |
| Medicina | 1 | 83 | 70 | 16 | 5 | 3 | Médico general (48/3) | c |
| Psicología | 2 | 247 | 92 | 63 | 3 | 3 | Analista de selección (52/3) | c |
| **Relaciones Internacionales** | 0 | 85 | 13 | 85 | 2 | 2 | Practicante de RR. II. (4/2) | **b** |

Evidencia de (c): meses con datos por país tras filtro — `co` (Google Jobs): **2026-06: 57, 2026-07: 951, 2026-08: 1.311, 2026-09: 0**; `co_li` (LinkedIn): abr 0, may 6, jun 25, jul 134, ago 234, sep 12. Con `MIN_PERIODOS=3` y `MIN_VACANTES_MES_PROGRAMA=3` **por mercado**, un programa necesita ≥3 filas en junio en Google Jobs (mes de solo 57 vacantes en total) o en LinkedIn (25): la mayoría cae a 2 meses válidos. Cargos con volumen sobrado se pierden por esto: "Analista administrativo" 74 apariciones en 2 meses, "Analista de mercadeo" 68/2, "Ingeniero mecánico" 60/2, "Community Manager" 53/2, "Ingeniero químico" 49/2. **No es bug; es falta de historia** (y en septiembre Google Jobs no recolectó nada: la ventana no crecerá sola).

### 4.5 Cargo × Programa (Experiencia=TODOS) — Todas (solo las 11 con ≤2 términos)

| Programa | Términos | Crudas | Tras filtro | % desc. | Meses válidos | Cargo top (apar./meses) | Sin filtro habría | Causa |
|---|---|---|---|---|---|---|---|---|
| Administración & Servicio | 2 | 5.392 | 252 | 95 | 11 | Analista de servicio al cliente (41/3) | 39 términos | b |
| Adm. Negocios Internacionales | 2 | 2.658 | 222 | 92 | 7 | Analista de comercio exterior (38/3) | 14 | b |
| Ciencias Políticas | 0 | 995 | 24 | 98 | 3 | Analista político (3/1) | 2 | c/d |
| Comportamiento Organizacional | 1 | 4.459 | 135 | 97 | 3 | Analista de recursos humanos (23/3) | 28 | b |
| Comunicación Corporativa | 1 | 1.592 | 95 | 94 | 7 | Relaciones públicas (28/3) | 11 | b |
| Economía y Finanzas Int. Virtual | 1 | 2.188 | 187 | 92 | 9 | Analista financiero digital (remoto) (44/1) | 20 | b |
| Filosofía | 1 | 903 | 185 | 80 | 12 | Analista de políticas públicas (74/10) | 2 | c |
| Fisioterapia | 2 | 1.528 | 931 | 39 | 27 | Fisioterapeuta (718/27) | 3 | concentración en 1 cargo (no es bug) |
| Ingeniería Química | 2 | 1.679 | 136 | 92 | 11 | Ingeniero químico (59/8) | 13 | b |
| Ingeniería de Bioproducción | 0 | 388 | 15 | 96 | 2 | Ing. de desarrollo de bioprocesos (2/1) | 1 | c/d |
| Relaciones Internacionales | 0 | 1.856 | 36 | 98 | 3 | Oficial de seguridad (8/1) | 8 | b |

Matiz importante sobre (b) en Adzuna: el filtro **descarta ruido real** (`organizational development` trae "Line Cook", etc.), así que "sin filtro habría 28 términos" no significa que esos términos sean del programa. La causa de fondo es que **la keyword no describe un cargo** (`business administration`, `talent management`, `international business`, `public policy`, `diplomat`, `ethics officer`) y por eso ningún título la contiene. Es un problema de **keywords**, no del filtro.

Keywords Adzuna con mayor descarte (Todas): `organizational development` 1.903→8 (99,6%), `biotechnology engineer` 249→1, `talent management` 2.324→15, `business administration` 1.967→14, `ethics officer` 443→4, `diplomat` 897→8, `international business` 1.568→17, `public policy` 936→12.

### 4.6 Cuantificación del filtro `coincide_con_keyword` por programa (Colombia)

Sobre Colombia descarta el 53,7% (5.918 → 2.740). Por programa (crudas → tras filtro, % descartado): Ciencias Políticas 29→0 (100%), Ing. Bioproducción 40→0 (100%), Relaciones Internacionales 85→13 (85%), Ing. IA 208→50 (76%), EyF Virtual 255→66 (74%), Com. Corporativa 144→44 (69%), Adm. & Servicio 335→103 (69%), EyF 244→85 (65%), Fisioterapia 109→38 (65%), Ing. Química 152→53 (65%), Psicología 247→92 (63%), Adm. Negocios Int. 320→121 (62%), Lic. Educación Infantil 189→74 (61%), Adm. Empresas 377→160 (58%), Comportamiento Org. 210→90 (57%), Ing. Informática 252→115 (54%), Com. Social 170→80 (53%), Filosofía 165→78 (53%), Ing. Diseño 224→110 (51%), Adm. Mercadeo 391→205 (48%), Ciencia de Datos 238→127 (47%), Gastronomía 164→89 (46%), Ing. Industrial 225→136 (40%), Derecho 193→121 (37%), Ing. Mecánica 193→124 (36%), Ing. Civil 245→159 (35%), Com. Audiovisual 167→123 (26%), Enfermería 264→214 (19%), Medicina 83→70 (16%). Tabla completa por keyword: `filtro_keyword_programa.csv`.

Keywords colombianas donde el filtro sí pierde vacantes legítimas (exige TODAS las palabras significativas, sin lematizar):

| Keyword (programa) | Crudas → tras | Títulos descartados (ejemplos reales) |
|---|---|---|
| `ingeniero de procesos químicos` (Ing. Química) | 52 → **0** | "Ingeniero Químico de Procesos", "Ingeniero Químico en produccion - Medellin", "Líder de Turno — Ingeniero Químico" (plural "químicos" ≠ "químico") |
| `ingeniero en biotecnología` (Bioproducción) | 21 → **0** | "Bacterióloga/o Coordinador de procesamiento", "Analista de Microbiología", "Analista de Laboratorio" |
| `analista político` (C. Políticas) | 21 → **0** | "Oficial de Monitoreo y Evaluación", "Consultor Acceso a Mercados" (ruido real) |
| `productor audiovisual` (Com. Audiovisual) | 33 → 1 | "Producer", "Event Producer", "Video Editor" |
| `coordinador de importaciones y exportaciones` (Neg. Int.) | 86 → 7 | "Coordinador de Importaciones", "Supervisor de importaciones y exportaciones", "Coordinador(a) Plan Vallejo" |
| `administrador de empresas` (Adm. Empresas) | 165 → 18 | "Administrador de tienda", "Administrador punto de venta", "Administrador Regional" |
| `analista fintech` (EyF Virtual) | 110 → 13 | "Business Analyst", "Bilingual Customer Analytics Analyst (Fintech, Bogotá)" |
| `jefe de servicio al cliente` (Adm. & Servicio) | 139 → 17 | "Jefe de servicios", "Customer Service Team Lead", "Líder de Servicio - Sector seguros" |
| `comunicaciones corporativas` (Com. Corporativa) | 71 → 10 | "Gestor de Comunicaciones Institucionales (Comunicación Corporativa)" (singular), "Coordinador de Relaciones Públicas" |
| `educador infantil` (Educación Infantil) | 53 → 9 | "Licenciada Educadora Especial", "Aprendiz Sena o Practicante en Auxiliar de Primera Infancia" |
| `docente de filosofía` (Filosofía) | 82 → 16 | "Profesor Filosofía Bogotá", "Profesor/a de Sociales y Filosofía Bilingüe" (profesor ≠ docente) |
| `psicólogo organizacional` (Psicología) | 112 → 22 | títulos con "Psicóloga" (femenino) o "Analista de selección" |

Patrón: keywords de 2-3 palabras significativas + comparación por subcadena exacta → pierde plural/singular (`químicos`), género (`psicóloga`), sinónimos (`profesor`/`docente`, `supervisor`/`coordinador`) y orden. **Propuesta (cambio de lógica, Tech Lead)**: lematización mínima (quitar `s`/`es`, `a`/`o` final) y aceptar ≥ N-1 palabras cuando la keyword tiene ≥3; o mantener el filtro pero **cambiar keywords** a la forma que usan los títulos: `ingeniero químico`, `bacteriólogo`/`microbiólogo`, `profesor de filosofía`, `psicólogo` (ya existe), `coordinador de importaciones`, `comunicación corporativa`.

### 4.7 Sector

- **Colombia**: 150/150 `sin_datos` — `vacantes_historicas.category` es nulo en el 100% de `co` (3.987), `co_li` (1.931), `mx_li`, `ar_li`, `cl_li`, `pe_li`. La gráfica "Sectores más demandados" de Tendencias queda vacía con "Colombia" y en Latinoamérica el #1 es "Sin especificar" (412 de 4.128). **a) cobertura de fuente** — proponer que la UI oculte la gráfica/dimensión cuando ninguna fuente seleccionada tiene `sector` (la info ya está en `opciones_disponibles().fuentes[].dimensiones`).
- Latinoamérica sector por programa: 4 (a), 6 (b), 17 (c); Todas: 18 (b) — mismo diagnóstico que cargos.

---

## 5. Por programa: Competencias / Análisis salarial / Perfil ocupacional

29/29 responden sin error en las tres funciones. Estado (OK / ⚠️ advertencia / ❌ error):

| Programa | Competencias | Salarial | Perfil | Detalle |
|---|---|---|---|---|
| Administración & Servicio | OK | OK | ⚠️ | ciudad "Colombia" |
| Administración de Empresas | OK | OK | ⚠️ | ciudad "Colombia" |
| Adm. Mercadeo y Logística Int. | OK | OK | ⚠️ | ciudad "Colombia" |
| Adm. Negocios Internacionales | OK | OK | ⚠️ | ciudad "Colombia" |
| Ciencia de Datos | ❌ | OK | ⚠️ | **competencias vacías en los 4 mercados** (caché disco obsoleto; API viva devuelve 8); ciudad "Colombia" |
| Ciencias Políticas | ⚠️ | OK | ⚠️ | tecnología en inglés "Library of Congress E-resources Online Catalog"; ciudad "Colombia" |
| Comportamiento Organizacional | ⚠️ | OK | ⚠️ | "Lawson Human Resource Management"; ciudad "Colombia" |
| Com. Audiovisual y Multimedios | ⚠️ | OK | ⚠️ | "Web content management system CMS"; ciudades "Colombia", "Antioquia" |
| Comunicación Corporativa | ⚠️ | OK | ⚠️ | descripciones EN (HubSpot, Marketo); sector #1 "Otros / general" (99); tendencia creciente **+229%**; ciudades "Colombia", "Valle del Cauca" |
| Com. Social y Periodismo | ⚠️ | OK | ⚠️ | "Web content management system CMS"; ciudad "Colombia" |
| Derecho | ⚠️ | OK | ⚠️ | "Orion Law Management Systems Orion"; **ciudades Lima 12, Santiago 11**; ciudad "Colombia" |
| Economía y Finanzas Int. | ❌ | OK | ⚠️ | **competencias vacías (API viva también vacía: 13-2051.00)**; "Oracle Hyperion Financial Management"; ciudades "Colombia", "Risaralda" |
| Economía y Finanzas Int. Virtual | ❌ | OK | ⚠️ | idem; ciudades "Colombia", "Valle del Cauca", "Buenos Aires Province" |
| Enfermería | ⚠️ | OK | ⚠️ | "Human resource management software HRMS"; seniority confianza limitada (12 etiquetadas); ciudad "Colombia" |
| Filosofía | ⚠️ | OK | ⚠️ | "Philosopher's Information Center The Philosopher's Index", "Learning management system LMS"; tendencia **+233%**; ciudades "Colombia", "Antioquia" |
| Fisioterapia | OK | OK | ⚠️ | seniority limitada (24); ciudad "Colombia" |
| Gastronomía | OK | ⚠️ | ⚠️ | escalera educativa no monótona [1,70M; 1,56M; 2,0M; 2,0M; 2,0M; 2,5M; 3,6M]; ciudades "Colombia", "Santiago" 7 |
| Ingeniería Civil | ⚠️ | OK | ⚠️ | "Geographic information system GIS"; descripciones EN (ArcGIS, ESRI); ciudades "Colombia", "Santiago" 8, "Lima" 6 |
| Ingeniería Industrial | ⚠️ | OK | ⚠️ | "Supervisory control and data acquisition SCADA"; descripciones EN (HMI, Allen Bradley); ciudad "Colombia" |
| Ingeniería Informática | OK | OK | ⚠️ | ciudad "Colombia" |
| Ingeniería Mecánica | ⚠️ | OK | ⚠️ | descripciones EN (ArcGIS, HMI, CNC); ciudades "Colombia", "Santiago" 8, "Marmato" |
| Ingeniería Química | ⚠️ | OK | ⚠️ | SCADA; descripciones EN (GE Fanuc); ciudad "Colombia" |
| Ingeniería de Bioproducción | OK | OK | ⚠️ | ciudad "Colombia" |
| Ing. de Diseño e Innovación | OK | OK | ⚠️ | ciudad "Colombia" |
| Ing. en Inteligencia Artificial | OK | OK | ⚠️ | tendencia creciente **+248,6%**; ciudades "Colombia", "Sevilla" 4 |
| Lic. Educación Infantil | ⚠️ | ⚠️ | ⚠️ | descripciones EN (Bloomz, ClassDojo, Edmodo, Tadpoles); escalera educativa no monótona [1,75M; 3,2M; 5,0M; 4,6M; 7,48M]; ciudad "Colombia" |
| Medicina | ⚠️ | OK | ⚠️ | descripción EN ("Billing"); seniority limitada (27); ciudades "Colombia", "Santiago" 3 |
| Psicología | ⚠️ | OK | ⚠️ | "Noldus Information Technology The Observer XT"; seniority limitada (27); ciudad "Colombia" |
| Relaciones Internacionales | ⚠️ | OK | ⚠️ | "Library of Congress E-resources Online Catalog"; ciudad "Colombia" |

Detalle:
- **Competencias**: nombres de tecnologías en inglés (son nombres de herramientas O*NET sin entrada en `TECNOLOGIAS`/`_DESCRIPCIONES_TECNOLOGIAS`): propuesta de entradas: `"Web content management system CMS": "Gestores de contenido web (CMS)"`, `"Supervisory control and data acquisition SCADA": "SCADA (supervisión y adquisición de datos)"`, `"Geographic information system GIS": "Sistemas de información geográfica (SIG)"`, `"Human resource management software HRMS": "Software de gestión de talento humano (HRMS)"`, `"Learning management system LMS": "Plataformas de aprendizaje (LMS)"`, `"Library of Congress E-resources Online Catalog": "Catálogos bibliográficos en línea"`, `"Lawson Human Resource Management": "Lawson HRM"`, `"Orion Law Management Systems Orion": "Orion (gestión jurídica)"`, `"Oracle Hyperion Financial Management": "Oracle Hyperion"`, `"Noldus Information Technology The Observer XT": "The Observer XT (Noldus)"`, `"Philosopher's Information Center The Philosopher's Index": "The Philosopher's Index"`, `"Human machine interface HMI": "Interfaces hombre-máquina (HMI)"`, `"Computer numerical control CNC": "Control numérico (CNC)"`; descripciones en español para HubSpot, Marketo, ArcGIS, ESRI ArcInfo/ArcView, Allen Bradley PanelView, GE Fanuc Proficy, Bloomz, ClassDojo, Edmodo, Tadpoles, Billing. El ranking por programa no cambia de conjunto de skills entre mercados (correcto), pero sí de orden (el índice usa la demanda de mercado: diseño documentado).
- **Salarial**: 29/29 resuelven el programa; medianas entre $2,0M y $4,0M COP (plausibles); `p10 ≤ mediana ≤ p90` en todos; rango SPE resuelto en todos. Por la granularidad a 2 dígitos **7 programas muestran exactamente el mismo análisis** ($3.000.000, CNO 24), 8 el mismo ($3.500.000, CNO 26) y 6 el mismo ($3.500.000, CNO 21): no es bug, pero el usuario ve "todos iguales" (sugerir mostrar el nombre del subgrupo CNO con más prominencia). Escalera educativa no monótona en Gastronomía (CNO 14) y Educación Infantil (CNO 23): dato GEIH, revisar si el texto "cuánto sube con estudios" asume monotonía.
- **Perfil**: (i) bug de ciudades extranjeras (LinkedIn `mx/pe/cl/ar` = 401 filas: Santiago 52, Lima 41, Las Condes 16, Buenos Aires 14, Mexico City 13…) por no filtrar `pais=='co'` en `_ciudades_colombia`; (ii) "Colombia" como ciudad en 29/29 (Google Jobs `city='Colombia'` en 393 filas; `geografia.py` ya lo ignora con `_IGNORAR`, `perfil_service.py` no); (iii) departamentos como ciudad (`city` = "Valle del Cauca" 29, "Cundinamarca" 24, "Antioquia" 23, "Santander" 10…); (iv) seniority con confianza limitada en Enfermería/Fisioterapia/Medicina/Psicología (12-27 títulos con nivel) — se comunica, OK; (v) tendencias "creciente" con variación +229% / +233% / +248,6% (Com. Corporativa, Filosofía, Ing. IA) sobre `us`: bajo el tope de 300 pero sospechosas (base de 2024-07..09 minúscula para esos programas) — revisar `_VARIACION_MAX_FIABLE`; (vi) `ocupacion_ref` de O*NET siempre en inglés ("Customer Service Representatives"…): es la referencia SOC; si se pinta, traducir; (vii) sector #1 "Otros / general" en Com. Corporativa: `agrupar_sector` no mapea la categoría de Adzuna "PR, Advertising & Marketing Jobs" → "Comunicación, publicidad y marketing" a un grupo (cae a OTROS) — verificar `GRUPOS_SECTOR`.

---

## 6. Otras anomalías

1. **"Ingeniero" genérico absorbe a los ingenieros de software** (hallazgo #1): `normalize_title` aplica `(software\s+)?engine(er|eering)` → `engineer` y `(software\s+)?develop(er|ment|ing)` → `developer`. Resultado tras filtro: de 1.594 vacantes con "software" en el título, 891 se etiquetan "Ingeniero" y 99 "Desarrollador"; solo 12 llegan a "Ingeniero de software". El top-1 de "Todas" (942) es 95% software (662 de Ing. Informática, 256 de Ing. IA). Propuesta: quitar el grupo opcional `(software\s+)?` y añadir `"software engineer": "Ingeniero de software"`, `"software developer": "Desarrollador de software"` a CARGOS (más `"ingeniero software"`, `"desarrollador software"` para las variantes españolas ya mutiladas).
2. **Duplicados de cargo por preposición/tilde/(a)** (12 grupos): Analista de inversiones | Analista inversiones (93 vac.), Especialista en marketing digital | Especialista marketing digital (31), Enfermero | Enfermero(a) (24), Ingeniero de software | Ingeniero software (19), Coordinador de marketing digital | Coordinador marketing digital (12), Analista de riesgos | Analista riesgos (7), Docente sociales y filosofia | …filosofía (5), Coordinador clínico | Coordinador(a) clínico(a) (4). Causa: el nivel "respaldo" muestra el título ya sin preposiciones (las quita `normalize_title`). `cargos_duplicados.csv`.
3. **Empresas**: 163 grupos con variantes (EY 35 | ey 10; Adecco Colombia 22 | Adecco Colombia S.A. 12 | Adecco 7; Manpower Group Colombia 35 | MANPOWER 5; Servicio de Empleo Comfama 35 | Servicio De Empleo Comfama 2; SUTTER HEALTH 14 | Sutter Health 11; Accenture 13 | accenture 7 | ACCENTURE 3; Michael Page Colombia 18 | Michael Page 5). Propuesta: agrupar por clave `casefold` + sin sufijos `S.A.S/SAS/S.A./Ltda/Inc/Group` y mostrar la grafía más frecuente (como ya hace `_ciudades_colombia`). `empresas_duplicadas.csv`.
4. **Placeholders que pasan `_EMPRESAS_CONFIDENCIALES`** (24): "Confidential Careers" 11, "Confidential Jobs" 4, "Confidential - Staffing and Recruiting" 2, "Our Client"/"Our client" 2, "Confidential Company" 1, "Importante empresa del sector {Calzado, salud, financiero, automotriz, …}" 8, "EMPRESA DEL SECTOR ALIMENTICIO". Propuesta: `re.match(r"^(confidential|confidencial|our client|importante empresa|empresa del sector|reconocida empresa)", plegado)`. `empresas_placeholder.csv`.
5. **"Sin especificar" como sector** ocupa el #4 en Todas (953) y el #1 en Latinoamérica (412): sale de `traducir_sector(None)`→`agrupar_sector` para filas sin `category`… en realidad `agrupar_sector(None)` devuelve `None` y no cuenta; las 953 provienen de `category='Unknown'` de Adzuna. Sugerir excluirlo del top o rotularlo como cobertura.
6. **Recolección de Google Jobs detenida**: `co` tiene 0 filas con `created_at` en 2026-09 (LinkedIn co_li: 12). Las tendencias de Colombia no ganarán el tercer mes si no se recolecta mensualmente. La tabla `tendencias_observaciones` se recalculó el 2026-09-11; el histórico llega al 2026-09-07 (coherentes).
7. **`_cache_onet.json` obsoleto** (12-ago): Ciencia de Datos con 0 competencias (la API viva devuelve 8: Pensamiento crítico, Comprensión de lectura, Resolución de problemas complejos, Aprendizaje activo…). EyF / EyF Virtual: 0 competencias también en la API viva para `13-2051.00` → revisar el código SOC (p. ej. `13-2099.01 Financial Quantitative Analysts` o `13-2052.00 Personal Financial Advisors` tienen *skills*).
8. Nombres de programa: los 29 se resuelven en `PROGRAMAS_KEYWORDS`, `PROGRAMAS_KEYWORDS_CO`, `PROGRAMAS_ONET`, `PROGRAMA_CNO`, `PROGRAMA_CNO_SENA` (29/29 con CNO SENA: 5-12 habilidades / 12-33 conocimientos). "Administración & Servicio" (con `&`) llega bien por query string.
9. Geografía (`resumen_departamentos`): cobertura 90,9% (2.491/2.740 con departamento), 26 departamentos, "Sin ciudad especificada" 369 en el ranking nacional de ciudades (#2) — coherente con `city='Colombia'`; top cargos = los mismos que demanda (sin inglés).

---

## 7. Recomendaciones priorizadas (impacto × esfuerzo)

### A. Fix trivial de datos (PROPUESTA concreta, no aplicada)
1. **`Adzuna/adzuna_service.normalize_title`**: quitar `(software\s+)?` en las dos regex y añadir a `CARGOS` `"software engineer": "Ingeniero de software"`, `"software developer": "Desarrollador de software"`, `"ingeniero software": "Ingeniero de software"`, `"desarrollador software": "Desarrollador de software"`, `"software development engineer": "Ingeniero de desarrollo de software"`. Impacto: corrige el top-1 de la vista principal y el perfil de Ing. Informática/Ing. IA. *Requiere recalcular Tendencias tras el cambio.*
2. **`traducciones._UBICACIONES`**: añadir los 32 municipios/zonas de §3.3 y los bigramas `zona franca|norte|sur`; **quitar (o restringir a sufijo) `ia`, `al`, `in`, `on`, `or`, `to`, `us`, `ma`, `ok`, `de`**.
3. **`traducciones.CARGOS/_MODIFICADORES/_NUCLEOS`**: entradas de §2.4 (`supply chain`, `area manager operations`, `digital marketing`, `graduate engineer structural`, `preschool …`, `intern/internship/apprenticeship`, `vice president`).
4. **`CARGOS` para los respaldos españoles más frecuentes** (evita barras partidas): `"analista inversiones": "Analista de inversiones"`, `"analista riesgos": "Analista de riesgos"`, `"analista riesgos financieros": "Analista de riesgos financieros"`, `"especialista marketing digital"`, `"coordinador marketing digital"`, `"analista marketing digital"`, `"profesional marketing digital"`, `"responsable marketing digital"`, `"ingeniero inteligencia artificial": "Ingeniero de inteligencia artificial"`, `"analista financiero y planeacion"`, `"profesional negocios internacionales"`, `"jefe seguridad cadena suministro"`, `"investigador campo"`, `"docente sociales y filosofia": "Docente de filosofía"`, `"enfermero": "Enfermero(a)"`.
5. **`demanda_actual._EMPRESAS_CONFIDENCIALES`** → regex de prefijo (§6.4).
6. **`ONet/_DESCRIPCIONES_TECNOLOGIAS` / `TECNOLOGIAS`**: entradas de §5.
7. **Borrar `Tendencias/_cache_onet.json`** para que Ciencia de Datos recupere sus competencias (y revisar SOC de EyF).
8. **`config.PROGRAMAS_KEYWORDS_CO`**: `ingeniero de procesos químicos` → `ingeniero químico de procesos`/`ingeniero químico`; `ingeniero en biotecnología` → `biotecnólogo`, `microbiólogo`; `docente de filosofía` → `profesor de filosofía`; `coordinador de importaciones y exportaciones` → `coordinador de importaciones`, `comercio exterior`; `comunicaciones corporativas` → `comunicación corporativa`. **`PROGRAMAS_KEYWORDS` (Adzuna)**: sustituir `organizational development`, `talent management`, `business administration`, `international business`, `public policy`, `diplomat`, `ethics officer` por cargos (`hr specialist`, `management analyst`, `policy analyst`…). Impacto directo en los 3 programas con 0 en todos los mercados.

### B. Cambio de lógica (Tech Lead / Equipo 2)
1. **`Perfil/perfil_service._ciudades_colombia`**: filtrar `oferta.get("pais") == "co"` en LinkedIn; ignorar `city in {"Colombia", ""}`; tratar departamentos como "sin ciudad" (reutilizar `geografia._ciudad_de`/`_IGNORAR`).
2. **Respaldo de `traducir_cargo`**: canonizar desde el título crudo (o re-insertar `de`) para no mostrar "Analista inversiones"; alternativamente aplicar `canonizar_cargo` antes de que `normalize_title` quite preposiciones.
3. **`coincide_con_keyword`**: lematización mínima (plural/género) y, para keywords de ≥3 palabras, aceptar N-1; medir con `filtro_keyword_programa.csv` (antes/después).
4. **UI Tendencias**: cuando ninguna fuente seleccionada tenga la dimensión `sector` (`opciones.fuentes[].dimensiones`), ocultar la gráfica/selector "Sector" con un aviso de cobertura (hoy queda vacío en Colombia y "Sin especificar" domina Latinoamérica).
5. **Empresas**: normalizar clave de agrupación (caso + sufijos societarios).
6. **`perfil_tendencia`**: revisar `_VARIACION_MAX_FIABLE`/base mínima para evitar +229…+249% con bases de 3 meses casi vacíos.
7. **`GRUPOS_SECTOR`**: verificar mapeo de "Comunicación, publicidad y marketing" (Com. Corporativa cae a "Otros / general").
8. **Orden núcleo-primero** en `_componer_cargo` (`graduate engineer structural`).

### C. No es bug, es falta de datos (comunicar, no "arreglar")
1. Tendencias de Colombia por programa: solo 3 meses de Google Jobs (jun-ago 2026) y septiembre sin recolección → la mayoría de programas queda en 2 meses válidos. Solución real: recolectar mensualmente y esperar; **no bajar `MIN_PERIODOS`**.
2. Experiencia `junior`/`graduado` y CUOC `servicios_ventas`/`apoyo_administrativo`: 31-95 vacantes en toda Colombia → ninguna celda por programa alcanza los mínimos.
3. Fisioterapia/Enfermería/Medicina en "Todas": 1-2 términos porque el programa es un solo cargo dominante (Fisioterapeuta 718/931), no por falta de datos.
4. Ciencias Políticas, Ing. de Bioproducción y Relaciones Internacionales: 29/40/85 vacantes crudas en Colombia y 0/0/13 tras filtro; con las keywords actuales no hay señal en ningún mercado.
5. Salarios idénticos entre programas del mismo subgrupo CNO: granularidad honesta de la GEIH.

---

## 8. Metodología y reproducibilidad

Entorno: `C:\Users\esteb\AppData\Local\Programs\Python\Python313\python.exe`, cwd/sys.path en `src/backend` (`config.py` carga `.env`); pandas 2.3.2. Sin escrituras: el único archivo que el backend habría escrito (`ONet/_cache_perfil_onet.json`, al consultar programas nuevos) se redirigió al scratchpad (`_cache_perfil_onet.qa.json`). Las llamadas externas fueron GET a Supabase (≈120 páginas de 1000, secuenciales con pausa de 0,25 s y un reintento) y GET a la API de O*NET (≈5 por programa, desde `construir_perfil_ocupacional`).

Scripts (en la carpeta `qa-datos\`):

| Script | Qué hace | Salidas |
|---|---|---|
| `lib_qa.py` | rutas, conjuntos de mercados, paginación de a 1000, parches EN MEMORIA de los lectores (`demanda_actual._cache`, `leer_observaciones`, `fetch_google_jobs_from_db`, `leer_ofertas_linkedin`, `_CACHE_JOBS`) y redirección del caché O*NET | — |
| `01_dump.py` | volcado de `vacantes_historicas` (73.977), `tendencias_observaciones` (18.027), `vacantes_google` (3.987), `vacantes_linkedin` (2.332), `vacantes` (14.548) | `dump_*.jsonl` |
| `02_enriquecer_y_demanda.py` | enriquece cada fila con las funciones del backend y calcula las 2.700 combinaciones de `demanda_actual`; valida 210 contra la función real | `enriquecido_historico.jsonl`, `matriz_demanda.csv` (22.736 filas: mercado, programa, seniority, cuoc, tipo, rank, label, count), `matriz_demanda_meta.csv`, `validacion_demanda.csv` |
| `02b_revalidar.py` | re-compara las 121 diferencias ignorando el orden de empates | log `02b.log` (121/121 equivalentes) |
| `03_matriz_tendencias.py` | 900 llamadas a `construir_tendencias` con observaciones en memoria | `matriz_tendencias_meta.csv`, `matriz_tendencias_terminos.csv` (950) |
| `04_por_programa.py` | Competencias × 4 conjuntos × 2 tipos, evolución, salarial y perfil por programa | `por_programa/*.json`, `por_programa_resumen.csv` |
| `05a_ingles_ubicaciones.py` | veredicto de idioma por etiqueta (vocabulario EN fuerte/débil vs ES, anglicismos aceptados), ubicaciones colombianas (DIVIPOLA parcial + zonas), duplicados | `ingles_cargos.csv`, `ingles_resumen.csv`, `ubicaciones_cargos.csv`, `ubicaciones_titulos_raw.csv`, `cargos_duplicados.csv`, `empresas_duplicadas.csv`, `empresas_placeholder.csv` |
| `05b_causas_raiz.py` | replica los umbrales del motor por combinación y clasifica a/b/c/d con contrafactual sin `coincide_con_keyword` | `causas_raiz.csv` (819), `filtro_keyword_programa.csv`, `filtro_programa.csv`, `meses_por_pais.csv` |
| `05c_anomalias_programa.py` | estado OK/⚠️/❌ y problemas por programa | `por_programa_estado.csv` |
| `05d_patrones.py` | siglas de 2 letras, vías de traducción (respaldo 37%), muestras de títulos descartados, bigramas EN, fuga de ciudades LinkedIn, `category` por país, seniority/CUOC | log en consola (`ingles_top60.csv`) |
| `06_tablas_md.py` | tablas Markdown | `tablas.md` |

Comandos: `cd qa-datos && python 01_dump.py && python 02_enriquecer_y_demanda.py && python 03_matriz_tendencias.py && python 04_por_programa.py && python 05a_ingles_ubicaciones.py && python 05b_causas_raiz.py && python 05c_anomalias_programa.py && python 05d_patrones.py && python 06_tablas_md.py` (≈12 min en total; el volcado ≈90 s).

Limitaciones: la heurística de idioma es léxica (puede haber falsos negativos en etiquetas de una sola palabra) y la lista de municipios cubre ≈200 municipios/localidades, no toda la DIVIPOLA; los conteos de "sobreviven" son por tanto un piso.
