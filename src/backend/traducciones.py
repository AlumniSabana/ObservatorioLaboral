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

# ═════════════════════════════════════════════════════════════════════════════
# AGRUPACIÓN DE SECTORES EN 18 GRUPOS ECONÓMICOS
# ═════════════════════════════════════════════════════════════════════════════
# Taxonomía única de sector de todo el Observatorio. Reemplaza dos cosas que
# convivían mal: los ~29 sectores finos de Adzuna (demasiado granulares y en su
# propia lógica de "job board") y una agrupación previa en 6 campos alineados a
# las áreas académicas de la Sabana. Los 18 grupos son SECTORES ECONÓMICOS, que
# es lo que se quiere leer en el dashboard.
#
# POR QUÉ SE NORMALIZA EL PREFIJO Y NO SE LISTAN TODAS LAS VARIANTES
# Adzuna entrega 29 etiquetas fijas (ya traducidas por SECTORES), pero Google
# Jobs y LinkedIn entregan las suyas con prefijo variable sobre el MISMO tema:
# "Empleos en informática", "Trabajos en informática", "Empleos de
# mantenimiento", "Trabajos de limpieza"... Medido en BD: 76 valores distintos
# que se reducen a ~30 temas. Listar las 76 sería frágil (cada fuente nueva
# inventa su prefijo); normalizar el prefijo y mapear el TEMA cubre las que ya
# existen y las que vengan.
#
# LÍMITE HONESTO DE LA FUENTE: estas etiquetas son de bolsas de empleo, no una
# clasificación industrial. Algunas mezclan dos de los 18 grupos y hay que
# elegir; esas decisiones van comentadas abajo. Lo que no es un sector
# (modalidad, nivel) cae en "Otros / general", y "Sin especificar" se deja
# aparte porque es ausencia de dato, no un sector sin encaje.
# ═════════════════════════════════════════════════════════════════════════════

AGROPECUARIO = "Agroindustria y sector agropecuario"
MINERIA = "Minería, petróleo y gas"
INDUSTRIA = "Industria y manufactura"
ENERGIA = "Energía, agua y servicios públicos"
CONSTRUCCION = "Construcción e infraestructura"
COMERCIO = "Comercio, retail y consumo"
TRANSPORTE = "Transporte, logística y cadena de suministro"
TURISMO = "Turismo, hotelería y gastronomía"
MEDIOS = "Medios, comunicación y contenidos"
TECNOLOGIA = "Tecnología, software, telecomunicaciones y datos"
FINANCIERO = "Servicios financieros, seguros y Fintech"
INMOBILIARIO = "Inmobiliario y bienes raíces"
CONSULTORIA = "Consultoría y servicios profesionales"
EMPRESARIALES = "Servicios empresariales, BPO y talento humano"
GOBIERNO = "Gobierno y sector público"
EDUCACION = "Educación"
SALUD = "Salud y ciencias de la vida"
CREATIVAS = "Industrias creativas, cultura, deporte y entretenimiento"

# Los 18, en el orden en que se declararon (para UI o validación).
GRUPOS_SECTOR_18: tuple[str, ...] = (
    AGROPECUARIO, MINERIA, INDUSTRIA, ENERGIA, CONSTRUCCION, COMERCIO,
    TRANSPORTE, TURISMO, MEDIOS, TECNOLOGIA, FINANCIERO, INMOBILIARIO,
    CONSULTORIA, EMPRESARIALES, GOBIERNO, EDUCACION, SALUD, CREATIVAS,
)

# Residuales: NO son ninguno de los 18 y no se fuerzan a uno.
OTROS_SECTOR = "Otros / general"
SIN_ESPECIFICAR = "Sin especificar"

# Prefijos con que Google Jobs / LinkedIn envuelven el tema.
_PREFIJOS_TEMA = ("empleos en ", "trabajos en ", "empleos de ", "trabajos de ")

# TEMA normalizado (minúsculas, sin tildes, sin prefijo) -> uno de los 18.
GRUPOS_SECTOR: dict[str, str] = {
    # Tecnología
    "tecnologia (ti)": TECNOLOGIA,
    "informatica": TECNOLOGIA,
    # Salud y ciencias de la vida. "Ciencia y control de calidad" (Scientific &
    # QA) mezcla investigación científica con control de calidad industrial; se
    # manda a ciencias de la vida porque la parte científica es la que domina.
    "salud y enfermeria": SALUD,
    "sanidad y salud": SALUD,
    "ciencia y control de calidad": SALUD,
    "ciencias y control de calidad": SALUD,
    # Industria. "Ingeniería" es el sector más grande de Adzuna (9.991 filas) y
    # es una FUNCIÓN, no un sector: cubre manufactura, obra y energía a la vez.
    # Se asigna a industria por ser el destino industrial más frecuente; es la
    # decisión más discutible de este mapa.
    "ingenieria": INDUSTRIA,
    "manufactura": INDUSTRIA,
    "fabricacion y manufactura": INDUSTRIA,
    "mantenimiento": INDUSTRIA,
    # Construcción
    "oficios y construccion": CONSTRUCCION,
    "construccion": CONSTRUCCION,
    # Minería, petróleo y gas. La etiqueta de Adzuna es "Energy, Oil & Gas":
    # cae aquí y no en ENERGIA porque "petróleo y gas" es explícito en ella,
    # mientras que servicios públicos (agua, redes) no aparece.
    "energia, petroleo y gas": MINERIA,
    # Comercio
    "ventas": COMERCIO,
    "comercio minorista": COMERCIO,
    "tiendas": COMERCIO,
    # Transporte y logística
    "logistica y almacenamiento": TRANSPORTE,
    "logistica y almacen": TRANSPORTE,
    # Turismo
    "hosteleria y gastronomia": TURISMO,
    "hosteleria y restauracion": TURISMO,
    "turismo y viajes": TURISMO,
    "turismo": TURISMO,
    # Medios y comunicación
    "comunicacion, publicidad y marketing": MEDIOS,
    "marketing, publicidad y relaciones publicas": MEDIOS,
    # Financiero
    "contabilidad y finanzas": FINANCIERO,
    # Inmobiliario
    "inmobiliario": INMOBILIARIO,
    "inmobiliarias": INMOBILIARIO,
    # Consultoría y servicios profesionales (incluye lo jurídico: despachos).
    "consultoria": CONSULTORIA,
    "juridico": CONSULTORIA,
    "legal": CONSULTORIA,
    # Servicios empresariales / BPO / talento humano. Aquí van administración,
    # RR.HH., atención al cliente (el corazón del BPO colombiano) y servicios
    # de aseo/facility.
    "administracion": EMPRESARIALES,
    "recursos humanos y seleccion": EMPRESARIALES,
    "recursos humanos": EMPRESARIALES,
    "servicio al cliente": EMPRESARIALES,
    "atencion al cliente": EMPRESARIALES,
    "servicio domestico y limpieza": EMPRESARIALES,
    "limpieza": EMPRESARIALES,
    # Gobierno y sector público: trabajo social y ONG son interés público.
    "trabajo social": GOBIERNO,
    "ong y voluntariado": GOBIERNO,
    # Educación
    "educacion": EDUCACION,
    # Industrias creativas
    "diseno y creatividad": CREATIVAS,
    "diseno y artes graficas": CREATIVAS,
    # NO son sectores: describen modalidad o nivel del puesto.
    "empleos de medio tiempo": OTROS_SECTOR,
    "medio tiempo": OTROS_SECTOR,
    "recien graduados": OTROS_SECTOR,
    "otros empleos": OTROS_SECTOR,
    "otros trabajos": OTROS_SECTOR,
    "otros / general": OTROS_SECTOR,
}


def _tema_sector(sector_es: str) -> str:
    """'Empleos en Informática' -> 'informatica'. Quita prefijo de fuente."""
    plano = _sin_tildes(sector_es.lower()).strip()
    for prefijo in _PREFIJOS_TEMA:
        if plano.startswith(prefijo):
            return plano[len(prefijo):].strip()
    return plano


