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


def traducir_cargo(titulo_normalizado: str | None) -> str | None:
    """Cargo normalizado EN→ES limpio (fallback al título normalizado)."""
    if titulo_normalizado is None:
        return None
    return CARGOS.get(titulo_normalizado, titulo_normalizado)


def traducir_tecnologia(nombre: str | None) -> str | None:
    """Nombre de tecnología O*NET a forma limpia. Regla extra: quita ' software'."""
    if nombre is None:
        return None
    if nombre in TECNOLOGIAS:
        return TECNOLOGIAS[nombre]
    if nombre.endswith(" software"):
        return nombre[: -len(" software")]
    return nombre
