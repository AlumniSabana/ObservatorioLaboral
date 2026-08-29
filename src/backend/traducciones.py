"""
traducciones.py — traducción EN→ES de valores de datos que llegan en inglés.

La UI del observatorio está en español, pero algunas fuentes entregan sus datos
en inglés y esos valores se pintaban crudos en las gráficas:

  - Adzuna (mercado EE.UU.): `category` (sector) y `contract_time` (modalidad),
    más los títulos de cargo (texto libre).
  - O*NET (normativo EE.UU.): nombres de tecnologías/herramientas.

Aquí viven los diccionarios y los helpers. La regla de oro es aplicar el helper
como transformación CANÓNICA: en el punto donde se PRODUCE el valor y también
donde se EMPAREJA (filtros, drill-down), para que el valor en español sea la
identidad en todo el flujo y no se rompa nada.

Todos los helpers hacen *fallback* al valor original si no está en el diccionario
(mejor mostrar el inglés que perder el dato).
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Sectores de Adzuna (category.label). Conjunto FINITO (~29 etiquetas fijas).
# Verificado sobre las 7.032 vacantes reales en BD.
# ─────────────────────────────────────────────────────────────────────────────
SECTORES: dict[str, str] = {
    "Healthcare & Nursing Jobs": "Salud y enfermería",
    "IT Jobs": "Tecnología (TI)",
    "Engineering Jobs": "Ingeniería",
    "Accounting & Finance Jobs": "Contabilidad y finanzas",
    "Sales Jobs": "Ventas",
    "Hospitality & Catering Jobs": "Hostelería y gastronomía",
    "Teaching Jobs": "Educación",
    "PR, Advertising & Marketing Jobs": "Comunicación, publicidad y marketing",
    "Logistics & Warehouse Jobs": "Logística y almacenamiento",
    "Admin Jobs": "Administración",
    "HR & Recruitment Jobs": "Recursos humanos y selección",
    "Legal Jobs": "Jurídico",
    "Creative & Design Jobs": "Diseño y creatividad",
    "Scientific & QA Jobs": "Ciencia y control de calidad",
    "Retail Jobs": "Comercio minorista",
    "Trade & Construction Jobs": "Oficios y construcción",
    "Customer Services Jobs": "Servicio al cliente",
    "Property Jobs": "Inmobiliario",
    "Manufacturing Jobs": "Manufactura",
    "Part time Jobs": "Empleos de medio tiempo",
    "Consultancy Jobs": "Consultoría",
    "Energy, Oil & Gas Jobs": "Energía, petróleo y gas",
    "Maintenance Jobs": "Mantenimiento",
    "Social work Jobs": "Trabajo social",
    "Travel Jobs": "Turismo y viajes",
    "Domestic help & Cleaning Jobs": "Servicio doméstico y limpieza",
    "Graduate Jobs": "Recién graduados",
    "Other/General Jobs": "Otros / general",
    "Charity & Voluntary Jobs": "ONG y voluntariado",
    # Centinela de las filas sin sector (Google Jobs no lo entrega, y algunas
    # vacantes de Adzuna llegan sin categoría).
    "Unknown": "Sin especificar",
}

# ─────────────────────────────────────────────────────────────────────────────
# Agrupación amplia de sectores para "Sectores con mayor actividad de
# contratación" (Tendencias > Demanda actual). Los ~29 sectores de Adzuna son
# demasiado finos para leerse de un vistazo, así que se colapsan en 6 campos
# amplios alineados con las áreas de los programas de la Sabana. Es una
# decisión EDITORIAL, no una taxonomía oficial (a diferencia de SECTORES, que
# sí es la traducción literal de Adzuna): un sector sin mejor encaje cae en
# "Otros / general" en vez de forzarlo, y "Sin especificar" se deja aparte
# porque es ausencia de dato, no un sector que no encaje.
# ─────────────────────────────────────────────────────────────────────────────
GRUPOS_SECTOR: dict[str, str] = {
    # Ciencias y de la ingeniería
    "Ingeniería": "Ciencias y de la ingeniería",
    "Ciencia y control de calidad": "Ciencias y de la ingeniería",
    "Energía, petróleo y gas": "Ciencias y de la ingeniería",
    "Manufactura": "Ciencias y de la ingeniería",
    "Mantenimiento": "Ciencias y de la ingeniería",
    "Oficios y construcción": "Ciencias y de la ingeniería",
    "Diseño y creatividad": "Ciencias y de la ingeniería",
    # Salud
    "Salud y enfermería": "Salud",
    # Educación
    "Educación": "Educación",
    # Negocios y Administración
    "Contabilidad y finanzas": "Negocios y Administración",
    "Ventas": "Negocios y Administración",
    "Administración": "Negocios y Administración",
    "Recursos humanos y selección": "Negocios y Administración",
    "Consultoría": "Negocios y Administración",
    "Logística y almacenamiento": "Negocios y Administración",
    "Inmobiliario": "Negocios y Administración",
    "Comercio minorista": "Negocios y Administración",
    "Servicio al cliente": "Negocios y Administración",
    "Comunicación, publicidad y marketing": "Negocios y Administración",
    "Hostelería y gastronomía": "Negocios y Administración",
    "Turismo y viajes": "Negocios y Administración",
    # Tecnología de la información y las comunicaciones
    "Tecnología (TI)": "Tecnología de la información y las comunicaciones",
    # Derecho y Ciencias Sociales y Culturales
    "Jurídico": "Derecho y Ciencias Sociales y Culturales",
    "Trabajo social": "Derecho y Ciencias Sociales y Culturales",
    "ONG y voluntariado": "Derecho y Ciencias Sociales y Culturales",
    # No son sectores reales: Adzuna los cuela como "categoría" pero describen
    # modalidad o nivel, no un rubro económico.
    "Empleos de medio tiempo": "Otros / general",
    "Recién graduados": "Otros / general",
}


def agrupar_sector(sector_es: str | None) -> str | None:
    """Colapsa un sector YA TRADUCIDO (salida de `traducir_sector`) en uno de
    los 6 campos amplios + "Otros / general".

    "Sin especificar" se deja tal cual: es ausencia de dato, no un sector que
    no encaje en ningún campo.
    """
    if not sector_es or sector_es == "Sin especificar":
        return sector_es
    return GRUPOS_SECTOR.get(sector_es, "Otros / general")


# ─────────────────────────────────────────────────────────────────────────────
# Modalidad de Adzuna (contract_time). Conjunto FINITO.
# La clave se compara en minúsculas para tolerar 'Unknown'/'unknown'.
# ─────────────────────────────────────────────────────────────────────────────
MODALIDAD: dict[str, str] = {
    "full_time": "Tiempo completo",
    "part_time": "Medio tiempo",
    "unknown": "No especificada",
}

# ─────────────────────────────────────────────────────────────────────────────
# Cargos de Adzuna: el título NORMALIZADO (salida de normalize_title, en
# minúsculas) → nombre de rol limpio en español. Es un conjunto ABIERTO (4.268
# títulos distintos, muy específicos de EE.UU.), así que se cura el TOP por
# frecuencia (lo que alimenta las gráficas de "cargos más demandados"). Además de
# traducir, se APROVECHA para limpiar el ruido (todas las variantes de
# "class a cdl delivery driver ..." → "Conductor de reparto"). El resto cae al
# título original en inglés (fallback), que es preferible a inventarlo.
# ─────────────────────────────────────────────────────────────────────────────
CARGOS: dict[str, str] = {
    "physical therapist pt rpt": "Fisioterapeuta",
    "mechanical engineer": "Ingeniero mecánico",
    "class a cdl delivery driver 12 000 sign on bonus": "Conductor de reparto",
    "financial analyst": "Analista financiero",
    "organizational effectiveness consultant o psychologist": "Consultor organizacional",
    "director engineering oci infrastructure planning capacity management": "Director de ingeniería",
    "financial analyst remote": "Analista financiero (remoto)",
    "developer manager": "Líder de desarrollo",
    "office manager": "Jefe administrativo",
    "medical surgical registered nurse med surg rn": "Enfermero(a) medicoquirúrgico",
    "seo link builder": "Especialista SEO",
    "engineer": "Ingeniero",
    "consultant": "Consultor",
    "electrical engineer": "Ingeniero eléctrico",
    "outside sales representative": "Representante de ventas",
    "merchandiser": "Mercaderista",
    "project engineer": "Ingeniero de proyectos",
    "class a delivery driver indianapolis": "Conductor de reparto",
    "director of restaurant operations": "Director de operaciones de restaurante",
    "sous chef": "Sous chef",
    "center clinical director": "Director clínico",
    "pharmacist sign on bonus relocation available": "Farmacéutico",
    "preschool teacher": "Docente de preescolar",
    "assistant restaurant manager": "Subgerente de restaurante",
    "pharmacist": "Farmacéutico",
    "process engineer": "Ingeniero de procesos",
    "retail store manager": "Gerente de tienda",
    "dental office assistant manager": "Administrador de consultorio dental",
    "primary care nurse rn registered nurse visiting nurse homecare": "Enfermero(a) de atención primaria",
    "travel pcu stepdown rn": "Enfermero(a) de cuidados intermedios",
    "pharmacist sign on bonus available": "Farmacéutico",
    "c net developer": "Desarrollador .NET",
    "class b delivery driver": "Conductor de reparto",
    "multi specialty account manager minneapolis mn": "Ejecutivo de cuenta",
    "class a delivery driver paducah": "Conductor de reparto",
    # Segunda tanda: roles reconocibles del top por frecuencia (se omiten los
    # títulos-basura muy locales que no representan un rol claro).
    "project manager": "Gerente de proyectos",
    "data analyst": "Analista de datos",
    "data scientist": "Científico de datos",
    "content writer": "Redactor de contenidos",
    "instructional designer": "Diseñador instruccional",
    "applied researcher": "Investigador aplicado",
    "director alternative investments": "Director de inversiones alternativas",
    "restaurant manager team": "Gerente de restaurante",
    "burger king restaurant general manager": "Gerente general de restaurante",
    "registered nurse rn hiring now": "Enfermero(a) registrado(a)",
    "class a cdl delivery driver": "Conductor de reparto",
    "early childhood teacher": "Docente de primera infancia",
    "real estate agent leads provided": "Agente inmobiliario",
    "primary care physician": "Médico de atención primaria",
    "primary care rn registered nurse visiting nurse homecare": "Enfermero(a) de atención primaria",
    "rn blood cancer oncology": "Enfermero(a) de oncología",
    "narrative strategist": "Estratega de contenidos",
    "employee benefits account executive": "Ejecutivo de cuenta de beneficios",
    "pharmacy intern grad": "Practicante de farmacia",
    "financial consultant highland park il": "Consultor financiero",
    "multi specialty account manager seattle wa": "Ejecutivo de cuenta",
    "director international business developer defense sector": "Director de desarrollo de negocios internacionales",
    "auto glass installation technician trainee": "Técnico instalador de vidrios (aprendiz)",
    "software engineer": "Ingeniero de software",
    "registered nurse": "Enfermero(a) registrado(a)",
    # Tercera tanda: los cargos que efectivamente afloran en la vista de
    # TENDENCIAS (pasan los umbrales de calidad). Es un conjunto acotado (~120),
    # así que aquí sí se logra cobertura casi completa de esa pantalla.
    "account executive": "Ejecutivo de cuenta",
    "account manager": "Gerente de cuenta",
    "accountant": "Contador",
    "ai engineer": "Ingeniero de IA",
    "analyst": "Analista",
    "asset protection investigator": "Investigador de prevención de pérdidas",
    "assistant general manager": "Subgerente general",
    "assistant manager": "Subgerente",
    "assistant professor": "Profesor asistente",
    "assistant store manager": "Subgerente de tienda",
    "attorney": "Abogado",
    "attorney lawyer": "Abogado",
    "automation engineer": "Ingeniero de automatización",
    "backend engineer": "Ingeniero backend",
    "bim manager": "Coordinador BIM",
    "bridge engineer": "Ingeniero de puentes",
    "business developer manager": "Gerente de desarrollo de negocios",
    "business developer representative": "Representante de desarrollo de negocios",
    "care assistant": "Auxiliar de cuidados",
    "cashier": "Cajero",
    "chef partie": "Chef de partida",
    "chemical process engineer": "Ingeniero de procesos químicos",
    "civil engineer": "Ingeniero civil",
    "civil engineer water": "Ingeniero civil (agua)",
    "cocinero a": "Cocinero",
    "controls engineer": "Ingeniero de control",
    "cook": "Cocinero",
    "crew member": "Miembro de equipo",
    "customer service representative": "Representante de servicio al cliente",
    "data engineer": "Ingeniero de datos",
    "design engineer": "Ingeniero de diseño",
    "developer": "Desarrollador",
    "diesel mechanic": "Mecánico diésel",
    "dishwasher": "Lavaplatos",
    "district manager": "Gerente de zona",
    "driver 0 hours": "Conductor",
    "engineer backend": "Ingeniero backend",
    "engineer full stack": "Ingeniero full stack",
    "engineering manager": "Gerente de ingeniería",
    "engineering technician": "Técnico en ingeniería",
    "estimator": "Presupuestador",
    "executive chef": "Chef ejecutivo",
    "executive sous chef": "Sous chef ejecutivo",
    "finance analyst": "Analista financiero",
    "fire protection engineer": "Ingeniero de protección contra incendios",
    "forward deployed engineer": "Ingeniero de campo",
    "full stack developer": "Desarrollador full stack",
    "full stack engineer": "Ingeniero full stack",
    "general manager": "Gerente general",
    "geotechnical engineer": "Ingeniero geotécnico",
    "head chef": "Chef principal",
    "infant teacher": "Docente de primera infancia",
    "insurance representative": "Representante de seguros",
    "investment analyst": "Analista de inversiones",
    "java developer": "Desarrollador Java",
    "kitchen designer": "Diseñador de cocinas",
    "licensed practical nurse lpn": "Enfermero(a) práctico(a) licenciado(a)",
    "line cook": "Cocinero de línea",
    "litigation attorney": "Abogado litigante",
    "machine learning engineer": "Ingeniero de machine learning",
    "maintenance engineer": "Ingeniero de mantenimiento",
    "maintenance technician": "Técnico de mantenimiento",
    "manager": "Gerente",
    "manufacturing engineer": "Ingeniero de manufactura",
    "marketing coordinator": "Coordinador de marketing",
    "marketing manager": "Gerente de marketing",
    "mechanical design engineer": "Ingeniero de diseño mecánico",
    "mechanical engineer water sector": "Ingeniero mecánico (sector agua)",
    "medical assistant": "Auxiliar médico",
    "mobile mechanic": "Mecánico móvil",
    "mobile vehicle technician": "Técnico automotriz móvil",
    "network engineer": "Ingeniero de redes",
    "nurse a registered nurse general duty nurse": "Enfermero(a) registrado(a)",
    "nurse a registered nurse registered psych nurse": "Enfermero(a) psiquiátrico(a)",
    "nurse practitioner": "Enfermero(a) especialista",
    "operations manager": "Gerente de operaciones",
    "outpatient registered nurse rn": "Enfermero(a) ambulatorio(a)",
    "patient care technician pct": "Técnico de atención al paciente",
    "personal care assistant": "Auxiliar de cuidado personal",
    "pest control technician": "Técnico de control de plagas",
    "physical therapist": "Fisioterapeuta",
    "physical therapist assistant": "Auxiliar de fisioterapia",
    "physical therapist degree": "Fisioterapeuta",
    "physical therapist prn": "Fisioterapeuta",
    "physical therapist pt": "Fisioterapeuta",
    "physical therapy assistant": "Auxiliar de fisioterapia",
    "prep cook": "Auxiliar de cocina",
    "preschool before after school teacher bus driver": "Docente de preescolar",
    "producer": "Productor",
    "product designer": "Diseñador de producto",
    "product engineer": "Ingeniero de producto",
    "product manager": "Gerente de producto",
    "program manager": "Gerente de programa",
    "quality engineer": "Ingeniero de calidad",
    "registered behavior technician rbt": "Técnico en análisis conductual",
    "registered nurse rn": "Enfermero(a) registrado(a)",
    "registered practical nurse": "Enfermero(a) práctico(a)",
    "registered veterinary nurse": "Auxiliar veterinario(a)",
    "reporter": "Periodista",
    "restaurant general manager": "Gerente general de restaurante",
    "restaurant manager": "Gerente de restaurante",
    "sales": "Ventas",
    "sales developer representative": "Representante de desarrollo de ventas",
    "sales manager": "Gerente de ventas",
    "server": "Mesero",
    "shift leader": "Líder de turno",
    "shift manager": "Jefe de turno",
    "small animal veterinarian": "Veterinario de animales pequeños",
    "store manager": "Gerente de tienda",
    "structural engineer": "Ingeniero estructural",
    "structural project engineer": "Ingeniero de proyectos estructurales",
    "substitute teacher": "Docente sustituto",
    "support worker": "Asistente de apoyo",
    "systems engineer": "Ingeniero de sistemas",
    "taxi fleet partners": "Socios de flota de taxis",
    "teacher": "Docente",
    "teachers": "Docentes",
    "team member": "Miembro de equipo",
    "warehouse": "Operario de bodega",
    "water wastewater engineer": "Ingeniero de aguas residuales",

    # Añadidos tras ampliar el backfill de Adzuna a la 2ª keyword por programa
    # (2026-08-25): estos cargos empezaron a aparecer con volumen real en el
    # top de "Demanda actual" y "Cargos más demandados" sin traducción.
    "video editor": "Editor de video",
    "financial analyst digital remote": "Analista financiero digital (remoto)",
    "civil structural engineer": "Ingeniero civil y estructural",
    "nurse": "Enfermero(a)",
    "director scientific communications cns": "Director de comunicaciones científicas",
    "legal counsel": "Asesor jurídico",
    "marketing design intern 2025 summer intern": "Practicante de diseño de marketing",
    "business analyst": "Analista de negocios",
    "graphic designer": "Diseñador gráfico",
    "bartender": "Barman",
    "devops engineer": "Ingeniero DevOps",
    "technical simulation platform galileo": "Líder técnico de simulación (Galileo)",
    "executive assistant": "Asistente ejecutivo(a)",
    "community manager": "Community Manager",
    "branch manager": "Gerente de sucursal",
    "sales executive": "Ejecutivo de ventas",
    "social media manager": "Gerente de redes sociales",
    "embedded engineer": "Ingeniero de sistemas embebidos",
    "projects": "Asociado de proyectos",
    "self employed estate agent": "Agente inmobiliario independiente",
    "hr administrator": "Administrador de RRHH",
    "nga ai engineer manager": "Gerente de ingeniería de IA",
    "solutions engineer": "Ingeniero de soluciones",
    "financial services tax real estate manager": "Gerente de impuestos inmobiliarios",
    "life sciences lab system support": "Soporte de laboratorio (ciencias de la vida)",
    "field applications scientist upstream bioproduction processing ma": "Científico de aplicaciones de campo (bioproducción)",
    "human resources manager": "Gerente de recursos humanos",
    "car delivery driver": "Conductor de entrega de vehículos",
    "cfoev finance transformation manager": "Gerente de transformación financiera",
    "business developer": "Desarrollador de negocios",
    "occupational therapist": "Terapeuta ocupacional",
    "hr business partner": "Socio estratégico de RRHH",
    "investment advisor": "Asesor de inversiones",
    "vp ai engineering": "VP de ingeniería de IA",
    "ai ml engineer": "Ingeniero de IA/ML",
    "finance manager": "Gerente financiero",
    "remote data clerk work at home": "Auxiliar de digitación remoto",
    "air force a10 arms control cwmd analyst hq usafe ramstein germany": "Analista de control de armas (Fuerza Aérea)",
    "chef": "Chef",
    "property manager": "Administrador de propiedades",
    "digital marketing manager": "Gerente de marketing digital",
    "cloud analyst": "Analista de nube",
    "sales representative": "Representante de ventas",
    "product marketing manager": "Gerente de marketing de producto",
    "medical physiotherapist": "Fisioterapeuta médico",
    "platform engineer": "Ingeniero de plataforma",
    "management trainee": "Trainee de gestión",
    "customer success manager": "Gerente de éxito del cliente",
    "solution architect": "Arquitecto de soluciones",

    # Añadidos tras filtrar el ruido de keywords amplias (2026-08-25, ver
    # coincide_con_keyword en config.py): con menos ruido compitiendo por
    # volumen, estos términos genuinos quedaron visibles sin traducir.
    "business manager": "Gerente de negocios",
    "business office manager": "Gerente de oficina",
    "it business manager": "Gerente de negocios de TI",
    "new business manager": "Gerente de nuevos negocios",
    "digital marketing specialist": "Especialista en marketing digital",
    "digital marketing executive": "Ejecutivo de marketing digital",
    "digital marketing coordinator": "Coordinador de marketing digital",
    "digital marketing intern": "Practicante de marketing digital",
    "field marketing manager": "Gerente de marketing de campo",
    "marketing sales manager": "Gerente de marketing y ventas",
    "growth marketing manager": "Gerente de marketing de crecimiento",
    "influencer marketing manager": "Gerente de marketing de influencers",
    "data governance analyst": "Analista de gobierno de datos",
    "business data analyst": "Analista de datos de negocio",
    "ecommerce data analyst remote": "Analista de datos de e-commerce (remoto)",
    "data management analyst": "Analista de gestión de datos",
    "financial data analyst": "Analista de datos financieros",
    "marketing data scientist": "Científico de datos de marketing",
    "data quality analyst": "Analista de calidad de datos",
    # Mismo término que "analista político" (keyword en español) para que
    # ambos idiomas se fusionen en una sola barra en vez de dos separadas.
    "political analyst": "Analista político",
    "political science analyst intern": "Practicante de análisis en ciencia política",
    "political research analyst": "Analista de investigación política",
    "geopolitical analyst": "Analista geopolítico",
    "organizational developer specialist": "Especialista en desarrollo organizacional",
    "corporate manager talent management": "Gerente corporativo de gestión del talento",
    "talent management intern": "Practicante de gestión del talento",
    "talent management analyst hr": "Analista de gestión del talento (RRHH)",

    # Formas en español que salían mal formadas por el bug de "Administrador(a)"
    # en normalize_title (ya arreglado ahí) o simplemente sin mayúsculas por
    # venir en minúscula desde la fuente. Donde ya existe un equivalente en
    # inglés en este diccionario, se usa la MISMA traducción para que se
    # fusionen en un solo término en vez de aparecer como barras separadas.
    "administrador empresas": "Administrador(a) de Empresas",
    "director desarrollo organizacional": "Director(a) de Desarrollo Organizacional",
    "científico datos": "Científico de datos",
    "cientifico datos": "Científico de datos",
    "coordinador contable": "Coordinador(a) Contable",
    "consultor sénior desarrollo organizacional": "Consultor(a) Sénior de Desarrollo Organizacional",
    "gerente operaciones": "Gerente de operaciones",
    "analista administrativo": "Analista administrativo",
    "analista mercadeo": "Analista de mercadeo",
    "analista logística": "Analista de logística",
    "analista comercio exterior": "Analista de comercio exterior",
    "analista recursos humanos": "Analista de recursos humanos",
    "analista datos": "Analista de datos",
    "analista inteligencia negocios": "Analista de inteligencia de negocios",
    "coordinador desarrollo organizacional": "Coordinador(a) de Desarrollo Organizacional",
    "auxiliar desarrollo organizacional": "Auxiliar de Desarrollo Organizacional",
    "analista desarrollo organizacional": "Analista de Desarrollo Organizacional",
    "especialista desarrollo organizacional": "Especialista en Desarrollo Organizacional",
    "analista gestión talento": "Analista de Gestión del Talento",
    # ── Ciencias Políticas y afines ──────────────────────────────────────────
    # Su cola larga es casi toda cargo académico estadounidense: al buscar
    # "public policy" Adzuna devuelve sobre todo plazas de universidad. Se
    # traducen en vez de dejarlas en inglés, pero se mantienen DISTINTAS entre
    # sí (un decano no es un profesor asistente).
    "public policy analyst": "Analista de políticas públicas",
    "policy analyst": "Analista de políticas públicas",
    "specialist public policy": "Especialista en políticas públicas",
    "public policy specialist": "Especialista en políticas públicas",
    "public policy graduate research intern": "Practicante de investigación en políticas públicas",
    "practicante análisis ciencia política": "Practicante de análisis en ciencia política",
    "political analyst": "Analista político",
    "adjunct faculty": "Docente adjunto",
    "adjunct professor": "Profesor adjunto",
    "assistant professor": "Profesor asistente",
    "associate professor": "Profesor asociado",
    "lecturer": "Profesor",
    "postdoctoral": "Investigador posdoctoral",
    "post doctoral": "Investigador posdoctoral",
    "postdoctoral researcher": "Investigador posdoctoral",
    "dean": "Decano",
    "executive director": "Director ejecutivo",
    "docente sustituto": "Docente sustituto",
    "social worker": "Trabajador(a) social",
    # ── Negocios internacionales ─────────────────────────────────────────────
    "business developer": "Gerente de desarrollo de negocios",
    "business development": "Gerente de desarrollo de negocios",
    "aprendiz negocios internacionales": "Aprendiz de negocios internacionales",
    "freight forwarder": "Agente de carga internacional",
    "foreign trade analyst": "Analista de comercio exterior",
    # ── Cargos frecuentes en la cola larga (medidos, no supuestos) ───────────
    "full stack developer": "Desarrollador full stack",
    "full stack engineer": "Ingeniero full stack",
    "multimedia specialist": "Especialista en multimedios",
    "video producer": "Productor audiovisual",
    "public relations manager": "Gerente de relaciones públicas",
    "corporate lawyer": "Abogado corporativo",
    "investment banking analyst": "Analista de banca de inversión",
    "financial planning analyst": "Analista de planeación financiera",
    "financial reporting analyst": "Analista de reportes financieros",
    "commis chef": "Ayudante de cocina",
    "physiotherapist": "Fisioterapeuta",
    "ingeniero procesos": "Ingeniero de procesos",
    "ingeniero mantenimiento": "Ingeniero de mantenimiento",
    "ingeniero machine learning": "Ingeniero de machine learning",
    "ingeniero diseño mecánico": "Ingeniero de diseño mecánico",
    "ingeniero estructural": "Ingeniero estructural",
    "auxiliar enfermería": "Auxiliar de enfermería",
    "analista servicio cliente": "Analista de servicio al cliente",
    "analista selección": "Analista de selección",
    "medico general": "Médico general",
    "residente obra": "Residente de obra",
    "jefe cocina": "Jefe de cocina",
    "administrador restaurante": "Administrador(a) de restaurante",
    "docente preescolar": "Docente de preescolar",
    "human resources generalist": "Generalista de recursos humanos",
    "hr generalist": "Generalista de recursos humanos",
    "hr manager": "Gerente de recursos humanos",
    "recruiter": "Reclutador(a)",
    "talent acquisition specialist": "Especialista en atracción de talento",
    # ── Últimos restos en inglés detectados en la auditoría por programa ─────
    "immigration lawyer": "Abogado de inmigración",
    "family lawyer": "Abogado de familia",
    "personal injury lawyer": "Abogado de daños personales",
    "criminal lawyer": "Abogado penalista",
    "multimedia journalist": "Periodista multimedia",
    "physician assistant": "Asistente médico",
    "medical doctor": "Médico",
    "bioprocess engineer": "Ingeniero de bioprocesos",
    "bioprocess developer engineer": "Ingeniero de desarrollo de bioprocesos",
    "customer service manager": "Gerente de servicio al cliente",
    "chemical process engineering professionals": "Ingeniero de procesos químicos",
    "industrial refrigeration engineer": "Ingeniero de refrigeración industrial",
    "school psychologist": "Psicólogo escolar",
    "corporate counsel": "Abogado corporativo",
    "account executive": "Ejecutivo de cuenta",
    "community manager": "Community Manager",
}

# ─────────────────────────────────────────────────────────────────────────────
# Tecnologías de O*NET: nombres verbosos → forma limpia. La mayoría de las
# tecnologías son marcas que NO se traducen (Python, Docker, Power BI); aquí solo
# se normalizan las etiquetas descriptivas en inglés y las que arrastran el
# sufijo " software". Conjunto FINITO conocido (diccionario_skills.json).
# ─────────────────────────────────────────────────────────────────────────────
TECNOLOGIAS: dict[str, str] = {
    "Structured query language SQL": "SQL",
    "Cascading style sheets CSS": "CSS",
    "Hypertext markup language HTML": "HTML",
    "Extensible markup language XML": "XML",
    "JavaScript Object Notation JSON": "JSON",
    "Border Gateway Protocol BGP": "BGP",
    "Dassault Systemes SolidWorks": "SolidWorks",
    "ESRI ArcGIS software": "ArcGIS",
    "Amazon Web Services AWS software": "Amazon Web Services (AWS)",
    "eClinicalWorks EHR software": "eClinicalWorks (historia clínica)",
    "Adobe Creative Cloud software": "Adobe Creative Cloud",
    "Google Workspace software": "Google Workspace",
    "Microsoft Azure software": "Microsoft Azure",
    "Microsoft Office software": "Microsoft Office",
    "Oracle Cloud software": "Oracle Cloud",
}


def traducir_sector(label: str | None) -> str | None:
    """Sector de Adzuna EN→ES (fallback al original)."""
    if label is None:
        return None
    return SECTORES.get(label, label)


def traducir_modalidad(valor: str | None) -> str | None:
    """Modalidad de Adzuna EN→ES (fallback al original)."""
    if valor is None:
        return None
    return MODALIDAD.get(str(valor).lower(), valor)


# ═════════════════════════════════════════════════════════════════════════════
# CANONICALIZACIÓN DE CARGOS
# ═════════════════════════════════════════════════════════════════════════════
# `CARGOS` es un diccionario de coincidencia EXACTA, y eso no escala: medido
# sobre las 14.142 vacantes que pasan los filtros de calidad, hay 8.750 títulos
# normalizados DISTINTOS y las 275 entradas curadas a mano solo cubrían el
# 20,3%. El 79,7% restante se pintaba crudo en las gráficas, casi siempre en
# inglés y con basura pegada al nombre del cargo.
#
# Diagnóstico sobre los datos reales (no hipotético):
#
#   1. RUIDO. El título trae cosas que no son el cargo: ciudad ("Gerente de
#      Operaciones | RESTAURANTES | CALI"), identificador de la oferta
#      ("Gerente de operaciones 1626430055-20"), modalidad ("remote", "per
#      diem") y reclamos ("urgent hiring"). 949 títulos distintos llevaban
#      números pegados. Cada variante se contaba como un cargo aparte, así que
#      "Gerente de operaciones" aparecía partido en 5 barras distintas.
#
#   2. TILDES. "auxiliar enfermería" y "auxiliar enfermeria" se contaban por
#      separado siendo el mismo cargo.
#
#   3. COLA LARGA. Un título con una palabra de más ("data scientist product
#      analytics") fallaba el match exacto contra "data scientist" y caía al
#      inglés crudo.
#
# La solución es una cascada de 4 niveles, de más preciso a más general:
#
#   canonizar → exacto → prefijo → contenido → composición → respaldo
#
# Resultado medido sobre las mismas 14.142 vacantes: cobertura 20,3% → 65,6%,
# y las etiquetas que quedaban en inglés bajaron del 35,4% al 15,4%.
# ═════════════════════════════════════════════════════════════════════════════

import re
import unicodedata

# Ubicaciones que aparecen pegadas al cargo. La lista se construyó mirando los
# tokens más frecuentes al final del título en la muestra real (ahí es donde
# las fuentes suelen colgar la ciudad), no inventando nombres.
_UBICACIONES: set[str] = {
    # Colombia
    "bogota", "medellin", "cali", "barranquilla", "cartagena", "bucaramanga",
    "pereira", "manizales", "cucuta", "ibague", "villavicencio", "armenia",
    "neiva", "monteria", "pasto", "popayan", "tunja", "sincelejo", "valledupar",
    "riohacha", "quibdo", "florencia", "yopal", "mosquera", "chia", "cajica",
    "zipaquira", "soacha", "funza", "cundinamarca", "antioquia", "atlantico",
    "autonorte", "colombia", "usaquen", "suba", "chapinero", "kennedy",
    # Países y regiones
    "usa", "us", "eeuu", "uk", "canada", "mexico", "spain", "espana", "latam",
    "latinoamerica", "emea", "apac", "worldwide", "overseas", "nationwide",
    # Reino Unido
    "london", "manchester", "birmingham", "leeds", "glasgow", "edinburgh",
    "liverpool", "bristol", "sheffield", "cardiff", "belfast", "nottingham",
    # España
    "barcelona", "madrid", "valencia", "sevilla", "bilbao", "malaga",
    "zaragoza", "murcia", "granada", "alicante", "valladolid", "vigo",
    # Canadá
    "toronto", "vancouver", "montreal", "calgary", "ottawa", "edmonton",
    "winnipeg", "quebec", "halifax", "saskatoon", "regina",
    # México
    "guadalajara", "monterrey", "puebla", "queretaro", "tijuana", "cancun",
    "merida", "toluca",
    # Estados Unidos
    "chicago", "houston", "phoenix", "philadelphia", "dallas", "austin",
    "seattle", "denver", "boston", "atlanta", "miami", "portland", "detroit",
    "minneapolis", "tampa", "orlando", "sacramento", "pittsburgh", "cincinnati",
    "cleveland", "baltimore", "milwaukee", "nashville", "memphis", "louisville",
    "indianapolis", "columbus", "charlotte", "raleigh",
    # Siglas de estado/provincia (van sueltas al final: "... - Austin, TX")
    "ny", "ca", "tx", "fl", "il", "pa", "oh", "ga", "nc", "mi", "nj", "va",
    "wa", "az", "ma", "tn", "mo", "md", "wi", "mn", "al", "sc", "ky", "or",
    "ok", "ct", "ut", "ia", "nv", "ar", "ms", "ks", "nm", "ne", "wv", "hi",
    "nh", "ri", "mt", "sd", "nd", "ak", "vt", "wy",
    "on", "bc", "ab", "qc", "mb", "sk", "ns", "nb",
}

# Modalidad, urgencia y muletillas de anuncio: describen la oferta, no el cargo.
_MODALIDAD_RUIDO: set[str] = {
    "remote", "remoto", "remota", "hybrid", "hibrido", "onsite", "presencial",
    "telecommute", "wfh", "virtual", "fulltime", "parttime", "tiempo",
    "completo", "medio", "prn", "diem", "casual", "contract", "contractor",
    "temporary", "temporal", "permanent", "permanente", "freelance", "nights",
    "night", "weekend", "weekends", "shift", "turno", "required", "requerido",
    "clearance", "experience", "experiencia", "degree", "level", "urgent",
    "urgente", "inmediato", "immediate", "hiring", "now", "apply", "opening",
    "openings", "vacante", "vacancy", "job", "jobs", "empleo", "trabajo",
    "position", "role", "opportunity", "oportunidad", "needed", "wanted",
    "sign", "bonus", "w", "relocation",
}

_RUIDO_CARGO = _UBICACIONES | _MODALIDAD_RUIDO

# Bigramas que hay que blindar ANTES de quitar ruido palabra por palabra.
# Sin esto "full stack developer" perdía "full" (está en _MODALIDAD_RUIDO por
# "full time") y se convertía en "stack developer" — el 3.º título más
# frecuente sin traducir en la primera medición. El valor vacío significa
# "bórralo entero" (es ruido de dos palabras, como "per diem" o "new york").
_BIGRAMAS_PROTEGIDOS: dict[str, str] = {
    "full stack": "fullstack",
    "front end": "frontend",
    "back end": "backend",
    "machine learning": "machinelearning",
    "new york": "",
    "santa marta": "",
    "per diem": "",
    "full time": "",
    "part time": "",
}


def _sin_tildes(texto: str) -> str:
    """'enfermería' -> 'enfermeria'. Para que las variantes no se separen."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def canonizar_cargo(titulo_normalizado: str) -> str:
    """Quita del título normalizado todo lo que no es el nombre del cargo.

    Opera sobre la salida de `normalize_title` (Adzuna/adzuna_service.py), no
    sobre el título crudo. Va aquí y no dentro de `normalize_title` a
    propósito: la salida de aquella función es el FORMATO DE CLAVE de las 275
    entradas curadas de `CARGOS` y de cualquier otro consumidor, así que
    cambiarla invalidaría en silencio ese trabajo. Esta limpieza es del
    momento de traducir, no de normalizar.
    """
    if not titulo_normalizado:
        return ""

    texto = _sin_tildes(titulo_normalizado.lower())

    # Blindar/eliminar bigramas antes del filtrado token a token.
    for bigrama, reemplazo in _BIGRAMAS_PROTEGIDOS.items():
        texto = texto.replace(bigrama, f" {reemplazo} " if reemplazo else " ")

    tokens = [
        t for t in texto.split()
        if t not in _RUIDO_CARGO
        # Números sueltos y códigos de oferta ("1626430055", "20", "id71005").
        and not re.fullmatch(r"\d+", t)
        and not re.fullmatch(r"[a-z]{0,3}\d{2,}[a-z\d]*", t)
    ]
    texto = " ".join(tokens)

    # Restaurar los bigramas blindados.
    for bigrama, reemplazo in _BIGRAMAS_PROTEGIDOS.items():
        if reemplazo:
            texto = texto.replace(reemplazo, bigrama)

    return re.sub(r"\s+", " ", texto).strip()