def agrupar_sector(sector_es: str | None) -> str | None:
    """Colapsa un sector YA TRADUCIDO (salida de `traducir_sector`) en uno de
    los 18 grupos económicos.

    "Sin especificar" se deja tal cual (ausencia de dato) y lo que no encaja en
    ningún grupo cae en "Otros / general" en vez de forzarlo.
    """
    if not sector_es or sector_es == SIN_ESPECIFICAR:
        return sector_es
    return GRUPOS_SECTOR.get(_tema_sector(sector_es), OTROS_SECTOR)


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
    "director desarrollo organizacional": "Director(a) de desarrollo organizacional",
    "científico datos": "Científico de datos",
    "cientifico datos": "Científico de datos",
    "coordinador contable": "Coordinador(a) contable",
    "consultor sénior desarrollo organizacional": "Consultor(a) sénior de desarrollo organizacional",
    "gerente operaciones": "Gerente de operaciones",
    "analista administrativo": "Analista administrativo",
    "analista mercadeo": "Analista de mercadeo",
    "analista logística": "Analista de logística",
    "analista comercio exterior": "Analista de comercio exterior",
    "analista recursos humanos": "Analista de recursos humanos",
    "analista datos": "Analista de datos",
    "analista inteligencia negocios": "Analista de inteligencia de negocios",
    "coordinador desarrollo organizacional": "Coordinador(a) de desarrollo organizacional",
    "auxiliar desarrollo organizacional": "Auxiliar de desarrollo organizacional",
    "analista desarrollo organizacional": "Analista de desarrollo organizacional",
    "especialista desarrollo organizacional": "Especialista en desarrollo organizacional",
    "analista gestión talento": "Analista de gestión del talento",
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
    # ── Detectados al revisar el filtro de Nivel de escolaridad ─────────────
    # Casi todos entran por PREFIJO: el título real arrastra el nombre del
    # departamento o del bufete ("Receptionist - Sepulveda Sanchez Accident
    # Lawyers Los Angeles - Bilingual"), y la clave corta lo absorbe.
    "administrative assistant": "Asistente administrativo",
    "administrative associate": "Asistente administrativo",
    "administrative coordinator": "Coordinador(a) administrativo(a)",
    "receptionist": "Recepcionista",
    "data entry clerk": "Auxiliar de digitación",
    "office assistant": "Asistente de oficina",
    "preschool assistant teacher": "Docente asistente de preescolar",
    "preschool teacher assistant": "Docente asistente de preescolar",
    "early childhood assistant teacher": "Docente asistente de primera infancia",
    "early childhood teacher assistant": "Docente asistente de primera infancia",
    "teacher assistant": "Docente asistente",
    "assistant teacher": "Docente asistente",
    "teaching assistant": "Docente asistente",
    "tax services manager": "Gerente de servicios tributarios",
    "tax manager": "Gerente tributario",
    "registered practical nurse": "Enfermero(a) práctico(a)",
    "practical nurse": "Enfermero(a) práctico(a)",
    "nursing assistant": "Auxiliar de enfermería",
    "certified nursing assistant": "Auxiliar de enfermería certificado(a)",
    "physical therapist assistant": "Auxiliar de fisioterapia",
    "medical assistant": "Auxiliar médico",
    "case manager": "Gestor(a) de casos",
    "care manager": "Gestor(a) de cuidados",
    "clinical manager": "Coordinador(a) clínico(a)",
    # ── Auditoría del top 10 por programa (sep 2026) ─────────────────────────
    # Casi todas estas entradas existen para FUSIONAR barras duplicadas: el
    # mismo cargo aparecía dos o tres veces porque el título en español no
    # estaba en el diccionario (y caía al respaldo) mientras su equivalente en
    # inglés sí se traducía. Las claves van sin tildes a propósito: el índice
    # canoniza plegando, así que una sola clave cubre ambas escrituras.
    # Ingenierías
    "ingeniero mecanico": "Ingeniero mecánico",
    "ingeniero quimico": "Ingeniero químico",
    "ingeniero produccion": "Ingeniero de producción",
    "ingeniero electrico": "Ingeniero eléctrico",
    "ingeniero civil": "Ingeniero civil",
    "ingeniero industrial": "Ingeniero industrial",
    "ingeniero sistemas": "Ingeniero de sistemas",
    "ingeniero diseno electrico": "Ingeniero de diseño eléctrico",
    "ingeniero innovacion y desarrollo": "Ingeniero de innovación y desarrollo",
    "mechanical designer engineer": "Ingeniero de diseño mecánico",
    "mechanical design manager engineer": "Ingeniero de diseño mecánico",
    "disenador producto": "Diseñador de producto",
    # Salud
    "jefe enfermeria": "Jefe de enfermería",
    "enfermero jefe": "Jefe de enfermería",
    "clinical nurse coordinator": "Coordinador(a) de enfermería",
    "registered general nurse": "Enfermero(a) registrado(a)",
    "terapeuta fisico fisioterapeuta": "Fisioterapeuta",
    "terapeuta fisico integral": "Fisioterapeuta",
    "fisioterapeuta domiciliario": "Fisioterapeuta domiciliario",
    "locum physician": "Médico (locum)",
    "locum physician do emergency medicine": "Médico de urgencias (locum)",
    "obgyn physician": "Médico ginecobstetra",
    # Comunicación
    "editor video": "Editor de video",
    "editor videos": "Editor de video",
    "digital video content producer editor": "Editor de video",
    "redactor contenidos": "Redactor de contenidos",
    "creador contenido": "Creador de contenido",
    "multiskilled journalist": "Periodista multimedia",
    "multi media journalist": "Periodista multimedia",
    "content strategist writer": "Estratega de contenidos",
    "relaciones publicas": "Relaciones públicas",
    # Negocios y administración
    "jefe servicio cliente": "Jefe de servicio al cliente",
    "coordinador cliente": "Coordinador(a) de servicio al cliente",
    "client success manager": "Gerente de éxito del cliente",
    "financial planning analysis analyst": "Analista de planeación financiera",
    "specialist talent management": "Especialista en gestión del talento",
    "hr ethics compliance officer": "Oficial de cumplimiento",
    # Derecho
    "employment lawyer": "Abogado laboralista",
    "in house lawyer": "Abogado interno",
    "asesor juridico": "Asesor jurídico",
    "abogado litigios": "Abogado litigante",
    # Educación y ciencias sociales
    "early childhood education teacher": "Docente de primera infancia",
    "docente filosofia": "Docente de filosofía",
    "auxiliar pedagogico": "Auxiliar pedagógico",
    "industrial organizational psychologist": "Psicólogo organizacional",
    "psicologo organizacional": "Psicólogo organizacional",
    "analista reclutamiento y seleccion": "Analista de selección",
    "international relations": "Relaciones internacionales",
    # ── Segunda pasada de la auditoría: títulos que subieron al top 10 al
    #    fusionarse los duplicados de la primera ronda ────────────────────────
    "physical therapist": "Fisioterapeuta",
    # Más específicas que "physical therapist"/"nurse": el bucle de prefijo
    # recorre las claves de más palabras a menos, así que estas ganan y el
    # auxiliar no se cuenta como el profesional.
    "physical therapist aide": "Auxiliar de fisioterapia",
    "physical therapy aide": "Auxiliar de fisioterapia",
    "nurse aide": "Auxiliar de enfermería",
    # Plurales de los cargos con entrada propia: la regla general de plural
    # solo actúa en la capa composicional, así que sin estas claves el plural
    # caía en una etiqueta distinta a la del singular ("Physical Therapists"
    # daba "Terapeuta físico" y "Physical Therapist", "Fisioterapeuta").
    "physical therapists": "Fisioterapeuta",
    "physiotherapists": "Fisioterapeuta",
    "registered nurses": "Enfermero(a) registrado(a)",
    "editores video": "Editor de video",
    # ── Plantilla "Physician (MD/DO) - <especialidad> - General/Other" ───────
    # Un solo portal de empleo médico publica así ~200 vacantes. Sin estas
    # claves cada especialidad quedaba en inglés y además partida por ciudad.
    "physician do family practice": "Médico de familia",
    "physician do psychiatry": "Médico psiquiatra",
    "physician do pediatrics": "Médico pediatra",
    "physician do cardiology": "Médico cardiólogo",
    "physician do internal medicine": "Médico internista",
    "physician do radiology": "Médico radiólogo",
    "physician do anesthesiology": "Médico anestesiólogo",
    "physician do surgery": "Médico cirujano",
    "physician do neurology": "Médico neurólogo",
    "physician do urology": "Médico urólogo",
    "physician do gastroenterology": "Médico gastroenterólogo",
    "physician do obstetrics gynecology": "Médico ginecobstetra",
    "physician do endocrinology": "Médico endocrinólogo",
    "physician do rheumatology": "Médico reumatólogo",
    "physician do hematology oncology": "Médico hematólogo y oncólogo",
    # ── Experiencia del cliente / UX ─────────────────────────────────────────
    # 'associate' lo borra normalize_title (es nivel), así que "Customer
    # Experience Associate" llega aquí como "customer experience".
    "customer experience": "Ejecutivo(a) de experiencia del cliente",
    "customer experience manager": "Gerente de experiencia del cliente",
    "customer experience specialist": "Especialista en experiencia del cliente",
    "customer experience agent": "Agente de experiencia del cliente",
    "customer experience lead": "Líder de experiencia del cliente",
    "user experience designer": "Diseñador UX",
    "user experience": "Diseñador UX",
    # ── Cola larga de la recolección nueva ──────────────────────────────────
    "asic design verification engineer": "Ingeniero de verificación de diseño ASIC",
    "application engineer bioprocess mixing": "Ingeniero de aplicaciones de bioprocesos",
    "applications engineering supervisor bioprocessing design": "Ingeniero de aplicaciones de bioprocesos",
    "bioprocess npi engineer": "Ingeniero de bioprocesos",
    "applications sales engineer chemical": "Ingeniero comercial de aplicaciones químicas",
    "practicante relaciones internacionales y estudios politicos": "Practicante de relaciones internacionales y estudios políticos",
    "profesional relaciones internacionales bilingue": "Profesional de relaciones internacionales bilingüe",
    # ── Auditoría tras sumar los mercados de LATAM (sep-2026) ────────────────
    # Inglés que entró con las nuevas fuentes.
    "manufacturing supply chain professional": "Profesional de manufactura y cadena de suministro",
    "export area manager": "Gerente de exportaciones",
    "export control manager": "Gerente de control de exportaciones",
    # Variantes regionales: en Perú y el Cono Sur se dice "planeamiento" donde
    # en Colombia/México se dice "planeación"; es el mismo cargo.
    "analista planeamiento financiero": "Analista de planeación financiera",
    "analista planeamiento": "Analista de planeación",
    "jefe planeamiento": "Jefe de planeación",
    # "Abogado/a Laboral" (Cono Sur) y "abogado laboralista" (Colombia) son el
    # mismo rol: sin esta entrada quedaban en dos barras.
    "abogado laboral": "Abogado laboralista",
    "family practice physician": "Médico de familia",
    "clinical psychologist": "Psicólogo clínico",
    "neuropsychologist": "Neuropsicólogo",
    "preschool pre k teacher": "Docente de preescolar",
    "pre k teacher": "Docente de preescolar",
    "corporate communications": "Comunicaciones corporativas",
    "intern corporate communications": "Practicante de comunicaciones corporativas",
    "electrochemical engineer": "Ingeniero electroquímico",
    "ux writer": "Redactor UX",
    "content designer": "Diseñador de contenido",
    "clinical nurse educator": "Enfermero(a) educador(a)",
    "ingenieros industriales": "Ingeniero industrial",
    "analista servicio y cliente": "Analista de servicio al cliente",
    "creador contenidos videos": "Creador de contenido",
    # ── Respaldos en ESPAÑOL más frecuentes (sep-2026, al automatizar el
    #    filtrado de inglés) ─────────────────────────────────────────────────
    # Títulos en español que ninguna entrada cubría y salían con la
    # preposición comida por `normalize_title` ("Ingeniero inteligencia
    # artificial"). Donde ya existe el equivalente en inglés se usa la MISMA
    # etiqueta para que se fusionen en una barra ('digital marketing' y
    # 'marketing digital' son el mismo perfil).
    # Estas dos SOLO casan por coincidencia exacta (ver _SOLO_EXACTO): como
    # contenido absorberían "Digital Marketing Account Manager" o "Digital
    # Marketing Designer", que son otros cargos y los resuelve la composición.
    "digital marketing": "Profesional de marketing digital",
    "marketing digital": "Profesional de marketing digital",
    "profesional marketing digital": "Profesional de marketing digital",
    "marketing digital comunicacion": "Profesional de marketing digital",
    "coordinador marketing digital": "Coordinador de marketing digital",
    "analista marketing digital": "Analista de marketing digital",
    "especialista marketing digital": "Especialista en marketing digital",
    "responsable marketing digital": "Responsable de marketing digital",
    "ingeniero inteligencia artificial": "Ingeniero de inteligencia artificial",
    "ingeniero software": "Ingeniero de software",
    "analista financiero y planeacion": "Analista de planeación financiera",
    "analista riesgos financieros": "Analista de riesgos financieros",
    "analista riesgos": "Analista de riesgos",
    "analista inversiones": "Analista de inversiones",
    "analista inversiones inmobiliarias": "Analista de inversiones inmobiliarias",
    "investigador campo": "Investigador de campo",
    "abogado contratos": "Abogado de contratos",
    "abogado corporativo": "Abogado corporativo",
    "practicante negocios internacionales": "Practicante de negocios internacionales",
    "profesional negocios internacionales": "Profesional de negocios internacionales",
    "jefe seguridad cadena suministro": "Jefe de seguridad de cadena de suministro",
    "enfermero": "Enfermero(a)",
    "enfermera": "Enfermero(a)",
    # ── Inglés que el detector descartaba con más frecuencia (sep-2026) ──────
    # Rescatados a mano porque son roles reales con volumen (≥3 vacantes). El
    # resto de descartados se puede revisar en GET /tendencias/cargos-descartados.
    "c engineer": "Ingeniero de software (C/C++)",
    "c developer engineer": "Ingeniero de software (C/C++)",
    "net engineer": "Desarrollador .NET",
    "cyber engineer": "Ingeniero de ciberseguridad",
    "flight engineer": "Ingeniero de software de vuelo",
    "graduate engineer structural": "Ingeniero estructural",
    "civil structural forensic engineer": "Ingeniero civil y estructural",
    "tech generalist engineer": "Ingeniero de software",
    "java kotlin engineer": "Desarrollador Java",
    "linux engineer": "Ingeniero Linux",
    "supply chain material analyst": "Analista de cadena de suministro",
    "special education teacher": "Docente de educación especial",
    "early childhood teachers teacher assistants": "Docente de primera infancia",
    "early childhood teachers support teachers": "Docente de primera infancia",
    "preschool classroom teacher": "Docente de preescolar",
    "preschool vpk teacher": "Docente de preescolar",
    "clinical nurse specialist": "Enfermero(a) especialista",
    "physician ob gyn": "Médico ginecobstetra",
    "physician family internal medicine": "Médico de familia",
    "financial planner analyst": "Analista de planeación financiera",
    "financial aid analyst": "Analista de ayuda financiera",
    "bank chef manager": "Chef",
}

# Claves de `CARGOS` que casan ÚNICAMENTE por coincidencia exacta: se dejan
# fuera de los niveles de prefijo y contenido porque, siendo de dos palabras
# genéricas, absorberían cargos distintos que las contienen.
_SOLO_EXACTO: frozenset[str] = frozenset({"digital marketing", "marketing digital"})

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
from typing import Iterable

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
    # Estados de EE.UU. escritos completos. Se añadieron al detectar que las
    # ofertas médicas de tipo "locum" traen el destino en el título ("Locum
    # Physician DO Emergency Medicine In Florida"), lo que partía un mismo
    # cargo en una barra por estado.
    "florida", "texas", "minnesota", "california", "georgia", "virginia",
    "carolina", "ohio", "michigan", "arizona", "nevada", "oregon",
    "washington", "colorado", "kansas", "missouri", "indiana", "kentucky",
    "tennessee", "alabama", "louisiana", "oklahoma", "arkansas",
    "mississippi", "iowa", "nebraska", "utah", "idaho", "montana", "wyoming",
    "dakota", "alaska", "hawaii", "maine", "vermont", "delaware", "maryland",
    "massachusetts", "connecticut", "pennsylvania", "illinois", "wisconsin",
    "sumter", "durham", "wilton", "lincoln",
    # Abreviaturas de lugar que las ofertas colombianas y mexicanas cuelgan al
    # final ("Enfermero UCI Neonatal Rionegro Ant", "Chef Miguel Hidalgo CDMX").
    "ant", "cdmx",
}