# ── Capa composicional: núcleo + modificador ────────────────────────────────
# Para los títulos que ninguna entrada de `CARGOS` cubre. La cola larga está
# muy concentrada en unos pocos sustantivos núcleo (engineer 475, analyst 271,
# developer 125, lawyer 122, teacher 116...), así que traducir "<modificador>
# <núcleo>" de forma composicional cubre mucho con poco diccionario.
_NUCLEOS: dict[str, str] = {
    "engineer": "Ingeniero", "engineering": "Ingeniero", "analyst": "Analista",
    "developer": "Desarrollador", "lawyer": "Abogado", "attorney": "Abogado",
    "teacher": "Docente", "teachers": "Docente", "manager": "Gerente",
    "chef": "Chef", "specialist": "Especialista", "physician": "Médico",
    "nurse": "Enfermero(a)", "journalist": "Periodista", "producer": "Productor",
    "consultant": "Consultor", "designer": "Diseñador", "scientist": "Científico",
    "director": "Director", "coordinator": "Coordinador",
    "supervisor": "Supervisor", "assistant": "Asistente",
    "technician": "Técnico", "architect": "Arquitecto", "accountant": "Contador",
    "therapist": "Terapeuta", "economist": "Economista",
    "psychologist": "Psicólogo", "professor": "Profesor",
    "researcher": "Investigador", "writer": "Redactor", "editor": "Editor",
    "recruiter": "Reclutador", "representative": "Representante",
    "administrator": "Administrador", "planner": "Planificador",
    "auditor": "Auditor", "advisor": "Asesor", "programmer": "Programador",
    "surgeon": "Cirujano", "pharmacist": "Farmacéutico", "dentist": "Odontólogo",
    "veterinarian": "Veterinario", "translator": "Traductor",
    "generalist": "Generalista", "paralegal": "Asistente jurídico",
    "practitioner": "Profesional", "officer": "Oficial", "agent": "Agente",
}