# ─────────────────────────────────────────────────────────────────────────────
# Ubicaciones DINÁMICAS: las que se aprenden de los propios datos.
# ─────────────────────────────────────────────────────────────────────────────
# `_UBICACIONES` (arriba) es una lista curada a mano y se queda corta: medido
# sobre las 15.232 vacantes que pasan los filtros de calidad (sep-2026), al
# final del cargo canonizado seguían colándose Huila, Rionegro, Yumbo, Siberia,
# Marmato, Sibaté, Palmira, Dosquebradas, Cota… —municipios y departamentos
# que ninguna lista escrita a mano va a cubrir completa—. La fuente natural
# de esos nombres ya está en la base: `DEPARTAMENTOS` de Tendencias/geografia
# y las ciudades OBSERVADAS en `vacantes_google.city` y `vacantes_linkedin.city`.
# `Tendencias/ubicaciones.py` las lee (una vez, con caché en disco) y las
# registra aquí con `registrar_ubicaciones()`.
#
# POR QUÉ SOLO SE QUITAN EN LOS EXTREMOS Y NO EN CUALQUIER POSICIÓN
# Los nombres aprendidos no son de fiar como palabras sueltas: la columna
# `city` trae valores que también son vocabulario de cargo ("Control" aparece
# 31 veces EN MEDIO de títulos como 'financial control analyst'; también
# "Banco", "Colegio", "Unión", "Mesa" —de La Mesa—, "Meta" —departamento y
# también 'Meta Ads'—, "Santander" —departamento y banco—, "Lima", "Santiago",
# "Madrid"…). Quitarlas donde aparezcan mutilaría cargos legítimos. En cambio,
# las fuentes cuelgan la ubicación casi siempre al FINAL ("Analista de Datos
# Bogotá", "Coordinador Comercial - Medellín", "... Pitalito Huila") y a veces
# al PRINCIPIO ("Lima Norte Asistente de Cooperación", "Gachancipá Analista de
# Comercio Exterior"). Así que las dinámicas se recortan solo por los extremos,
# de forma repetida (primero cae "huila", luego "pitalito"), y nunca se deja el
# título vacío. La lista curada `_UBICACIONES` conserva su comportamiento
# (se quita en cualquier posición): son nombres sin doble sentido.
#
# Además, un puñado de valores de `city` son directamente palabras de cargo y
# NI SIQUIERA al final se pueden quitar ("Analista de Control" termina en
# 'control'): están en `_NUNCA_UBICACION` y `registrar_ubicaciones` los ignora,
# igual que ignora cualquier nombre cuyas palabras estén en el vocabulario del
# propio diccionario de cargos (se calcula, no se adivina).
#
# Los nombres se guardan como TUPLAS de tokens plegados y SIN las palabras
# vacías que `normalize_title` ya elimina ("Valle del Cauca" -> ('valle',
# 'cauca'); "La Estrella" -> ('estrella',)), porque es en esa forma en la que
# llegan a `canonizar_cargo`.
_UBICACIONES_EXTREMO: set[tuple[str, ...]] = set()

# Palabras vacías que `normalize_title` (Adzuna/adzuna_service.py) borra del
# título; hay que borrarlas también del nombre de la ubicación para que casen.
_STOP_TITULO: frozenset[str] = frozenset({
    "de", "del", "la", "las", "los", "el", "en", "y", "and", "para", "por", "con",
})

# Valores de `city` que son vocabulario de cargo, no lugares (observados en los
# datos reales). Nunca se tratan como ubicación, ni al final del título.
_NUNCA_UBICACION: frozenset[str] = frozenset({
    "control", "banco", "colegio", "union", "colina", "leon", "mesa",
    "progreso", "libertad", "paz", "victoria", "remoto", "remote", "virtual",
    "hibrido", "presencial", "colombia",
})

# Ubicaciones que no son ciudad pero llegan en la misma columna (países, "Home
# office"…). Se descartan al registrar: los países ya están en `_UBICACIONES`.
_PAISES_EN_CITY: frozenset[str] = frozenset({
    "colombia", "mexico", "argentina", "chile", "peru", "espana", "spain",
    "estados unidos", "united states",
})


def _vocabulario_cargos() -> set[str]:
    """Palabras que aparecen en el diccionario de cargos (claves y valores).

    Un nombre de ciudad que contenga una de ellas no se puede aprender como
    ubicación sin riesgo de mutilar un cargo legítimo, así que se descarta.
    """
    palabras: set[str] = set()
    for clave, valor in CARGOS.items():
        for token in f"{clave} {valor}".lower().replace("(", " ").replace(")", " ").split():
            palabras.add(_sin_tildes(token))
    return palabras - _STOP_TITULO


def _tokens_ubicacion(nombre: str) -> tuple[str, ...]:
    """'Valle del Cauca (y 3 ubicaciones más)' -> ('valle', 'cauca')."""
    plano = _sin_tildes(nombre.lower())
    plano = re.sub(r"\(.*?\)", " ", plano)          # sufijo de agregación de Google
    plano = re.sub(r"metropolitan area|ciudad$", " ", plano)
    plano = re.sub(r"[^a-z\s]", " ", plano)          # 'D.C.' -> 'd c', 'Nte.' -> 'nte'
    return tuple(t for t in plano.split() if t not in _STOP_TITULO)


def registrar_ubicaciones(nombres: "Iterable[str]") -> int:
    """Aprende nombres de lugar para recortarlos de los EXTREMOS del cargo.

    Devuelve cuántos nombres nuevos se aceptaron. Descarta: vacíos, países,
    los de `_NUNCA_UBICACION`, los que contienen vocabulario de cargo y los de
    una sola letra. Reconstruye el índice de `CARGOS` porque las claves se
    indexan ya canonizadas y la canonización acaba de cambiar.
    """
    vocabulario = _vocabulario_cargos()
    nuevos = 0
    for nombre in nombres:
        if not nombre:
            continue
        tokens = _tokens_ubicacion(nombre)
        if not tokens or " ".join(tokens) in _PAISES_EN_CITY:
            continue
        if any(t in _NUNCA_UBICACION or t in vocabulario or len(t) < 2 for t in tokens):
            continue
        if tokens not in _UBICACIONES_EXTREMO:
            _UBICACIONES_EXTREMO.add(tokens)
            nuevos += 1
    if nuevos:
        _reindexar_cargos()
    return nuevos


def ubicaciones_registradas() -> int:
    """Cuántas ubicaciones dinámicas hay cargadas (para diagnósticos)."""
    return len(_UBICACIONES_EXTREMO)


_ubicaciones_intentadas = False


def _asegurar_ubicaciones() -> None:
    """Carga las ubicaciones observadas la PRIMERA vez que se traduce un cargo.

    Se hace perezosamente y no al importar: este módulo lo importa
    Adzuna/adzuna_service.py ANTES de crear el cliente de Supabase, así que
    leer la base aquí arriba sería un import circular. Se intenta UNA sola
    vez por proceso; si falla (sin .env, sin red), se sigue con la lista
    curada y se avisa por consola —nunca se rompe la traducción por esto—.
    """
    global _ubicaciones_intentadas
    if _ubicaciones_intentadas:
        return
    _ubicaciones_intentadas = True
    try:
        from Tendencias.ubicaciones import cargar_ubicaciones

        cargar_ubicaciones()
    except Exception as e:  # pragma: no cover - depende del entorno
        print(f"   ⚠ Ubicaciones observadas no disponibles ({e}); se usa solo la lista curada.")


def _recortar_extremos(planos: list[str], tokens: list[str]) -> tuple[list[str], list[str]]:
    """Quita ubicaciones dinámicas del final y del principio, repetidamente.

    `planos` es la versión plegada (con la que se compara) y `tokens` la que
    se conserva (con o sin tildes según `plegar`); van en paralelo. Nunca
    devuelve una lista vacía: un título que fuera solo ubicación se deja tal
    cual, que ya se descartará aguas abajo por otras reglas.
    """
    if not _UBICACIONES_EXTREMO:
        return planos, tokens
    max_len = 3
    cambio = True
    while cambio and len(planos) > 1:
        cambio = False
        for n in range(min(max_len, len(planos) - 1), 0, -1):
            if tuple(planos[-n:]) in _UBICACIONES_EXTREMO:
                planos, tokens = planos[:-n], tokens[:-n]
                cambio = True
                break
        if cambio or len(planos) <= 1:
            continue
        for n in range(min(max_len, len(planos) - 1), 0, -1):
            if tuple(planos[:n]) in _UBICACIONES_EXTREMO:
                planos, tokens = planos[n:], tokens[n:]
                cambio = True
                break
    return planos, tokens

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
    # 'full' suelto ("Full Physiotherapist") es un resto de "full time"; es
    # seguro porque los bigramas protegidos ("full stack") se blindan ANTES
    # del filtrado token a token. 'in' aparece como preposición en los
    # títulos en inglés que traen destino ("... In Florida").
    "full", "in", "to",
    # Jerga del NHS británico, que publica el grado salarial en el título
    # ("Band 6 Locum Outpatient MSK Physiotherapist").
    "band", "msk", "outpatient", "inpatient",
    # Avisos de banco de talento ("Customer Experience Associate - Future
    # Opportunities"): no son el cargo, son la convocatoria.
    "future", "opportunities",
    # Restos del salario anunciado en el título ("... $90,000 to $120,000 per
    # year"): el importe ya lo quita el filtro de números.
    "per", "year", "annum", "hour", "hourly", "salary", "salario",
    # Puntos cardinales que acompañan a una zona ("Lima Norte", "Zona Sur",
    # "Región Occidente"): al recortar la ciudad quedaban sueltos.
    "norte", "sur", "oriente", "occidente",
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
    # 'experience' está en el ruido para descartar "5 years experience", pero
    # en estas dos es el NOMBRE del cargo: sin blindarlas, "Customer
    # Experience Associate" quedaba en "Customer" (93 vacantes afectadas).
    "customer experience": "customerexperience",
    "user experience": "userexperience",
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


def canonizar_cargo(titulo_normalizado: str, plegar: bool = True) -> str:
    """Quita del título normalizado todo lo que no es el nombre del cargo.

    Opera sobre la salida de `normalize_title` (Adzuna/adzuna_service.py), no
    sobre el título crudo. Va aquí y no dentro de `normalize_title` a
    propósito: la salida de aquella función es el FORMATO DE CLAVE de las 275
    entradas curadas de `CARGOS` y de cualquier otro consumidor, así que
    cambiarla invalidaría en silencio ese trabajo. Esta limpieza es del
    momento de traducir, no de normalizar.

    `plegar=True` (por defecto) devuelve el texto SIN TILDES: es la forma con
    la que se COMPARA contra el diccionario, para que "Ingeniería" y
    "Ingenieria" lleguen a la misma entrada.

    `plegar=False` conserva tildes y ñ: es la forma que se MUESTRA cuando
    ninguna entrada del diccionario aplica. Sin esta distinción, el respaldo
    imprimía el texto plegado y salían nombres mutilados —"Ingeniero
    mecanico", "Disenador producto", "Docente filosofia"— que además quedaban
    como una barra SEPARADA de su equivalente ya traducido del inglés
    ("Ingeniero mecánico"), partiendo en dos el mismo cargo.
    """
    if not titulo_normalizado:
        return ""

    texto = titulo_normalizado.lower()

    # Blindar/eliminar bigramas antes del filtrado token a token. Todos son
    # ASCII, así que casan igual sobre el texto con tildes.
    for bigrama, reemplazo in _BIGRAMAS_PROTEGIDOS.items():
        texto = texto.replace(bigrama, f" {reemplazo} " if reemplazo else " ")

    # El descarte SIEMPRE se decide sobre la forma plegada (los conjuntos de
    # ruido están escritos sin tildes: 'bogota', 'medellin'), pero lo que se
    # conserva depende de `plegar`. Se llevan las dos listas en paralelo porque
    # el recorte de ubicaciones dinámicas compara sobre la plegada.
    tokens: list[str] = []
    planos: list[str] = []
    for token in texto.split():
        plano = _sin_tildes(token)
        if plano in _RUIDO_CARGO:
            continue
        # Números sueltos y códigos de oferta ("1626430055", "20", "id71005").
        if re.fullmatch(r"\d+", plano) or re.fullmatch(r"[a-z]{0,3}\d{2,}[a-z\d]*", plano):
            continue
        tokens.append(plano if plegar else token)
        planos.append(plano)
    # Ubicaciones aprendidas de los datos: solo por los extremos (ver el bloque
    # de `_UBICACIONES_EXTREMO` para el porqué).
    planos, tokens = _recortar_extremos(planos, tokens)
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
    "physiotherapist": "Fisioterapeuta",
    # Añadidos al automatizar el filtrado de inglés: "Digital Marketing
    # Professional / Internship" caían al inglés crudo por falta de núcleo.
    "professional": "Profesional", "internship": "Practicante", "intern": "Practicante",
    "strategist": "Estratega", "copywriter": "Redactor publicitario",
    "instructor": "Instructor", "trainer": "Formador", "nutritionist": "Nutricionista",
    "optometrist": "Optómetra", "radiographer": "Radiólogo", "midwife": "Partera",
    "sonographer": "Ecografista", "paramedic": "Paramédico", "dietitian": "Nutricionista",
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
    # Las formas de DOS palabras son necesarias además de las pegadas:
    # `canonizar_cargo` restaura los bigramas protegidos antes de devolver, así
    # que a la composición le llega "front end engineer", no "frontend
    # engineer", y sin esta entrada no encontraba modificador.
    "front end": "frontend", "back end": "backend",
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
    "english": "de inglés", "music": "de música", "art": "de arte",
    "web": "web", "mobile": "móvil", "java": "Java",
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
    # ── Añadidos al automatizar el filtrado de inglés (sep-2026) ─────────────
    # Salen del top de títulos que caían al respaldo en inglés medido sobre
    # las 15.232 vacantes reales que pasan los filtros: la composición no
    # encontraba modificador y el título se pintaba crudo. Los de dos
    # palabras se listan porque la composición ahora traduce TODOS los
    # modificadores de un título (ver `_componer_cargo`) y sin la forma
    # compuesta "supply chain analyst" caía por 'chain'.
    "supply chain": "de cadena de suministro", "digital marketing": "de marketing digital",
    "business intelligence": "de inteligencia de negocios",
    "artificial intelligence": "de inteligencia artificial",
    "site reliability": "de confiabilidad de sitio", "real estate": "inmobiliario",
    "social media": "de redes sociales", "customer service": "de servicio al cliente",
    "customer success": "de éxito del cliente", "data science": "de ciencia de datos",
    "cyber security": "de ciberseguridad", "information security": "de seguridad de la información",
    "project management": "de gestión de proyectos", "talent acquisition": "de atracción de talento",
    "foreign trade": "de comercio exterior", "international trade": "de comercio internacional",
    "international business": "de negocios internacionales",
    "financial planning": "de planeación financiera", "internal audit": "de auditoría interna",
    "market research": "de investigación de mercados", "computer vision": "de visión por computador",
    "generative ai": "de IA generativa", "continuous improvement": "de mejora continua",
    "quality control": "de control de calidad", "accounts payable": "de cuentas por pagar",
    "accounts receivable": "de cuentas por cobrar", "occupational health": "de salud ocupacional",
    "clinical research": "de investigación clínica", "physical education": "de educación física",
    "research": "de investigación", "robotics": "de robótica", "analytics": "de analítica",
    "infrastructure": "de infraestructura", "android": "Android", "ios": "iOS",
    "ui": "UI", "ux": "UX", "graphics": "de gráficos", "cybersecurity": "de ciberseguridad",
    "compliance": "de cumplimiento", "procurement": "de compras", "purchasing": "de compras",
    "inventory": "de inventarios", "commercial": "comercial", "regional": "regional",
    "national": "nacional", "international": "internacional", "global": "global",
    "strategic": "estratégico", "strategy": "de estrategia", "innovation": "de innovación",
    "sustainability": "de sostenibilidad", "safety": "de seguridad", "health": "de salud",
    "fintech": "fintech", "payments": "de pagos", "treasury": "de tesorería",
    "pricing": "de precios", "growth": "de crecimiento", "brand": "de marca",
    "media": "de medios", "video": "de video", "multimedia": "multimedia", "graphic": "gráfico",
    "transportation": "de transporte", "transport": "de transporte", "fleet": "de flota",
    "hydraulic": "hidráulico", "wastewater": "de aguas residuales", "plant": "de planta",
    "reliability": "de confiabilidad", "controls": "de control", "control": "de control",
    "instrumentation": "de instrumentación", "materials": "de materiales",
    "packaging": "de empaques", "food": "de alimentos", "pharmaceutical": "farmacéutico",
    "biotechnology": "de biotecnología", "laboratory": "de laboratorio", "lab": "de laboratorio",
    "validation": "de validación", "regulatory": "regulatorio", "nursing": "de enfermería",
    "school": "escolar", "bilingual": "bilingüe", "academic": "académico",
    "employment": "laboral", "labor": "laboral", "immigration": "de inmigración",
    "litigation": "de litigios", "contracts": "de contratos", "contract": "de contratos",
    "family": "de familia", "criminal": "penal", "government": "gubernamental",
    "intelligence": "de inteligencia", "defense": "de defensa", "economics": "de economía",
    "economic": "económico", "portfolio": "de portafolio", "budget": "de presupuesto",
    "cost": "de costos", "payroll": "de nómina", "benefits": "de beneficios",
    "compensation": "de compensación", "learning": "de formación",
    "organizational": "organizacional", "culture": "de cultura", "kitchen": "de cocina",
    "culinary": "culinario", "pastry": "pastelero", "restaurant": "de restaurante",
    "hotel": "de hotel", "events": "de eventos", "event": "de eventos", "tourism": "de turismo",
    "travel": "de viajes", "import": "de importaciones", "export": "de exportaciones",
    "customs": "de aduanas", "trade": "de comercio", "freight": "de carga",
    "sourcing": "de abastecimiento", "retail": "de retail", "store": "de tienda",
    "ecommerce": "de e-commerce", "seo": "SEO", "crm": "CRM", "editorial": "editorial",
    "press": "de prensa", "photography": "de fotografía", "animation": "de animación",
    "sound": "de sonido", "audio": "de audio", "creative": "creativo", "visual": "visual",
    "cad": "CAD", "bim": "BIM", "lean": "lean", "planning": "de planeación",
    "hse": "HSE", "renewable": "de energías renovables", "solar": "solar",
    "mining": "de minería", "petroleum": "de petróleo", "textile": "textil",
    "automotive": "automotriz", "aviation": "de aviación", "naval": "naval",
    "program": "de programa", "platform": "de plataforma", "solutions": "de soluciones",
    "solution": "de soluciones", "integration": "de integración",
    "implementation": "de implementación", "application": "de aplicaciones",
    "applications": "de aplicaciones", "embedded": "de sistemas embebidos",
    "firmware": "de firmware", "hardware": "de hardware", "wireless": "inalámbrico",
    "iot": "IoT", "mlops": "MLOps", "ml": "de machine learning", "nlp": "de NLP",
    "database": "de bases de datos", "sql": "SQL", "etl": "ETL", "bi": "de inteligencia de negocios",
    "reporting": "de reportes", "statistics": "de estadística", "statistical": "estadístico",
    "actuarial": "actuarial", "quantitative": "cuantitativo", "fraud": "de fraude",
    "collections": "de cobranzas", "insurance": "de seguros", "claims": "de reclamaciones",
    "billing": "de facturación", "founding": "fundador", "principal": "principal",
    "technical": "técnico", "tech": "técnico", "it": "de TI", "operational": "operativo",
    "administrative": "administrativo", "executive": "ejecutivo", "general": "general",
    "assistant": "asistente", "associate": "asociado", "regional sales": "de ventas regional",
    "inside sales": "de ventas internas", "key account": "de cuentas clave",
    "account": "de cuentas", "partner": "de alianzas", "channel": "de canal",
    "revenue": "de ingresos", "loan": "de crédito", "mortgage": "hipotecario",
    "wealth": "de patrimonio", "equity": "de renta variable", "capital": "de capital",
    "mergers acquisitions": "de fusiones y adquisiciones", "corporate finance": "de finanzas corporativas",
    "emergency": "de urgencias", "psychiatric": "psiquiátrico", "oncology": "de oncología",
    "rehabilitation": "de rehabilitación", "nutrition": "de nutrición",
    "occupational": "ocupacional", "speech": "del habla", "respiratory": "respiratorio",
    "dental": "dental", "veterinary": "veterinario", "hospice": "de cuidados paliativos",
    "home health": "domiciliario", "home care": "domiciliario", "travel nurse": "itinerante",
    "ux ui": "UX/UI", "ui ux": "UX/UI",
}