_MODIFICADORES: dict[str, str] = {
    "civil": "civil", "mechanical": "mecánico", "industrial": "industrial",
    "chemical": "químico", "software": "de software",
    "structural": "estructural", "electrical": "eléctrico",
    "electronic": "electrónico", "financial": "financiero",
    "finance": "financiero", "data": "de datos", "marketing": "de marketing",
    "security": "de seguridad", "quality": "de calidad", "sales": "de ventas",
    "product": "de producto", "project": "de proyectos",
    "business": "de negocios", "process": "de procesos", "design": "de diseño",
    "systems": "de sistemas", "system": "de sistemas", "network": "de redes",
    "cloud": "de la nube", "frontend": "frontend", "backend": "backend",
    "full stack": "full stack", "machine learning": "de machine learning",
    "ai": "de IA", "environmental": "ambiental", "biomedical": "biomédico",
    "aerospace": "aeroespacial", "automation": "de automatización",
    "manufacturing": "de manufactura", "production": "de producción",
    "logistics": "de logística", "supply": "de cadena de suministro",
    "operations": "de operaciones", "digital": "digital",
    "content": "de contenido", "corporate": "corporativo", "legal": "jurídico",
    "tax": "tributario", "audit": "de auditoría", "risk": "de riesgos",
    "credit": "de crédito", "investment": "de inversiones",
    "banking": "de banca", "accounting": "contable",
    "hr": "de recursos humanos", "human resources": "de recursos humanos",
    "recruitment": "de selección", "training": "de formación",
    "clinical": "clínico", "medical": "médico", "surgical": "quirúrgico",
    "pediatric": "pediátrico", "mental health": "de salud mental",
    "public health": "de salud pública", "physical": "físico",
    "preschool": "de preescolar", "elementary": "de primaria",
    "secondary": "de secundaria", "special education": "de educación especial",
    "early childhood": "de primera infancia", "science": "de ciencias",
    "math": "de matemáticas", "mathematics": "de matemáticas",
    "english": "de inglés", "web": "web", "mobile": "móvil", "java": "Java",
    "python": "Python", "test": "de pruebas", "qa": "de calidad",
    "devops": "DevOps", "policy": "de políticas",
    "public policy": "de políticas públicas",
    "communications": "de comunicaciones",
    "public relations": "de relaciones públicas",
    "customer": "de servicio al cliente", "field": "de campo",
    "site": "de obra", "maintenance": "de mantenimiento", "water": "de aguas",
    "energy": "de energía", "construction": "de construcción",
    "traffic": "de tránsito", "geotechnical": "geotécnico",
    "telecommunications": "de telecomunicaciones",
}