# Modificadores de varias palabras, del más largo al más corto: "early
# childhood teacher" debe ganarle a "childhood".
_MODIFICADORES_COMPUESTOS = sorted(
    (m for m in _MODIFICADORES if " " in m),
    key=lambda m: -len(m.split()),
)

# Profesiones cuyo nombre A SECAS ya es un cargo completo y sin ambigüedad.
# Solo para estas se acepta componer sin modificador conocido: da igual cuánta
# jerga arrastre el título ("Band 6 Locum Outpatient MSK Physiotherapist
# Lincoln"), sigue siendo un fisioterapeuta.
#
# Se dejan FUERA a propósito las genéricas —engineer, analyst, manager,
# developer, specialist, teacher…—: ahí el modificador ES el cargo, y quedarse
# con "Analista" a secas fusionaría 'investment banking analyst' con 'policy
# analyst' en una sola barra sin sentido.
_NUCLEOS_AUTONOMOS: frozenset[str] = frozenset({
    "physiotherapist", "nurse", "physician", "lawyer", "attorney",
    "psychologist", "journalist", "chef", "accountant", "architect",
    "dentist", "veterinarian", "pharmacist", "surgeon", "economist",
    "translator",
})


def _segmentar_modificadores(resto: list[str]) -> list[str] | None:
    """Parte los tokens previos al núcleo en modificadores conocidos.

    Va de derecha a izquierda (el modificador pegado al núcleo primero) y
    prueba antes las formas compuestas ("supply chain") que las sueltas.
    Devuelve la lista de traducciones en ese mismo orden (la más cercana al
    núcleo primero), o None si algún tramo no se reconoce: con un tramo
    desconocido no se compone nada, porque adivinar produce agrupaciones
    falsas.
    """
    salida: list[str] = []
    i = len(resto)
    while i > 0:
        for n in (3, 2, 1):
            if i - n < 0:
                continue
            frase = " ".join(resto[i - n:i])
            if frase in _MODIFICADORES:
                salida.append(_MODIFICADORES[frase])
                i -= n
                break
        else:
            return None
    return salida


def _componer_cargo(canonico: str) -> str | None:
    """'civil engineer' -> 'Ingeniero civil'. None si no se puede componer.

    Devuelve None (en vez de solo el núcleo) cuando algún modificador es
    desconocido: quedarse con "Analista" a secas fusionaría en una sola barra
    cargos tan distintos como 'investment banking analyst' y 'policy analyst'.
    Perder cobertura es preferible a inventar una agrupación falsa.

    COMPOSICIÓN COMPLETA (sep-2026). Antes solo se traducía el modificador
    pegado al núcleo y el resto se perdía ('ai infrastructure engineer' ->
    "Ingeniero de infraestructura", sin la IA) o, si ese único modificador
    no se conocía, el título entero caía al inglés crudo. Ahora se exige
    reconocer TODOS los modificadores y se traducen todos, en el orden del
    español (el más cercano al núcleo va primero):

        ai infrastructure engineer -> Ingeniero de infraestructura de IA
        digital marketing analyst  -> Analista de marketing digital

    Regla de orden, deliberadamente conservadora: un modificador ADJETIVO
    (el que no empieza por "de ", p. ej. 'financiero', 'clínico') solo se
    acepta si está pegado al núcleo, porque en español se coloca junto al
    sustantivo que califica y a distancia ya no se sabe cuál es ('financial
    plant analyst' puede ser un analista financiero de planta o un analista
    de planta financiera). Los modificadores que sí son sintagmas "de X" se
    encadenan sin ambigüedad. Si la regla no se cumple, se devuelve None y el
    título sigue su camino (detección de inglés, ver `traducir_cargo`).
    """
    tokens = canonico.split()
    if not tokens:
        return None

    # El núcleo puede venir en plural ("Physical Therapists", "Ingenieros
    # Industriales", "Editores de Video"): se prueba el singular antes de
    # rendirse. Es seguro porque solo acierta si el singular resultante es un
    # núcleo conocido.
    nucleo = tokens[-1]
    if nucleo not in _NUCLEOS:
        for sufijo in ("es", "s"):
            if nucleo.endswith(sufijo) and nucleo[: -len(sufijo)] in _NUCLEOS:
                nucleo = nucleo[: -len(sufijo)]
                break

    base = _NUCLEOS.get(nucleo)
    if not base:
        # Plantilla médica "Physician - OB/GYN", "Physician - ESA", "Nurse ICU":
        # el núcleo va PRIMERO y lo que sigue es la especialidad o la unidad.
        # Solo se acepta para profesiones autónomas y si ningún otro token es
        # un núcleo (si lo fuera, el cargo real sería ese otro).
        primero = tokens[0]
        if primero in _NUCLEOS_AUTONOMOS and not any(t in _NUCLEOS for t in tokens[1:]):
            return _NUCLEOS[primero]
        return None

    resto = tokens[:-1]
    if not resto:
        # Núcleo a secas: solo si la profesión es autónoma (ver _NUCLEOS_AUTONOMOS).
        return base if nucleo in _NUCLEOS_AUTONOMOS else None

    # 1) Composición completa, con dos condiciones: como mucho DOS sintagmas
    #    (con tres, el resultado se vuelve ilegible: 'Ingeniero de integración
    #    de IA de analítica') y ningún adjetivo lejos del núcleo.
    modificadores = _segmentar_modificadores(resto)
    if modificadores and len(modificadores) <= 2 and all(
        pos == 0 or mod.startswith(("de ", "del ")) for pos, mod in enumerate(modificadores)
    ):
        return " ".join([base, *modificadores])

    # 2) Comportamiento anterior, como respaldo: solo el modificador pegado al
    #    núcleo (primero las formas compuestas, "mental health nurse"). Es lo
    #    que ya traducía bien 'Supervisor, Software Engineering' -> 'Ingeniero
    #    de software' y 'Toddler and Preschool Teachers' -> 'Docente de
    #    preescolar', y no se quiere perder por exigir más.
    resto_txt = " ".join(resto)
    for compuesto in _MODIFICADORES_COMPUESTOS:
        if resto_txt.endswith(compuesto):
            return f"{base} {_MODIFICADORES[compuesto]}"
    modificador = _MODIFICADORES.get(resto[-1])
    if modificador:
        return f"{base} {modificador}"
    # Sin modificador conocido: solo se acepta el núcleo a secas si la
    # profesión es autónoma (un 'fisioterapeuta' lo sigue siendo por mucha
    # jerga que arrastre el título).
    return base if nucleo in _NUCLEOS_AUTONOMOS else None


# Índice de `CARGOS` con las claves ya canonizadas, para que el match ignore
# tildes y ruido igual que lo hace el título entrante. Se construye al importar
# y se RECONSTRUYE cuando se registran ubicaciones dinámicas (la canonización
# de las claves puede cambiar con ellas). `setdefault` conserva la primera de
# dos claves que colapsen a la misma forma canónica (el orden del dict es el de
# escritura, así que gana la entrada declarada antes).
_INDICE_CARGOS: dict[str, str] = {}
# Ordenadas de más palabras a menos: el match más específico debe ganar.
_CLAVES_POR_LONGITUD: list[str] = []


def _reindexar_cargos() -> None:
    _INDICE_CARGOS.clear()
    for _clave, _valor in CARGOS.items():
        _INDICE_CARGOS.setdefault(canonizar_cargo(_clave) or _sin_tildes(_clave), _valor)
    # Las de `_SOLO_EXACTO` no participan en prefijo/contenido.
    _CLAVES_POR_LONGITUD[:] = sorted(
        (k for k in _INDICE_CARGOS if k not in _SOLO_EXACTO), key=lambda k: -len(k.split())
    )


_reindexar_cargos()


# ═════════════════════════════════════════════════════════════════════════════
# DETECCIÓN AUTOMÁTICA DE TÍTULOS EN INGLÉS
# ═════════════════════════════════════════════════════════════════════════════
# Tras la cascada (exacto → prefijo → contenido → composición), lo que no
# encajaba se devolvía tal cual: medido sobre las 15.232 vacantes que pasan los
# filtros de calidad (sep-2026), 3.153 caían a ese respaldo (2.526 títulos
# distintos) y la mayoría eran inglés crudo ('Applied ai solution engineer',
# 'Area manager operations', 'Software engineering coach genai llms'…) que se
# pintaba en las gráficas como si fuera un cargo más. Curar 2.500 títulos a
# mano no escala y además cada recolección trae otros nuevos.
#
# La regla, en dos pasos:
#   1. Si el título canonizado PARECE INGLÉS y ningún nivel pudo traducirlo, se
#      DESCARTA de la dimensión 'cargo' (devuelve None). La vacante sigue
#      contando en el total, en su sector y en su programa; solo deja de
#      producir una barra con etiqueta en inglés. Quien quiera rescatarlos ve
#      la lista en `demanda_actual.cargos_descartados()` y añade la entrada a
#      `CARGOS`, que es el mecanismo curado que ya existía.
#   2. Si parece ESPAÑOL, se conserva el respaldo de siempre (con tildes).
#
# El detector es una heurística por vocabulario y sufijos, sin librerías: en
# títulos de 2-5 palabras un clasificador estadístico no aporta y sí pesa. Se
# puntúan señales de cada idioma y gana la mayoría; los empates y los títulos
# sin señal (marcas, siglas, 'chef') NO se consideran inglés — el costo de un
# falso positivo (perder un cargo en español) es mayor que el de un falso
# negativo (dejar pasar uno en inglés, que es el statu quo).
# ═════════════════════════════════════════════════════════════════════════════

# Vocabulario frecuente en títulos de cargo EN ESPAÑOL (sin tildes: se compara
# sobre la forma plegada). Los anglicismos asentados en español ('marketing',
# 'community manager', 'software') NO están en ninguna de las dos listas: no
# discriminan idioma.
_LEXICO_ES: frozenset[str] = frozenset({
    "auxiliar", "jefe", "jefa", "gerente", "coordinador", "coordinadora",
    "analista", "asesor", "asesora", "ingeniero", "ingeniera", "abogado",
    "abogada", "medico", "medica", "enfermero", "enfermera", "docente",
    "profesor", "profesora", "director", "directora", "especialista", "tecnico",
    "tecnica", "tecnologo", "operario", "operaria", "practicante", "aprendiz",
    "ejecutivo", "ejecutiva", "vendedor", "vendedora", "consultor", "consultora",
    "desarrollador", "desarrolladora", "disenador", "disenadora", "lider",
    "supervisor", "supervisora", "administrador", "administradora", "contador",
    "contadora", "psicologo", "psicologa", "fisioterapeuta", "periodista",
    "redactor", "redactora", "investigador", "investigadora", "cientifico",
    "cientifica", "profesional", "residente", "encargado", "encargada",
    "responsable", "gestor", "gestora", "asistente", "secretaria", "secretario",
    "recepcionista", "cajero", "cajera", "mesero", "mesera", "cocinero",
    "cocinera", "conductor", "conductora", "mecanico", "electricista",
    "comercial", "ventas", "mercadeo", "contable", "financiero", "financiera",
    "riesgos", "inversiones", "negocios", "internacionales", "comercio",
    "exterior", "logistica", "calidad", "produccion", "mantenimiento", "procesos",
    "proyectos", "datos", "sistemas", "recursos", "humanos", "talento",
    "seleccion", "servicio", "cliente", "clientes", "atencion", "apoyo",
    "gestion", "zona", "planta", "obra", "nomina", "tesoreria", "cartera",
    "compras", "abastecimiento", "bodega", "almacen", "operaciones", "cocina",
    "enfermeria", "salud", "educacion", "infantil", "preescolar", "primaria",
    "juridico", "juridica", "laboral", "laboralista", "penal", "civil",
    "empresas", "empresa", "sucursal", "oficina", "campo", "area", "region",
    "nacional", "regional", "senior", "junior", "bilingue", "medio", "tiempo",
    "publicas", "publico", "publica", "politicas", "relaciones", "comunicaciones",
    "comunicacion", "contenido", "contenidos", "redes", "sociales", "digital",
    "mercado", "mercados", "economia", "economista", "estadistico", "estadistica",
    "quimico", "quimica", "industrial", "ambiental", "electrico", "electrica",
    "electronico", "biomedico", "clinico", "clinica", "hospitalario", "urgencias",
    "farmaceutico", "odontologo", "veterinario", "nutricionista", "terapeuta",
    "psicopedagogo", "trabajador", "trabajadora", "social", "educador", "educadora",
    "pedagogico", "pedagogica", "bienestar", "seguridad", "vigilante",
    "coordinacion", "direccion", "gerencia", "subgerente", "vicepresidente",
    "presidente", "socio", "socia", "aliado", "emprendimiento", "innovacion",
})