# Modificadores de varias palabras, del más largo al más corto: "early
# childhood teacher" debe ganarle a "childhood".
_MODIFICADORES_COMPUESTOS = sorted(
    (m for m in _MODIFICADORES if " " in m),
    key=lambda m: -len(m.split()),
)


def _componer_cargo(canonico: str) -> str | None:
    """'civil engineer' -> 'Ingeniero civil'. None si no se puede componer.

    Devuelve None (en vez de solo el núcleo) cuando el modificador es
    desconocido: quedarse con "Analista" a secas fusionaría en una sola barra
    cargos tan distintos como 'investment banking analyst' y 'policy analyst'.
    Perder cobertura es preferible a inventar una agrupación falsa.
    """
    tokens = canonico.split()
    if not tokens:
        return None

    base = _NUCLEOS.get(tokens[-1])
    if not base:
        return None

    resto = " ".join(tokens[:-1])
    if not resto:
        return base
    for compuesto in _MODIFICADORES_COMPUESTOS:
        if resto.endswith(compuesto):
            return f"{base} {_MODIFICADORES[compuesto]}"
    modificador = _MODIFICADORES.get(tokens[-2]) if len(tokens) >= 2 else None
    return f"{base} {modificador}" if modificador else None


# Índice de `CARGOS` con las claves ya canonizadas, para que el match ignore
# tildes y ruido igual que lo hace el título entrante. Se construye una sola
# vez al importar. `setdefault` conserva la primera de dos claves que colapsen
# a la misma forma canónica (el orden del dict es el de escritura, así que gana
# la entrada declarada antes).
_INDICE_CARGOS: dict[str, str] = {}
for _clave, _valor in CARGOS.items():
    _INDICE_CARGOS.setdefault(canonizar_cargo(_clave) or _sin_tildes(_clave), _valor)

# Ordenadas de más palabras a menos: el match más específico debe ganar.
_CLAVES_POR_LONGITUD = sorted(_INDICE_CARGOS, key=lambda k: -len(k.split()))


def traducir_cargo(titulo_normalizado: str | None) -> str | None:
    """Cargo normalizado -> nombre de rol limpio y en español.

    Cascada de 4 niveles (ver el bloque de arriba para el porqué):

      1. EXACTO     — la forma canónica está en `CARGOS`.
      2. PREFIJO    — el título EMPIEZA por una entrada conocida:
                      'data scientist product analytics' -> 'Científico de datos'.
      3. CONTENIDO  — una entrada conocida (de 2+ palabras, para no disparar
                      con genéricos) aparece dentro:
                      'global business developer manager' -> 'Gerente de
                      desarrollo de negocios'.
      4. COMPOSICIÓN — núcleo + modificador: 'civil engineer' -> 'Ingeniero civil'.

    Si nada aplica, devuelve el título ya CANONIZADO (sin ciudad, sin código de
    oferta) con la inicial en mayúscula. Sigue pudiendo quedar en inglés, pero
    al menos es el cargo y no el cargo más la ciudad.
    """
    if titulo_normalizado is None:
        return None

    canonico = canonizar_cargo(titulo_normalizado)
    if not canonico:
        return titulo_normalizado or None

    if canonico in _INDICE_CARGOS:
        return _INDICE_CARGOS[canonico]

    for clave in _CLAVES_POR_LONGITUD:
        if canonico.startswith(clave + " "):
            return _INDICE_CARGOS[clave]

    for clave in _CLAVES_POR_LONGITUD:
        if len(clave.split()) >= 2 and f" {clave} " in f" {canonico} ":
            return _INDICE_CARGOS[clave]

    compuesto = _componer_cargo(canonico)
    if compuesto:
        return compuesto

    return canonico[0].upper() + canonico[1:]


def traducir_tecnologia(nombre: str | None) -> str | None:
    """Nombre de tecnología O*NET a forma limpia. Regla extra: quita ' software'."""
    if nombre is None:
        return None
    if nombre in TECNOLOGIAS:
        return TECNOLOGIAS[nombre]
    if nombre.endswith(" software"):
        return nombre[: -len(" software")]
    return nombre