# Vocabulario frecuente en títulos EN INGLÉS. Se excluyen a propósito las
# palabras que se escriben igual en español ('director', 'senior', 'civil',
# 'industrial', 'general', 'social', 'hotel') y los anglicismos que un título
# en español usa con toda naturalidad ('marketing', 'digital', 'software',
# 'community manager'): ninguna discrimina idioma. Medido: con 'marketing' y
# 'digital' en esta lista, "Coordinador de marketing digital" se clasificaba
# como inglés y se descartaba.
_LEXICO_EN: frozenset[str] = frozenset({
    "manager", "engineer", "engineering", "analyst", "developer", "specialist",
    "assistant", "nurse", "officer", "lead", "head", "coordinator", "consultant",
    "designer", "scientist", "technician", "architect", "accountant", "therapist",
    "teacher", "teachers", "lawyer", "attorney", "physician", "business",
    "operations", "customer", "service", "services", "support", "account",
    "accounts", "executive", "representative", "advisor", "administrator",
    "clerk", "driver", "worker", "intern", "trainee", "planner", "buyer",
    "recruiter", "partner", "agent", "sales", "of", "for", "with", "the", "at",
    "on", "by", "from", "all", "new", "time", "hybrid", "staff", "team",
    "member", "leader", "leadership", "strategy", "strategist", "growth",
    "product", "project", "program", "quality", "safety", "health", "care",
    "school", "student", "students", "education", "research", "researcher",
    "science", "data", "cloud", "security", "network", "systems", "system",
    "mobile", "field", "site", "plant", "warehouse",
    "store", "retail", "kitchen", "cook", "server", "pastry", "bakery",
    "hospitality", "restaurant", "front", "office", "desk", "reception",
    "receptionist", "cashier", "delivery", "shift", "night", "weekend",
    "part", "full", "entry", "level", "graduate", "professional", "professor",
    "faculty", "adjunct", "lecturer", "instructor", "tutor", "counselor",
    "psychologist", "public", "policy", "affairs",
    "relations", "communications", "content", "writer", "editor", "journalist",
    "producer", "creative", "brand",
    "finance", "financial", "investment", "banking", "bank", "credit", "risk",
    "audit", "tax", "accounting", "payroll", "treasury", "legal", "counsel",
    "compliance", "paralegal", "human", "resources", "talent", "acquisition",
    "recruitment", "recruiting", "training", "learning", "development",
    "organizational", "supply", "chain", "logistics", "procurement",
    "purchasing", "inventory", "transportation", "fleet", "manufacturing",
    "production", "maintenance", "reliability", "automation", "controls",
    "process", "chemical", "mechanical", "electrical", "structural",
    "environmental", "energy", "water", "construction", "estimator", "surveyor",
    "inspector", "medical", "clinical", "registered", "practical", "licensed",
    "certified", "dental", "veterinary", "pharmacy", "pharmacist", "therapy",
    "physical", "occupational", "speech", "behavioral", "mental", "primary",
    "urgent", "emergency", "surgical", "pediatric", "oncology", "hospice",
    "home", "associate", "chief", "vice",
    "president", "deputy", "national",
    "international", "global", "corporate", "enterprise", "commercial",
    "technical", "tech", "it", "ai", "machine", "deep", "computer",
    "vision", "language", "model", "models", "platform", "infrastructure",
    "applications", "application", "integration", "implementation", "solutions",
    "solution", "architecture", "database", "analytics", "insights",
    "intelligence", "reporting", "statistics", "quantitative", "actuarial",
    "and", "or", "to", "in", "an", "us", "uk",
})

# Anglicismos que un título en español usa tal cual: no puntúan para ningún
# idioma, ni por léxico ni por sufijo ('marketing' termina en '-ing').
_NEUTROS: frozenset[str] = frozenset({
    "marketing", "digital", "software", "hardware", "community", "manager",
    "senior", "junior", "staff", "chef", "sous", "trade", "fintech", "startup",
    "online", "ecommerce", "e", "commerce", "retail", "coaching", "coach",
    "branding", "trainee", "freelance", "call", "center", "contact", "media",
    "social", "civil", "industrial", "general", "regional", "hotel", "director",
    "supervisor", "principal", "a", "o", "y",
})
# 'community manager' y 'trainee' están arriba a la vez que en _LEXICO_EN:
# `_NEUTROS` se evalúa primero y gana, así que en la práctica no puntúan.

# Sufijos que casi solo existen en un idioma. Se aplican a tokens de 5+ letras
# para no disparar con siglas. 'tion' vs 'cion': en español la terminación es
# '-ción' (plegada, '-cion'), así que 'tion' es inglés seguro. NO están '-er'
# ni '-or': 'coordinador', 'director', 'asesor', 'gestor', 'líder' los
# comparten y hacían pasar por inglés títulos españoles.
_SUFIJOS_EN = ("tion", "ing", "ment", "ness", "ship", "ist", "ical", "ity", "ty")
_SUFIJOS_ES = ("cion", "dor", "dora", "ista", "ero", "era", "ario", "aria",
               "ologo", "ologa", "ologia", "encia", "ancia", "idad", "ico", "ica",
               "ivo", "iva", "ente", "ante", "ador", "adora", "edor", "edora")


def _parece_ingles(canonico: str) -> bool:
    """¿El título canonizado (plegado, sin ruido) está en inglés?

    Puntúa señales de cada idioma token a token: pertenencia al léxico y
    sufijos característicos. Un token con tilde o eñe en el original no se
    ve aquí (llega plegado), así que la señal española se apoya en el léxico y
    en sufijos como '-cion', '-dor', '-ista'. Devuelve True solo con MAYORÍA
    de señales inglesas: los empates y la ausencia de señal se tratan como
    español para no descartar cargos legítimos.
    """
    en = es = 0
    for token in canonico.split():
        if token in _NEUTROS:
            continue
        if token in _LEXICO_EN:
            en += 1
        if token in _LEXICO_ES:
            es += 1
        if len(token) >= 5:
            if token.endswith(_SUFIJOS_EN):
                en += 1
            if token.endswith(_SUFIJOS_ES):
                es += 1
    return en > es and en >= 1


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
      4. COMPOSICIÓN — núcleo + modificadores: 'ai infrastructure engineer' ->
                      'Ingeniero de infraestructura de IA'.

    Si nada aplica y el título PARECE INGLÉS, devuelve None: el cargo se
    descarta de la dimensión (ver el bloque "DETECCIÓN AUTOMÁTICA DE TÍTULOS EN
    INGLÉS"). Si parece español, devuelve el título ya CANONIZADO (sin ciudad,
    sin código de oferta) con la inicial en mayúscula.

    Antes de todo esto se cargan, una sola vez, las ubicaciones observadas en
    la base (ver `_asegurar_ubicaciones`), que la canonización recorta de los
    extremos del título.
    """
    if titulo_normalizado is None:
        return None

    _asegurar_ubicaciones()

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

    if _parece_ingles(canonico):
        return None

    # Respaldo: se muestra la forma SIN PLEGAR (con tildes y ñ). Ver la nota de
    # `canonizar_cargo` sobre por qué no se imprime `canonico`.
    visible = canonizar_cargo(titulo_normalizado, plegar=False) or canonico
    return visible[0].upper() + visible[1:]


def es_cargo_en_ingles(titulo_normalizado: str | None) -> bool:
    """True si el título cae al respaldo Y parece inglés (lo que `traducir_cargo`
    descarta). Sirve para listar los descartados y curarlos en `CARGOS`."""
    if not titulo_normalizado:
        return False
    canonico = canonizar_cargo(titulo_normalizado)
    return bool(canonico) and traducir_cargo(titulo_normalizado) is None


def traducir_tecnologia(nombre: str | None) -> str | None:
    """Nombre de tecnología O*NET a forma limpia. Regla extra: quita ' software'."""
    if nombre is None:
        return None
    if nombre in TECNOLOGIAS:
        return TECNOLOGIAS[nombre]
    if nombre.endswith(" software"):
        return nombre[: -len(" software")]
    return nombre
