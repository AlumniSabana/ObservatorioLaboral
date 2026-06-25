"""
Servicio de O*NET para la sección "Competencias y habilidades apetecidas".

O*NET (U.S. Dept. of Labor) es una base de datos de ~900 ocupaciones con sus
habilidades, conocimientos y tecnologías. Aquí mapeamos cada programa de La Sabana
a una ocupación O*NET y consultamos su API (gratuita, requiere registro) para
mostrar las competencias clave y las tecnologías típicas de esa ocupación.

⚠️ Sobre el dato: O*NET describe el mercado de EE.UU. y es NORMATIVO ("qué
requiere la ocupación"), NO demanda colombiana de vacantes. Sirve como referencia
autoritativa de competencias por carrera; en la UI se etiqueta como tal.

Acceso: API v2 en https://api-v2.onetcenter.org, autenticación por header
`X-API-Key`. Regístrate en https://services.onetcenter.org/developer/signup y pon
la clave en ONET_API_KEY. Sin la clave, las funciones devuelven listas vacías.

El resultado se cachea en memoria (O*NET es data de referencia que cambia pocas
veces al año): la primera consulta de un programa pega a la API, las siguientes
se sirven de caché hasta reiniciar el proceso.
"""

import requests

from config import ONET_API_KEY

ONET_BASE = "https://api-v2.onetcenter.org"

# Mapa: programa de La Sabana -> código de ocupación O*NET-SOC.
# Es una aproximación editable: cada programa apunta a la ocupación más cercana.
PROGRAMAS_ONET = {
    "Administración de Empresas": "11-1021.00",                       # General and Operations Managers
    "Administración & Servicio": "43-4051.00",                        # Customer Service Representatives
    "Administración de Mercadeo y Logística Internacionales": "11-2021.00",  # Marketing Managers
    "Administración de Negocios Internacionales": "13-1111.00",       # Management Analysts
    "Economía y Finanzas Internacionales": "13-2051.00",              # Financial and Investment Analysts
    "Economía y Finanzas Internacionales Virtual": "13-2051.00",      # Financial and Investment Analysts
    "Gastronomía": "35-1011.00",                                      # Chefs and Head Cooks
    "Comportamiento Organizacional": "13-1071.00",                    # Human Resources Specialists
    "Psicología": "19-3033.00",                                       # Clinical and Counseling Psychologists
    "Comunicación Audiovisual y Multimedios": "27-2012.00",           # Producers and Directors
    "Comunicación Corporativa": "27-3031.00",                         # Public Relations Specialists
    "Comunicación Social y Periodismo": "27-3023.00",                 # News Analysts, Reporters, Journalists
    "Licenciatura en Educación Infantil": "25-2011.00",               # Preschool Teachers
    "Enfermería": "29-1141.00",                                       # Registered Nurses
    "Fisioterapia": "29-1123.00",                                     # Physical Therapists
    "Ciencias Políticas": "19-3094.00",                               # Political Scientists
    "Derecho": "23-1011.00",                                          # Lawyers
    "Relaciones Internacionales": "19-3094.00",                       # Political Scientists (lo más cercano)
    "Filosofía": "25-1126.00",                                        # Philosophy and Religion Teachers, Postsecondary
    "Medicina": "29-1215.00",                                         # Family Medicine Physicians
    "Ciencia de Datos": "15-2051.00",                                 # Data Scientists
    "Ingeniería Civil": "17-2051.00",                                 # Civil Engineers
    "Ingeniería de Bioproducción": "17-2031.00",                      # Bioengineers and Biomedical Engineers
    "Ingeniería de Diseño e Innovación": "27-1021.00",                # Commercial and Industrial Designers
    "Ingeniería Industrial": "17-2112.00",                            # Industrial Engineers
    "Ingeniería Informática": "15-1252.00",                           # Software Developers
    "Ingeniería Mecánica": "17-2141.00",                              # Mechanical Engineers
    "Ingeniería Química": "17-2041.00",                               # Chemical Engineers
    "Ingeniería en Inteligencia Artificial": "15-1221.00",            # Computer and Information Research Scientists
}

# Caché en memoria: programa -> {"habilidades": [...], "tecnologias": [...]}
_cache = {}


def _get(path: str):
    """GET autenticado a la API de O*NET. Devuelve el JSON o None ante cualquier fallo."""
    if not ONET_API_KEY:
        return None
    try:
        resp = requests.get(
            f"{ONET_BASE}{path}",
            headers={"X-API-Key": ONET_API_KEY, "Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"   ❌ O*NET HTTP {resp.status_code} en {path}")
            return None
        return resp.json()
    except Exception as e:
        print(f"   ❌ O*NET error en {path}: {e}")
        return None


def _extraer_habilidades(data, max_n: int = 12):
    """Saca los nombres de habilidades de la respuesta de O*NET.

    Busca la primera lista de objetos que tengan 'name' (cada habilidad trae
    nombre y un puntaje de importancia). Tolerante a variaciones de estructura.
    """
    if not data:
        return []

    def buscar_lista(o):
        if isinstance(o, list):
            if o and isinstance(o[0], dict) and "name" in o[0]:
                return o
            for it in o:
                r = buscar_lista(it)
                if r:
                    return r
        elif isinstance(o, dict):
            for v in o.values():
                r = buscar_lista(v)
                if r:
                    return r
        return None

    lista = buscar_lista(data) or []
    nombres = []
    for it in lista:
        n = it.get("name")
        if n and n not in nombres:
            nombres.append(n)
        if len(nombres) >= max_n:
            break
    return nombres


def _extraer_tecnologias(data, max_n: int = 12):
    """Devuelve [{nombre, categoria, hot}] desde la respuesta technology_skills.

    Estructura real de O*NET:
      data["category"] = [ {"title": <categoría>, "example": [ {"title": <herramienta>,
                            "hot_technology": bool, "in_demand": bool, "percentage": int} ]} ]
    La categoría (ej. "Development environment software") sirve de explicación para
    CUALQUIER herramienta. Ordenamos por relevancia (hot/in-demand y % de empleadores).
    """
    if not data or not isinstance(data, dict):
        return []
    categorias = data.get("category")
    if not isinstance(categorias, list):
        return []

    items = []
    for cat in categorias:
        cat_title = cat.get("title")
        for ex in cat.get("example", []) or []:
            nombre = ex.get("title") or ex.get("name")
            if not nombre:
                continue
            items.append({
                "nombre": nombre,
                "categoria": cat_title,
                "hot": bool(ex.get("hot_technology")) or bool(ex.get("in_demand")),
                "pct": ex.get("percentage") or 0,
            })

    # Más relevantes primero: las "hot/in-demand" y las que más empleadores piden.
    items.sort(key=lambda x: (x["hot"], x["pct"]), reverse=True)

    vistos, unicos = set(), []
    for it in items:
        if it["nombre"] not in vistos:
            vistos.add(it["nombre"])
            unicos.append(it)
        if len(unicos) >= max_n:
            break
    return unicos


# Traducción al español de las habilidades de O*NET (es un vocabulario fijo de ~35
# "Skills"; si llegara un nombre fuera de la lista, se deja el original en inglés).
_TRADUCCIONES_SKILLS = {
    "Reading Comprehension": "Comprensión de lectura",
    "Active Listening": "Escucha activa",
    "Writing": "Redacción",
    "Speaking": "Expresión oral",
    "Mathematics": "Matemáticas",
    "Science": "Ciencia",
    "Critical Thinking": "Pensamiento crítico",
    "Active Learning": "Aprendizaje activo",
    "Learning Strategies": "Estrategias de aprendizaje",
    "Monitoring": "Monitoreo y autoevaluación",
    "Social Perceptiveness": "Percepción social",
    "Coordination": "Coordinación",
    "Persuasion": "Persuasión",
    "Negotiation": "Negociación",
    "Instructing": "Enseñanza/instrucción",
    "Service Orientation": "Orientación al servicio",
    "Complex Problem Solving": "Resolución de problemas complejos",
    "Operations Analysis": "Análisis de operaciones",
    "Technology Design": "Diseño de tecnología",
    "Equipment Selection": "Selección de equipos",
    "Installation": "Instalación",
    "Programming": "Programación",
    "Operations Monitoring": "Supervisión de operaciones",
    "Operation and Control": "Operación y control",
    "Equipment Maintenance": "Mantenimiento de equipos",
    "Troubleshooting": "Diagnóstico de fallas",
    "Repairing": "Reparación",
    "Quality Control Analysis": "Análisis de control de calidad",
    "Judgment and Decision Making": "Juicio y toma de decisiones",
    "Systems Analysis": "Análisis de sistemas",
    "Systems Evaluation": "Evaluación de sistemas",
    "Time Management": "Gestión del tiempo",
    "Management of Financial Resources": "Gestión de recursos financieros",
    "Management of Material Resources": "Gestión de recursos materiales",
    "Management of Personnel Resources": "Gestión de personal",
}

# Descripción (en español) de cada habilidad de O*NET. El vocabulario es fijo (35),
# así que cubrimos todas: cada competencia tiene siempre su explicación.
_DESCRIPCIONES_SKILLS = {
    "Reading Comprehension": "Entender oraciones y párrafos en documentos de trabajo.",
    "Active Listening": "Prestar total atención a lo que otros dicen, sin interrumpir y haciendo preguntas pertinentes.",
    "Writing": "Comunicarse por escrito de forma adecuada a las necesidades de la audiencia.",
    "Speaking": "Hablar con otros para transmitir información de manera efectiva.",
    "Mathematics": "Usar las matemáticas para resolver problemas.",
    "Science": "Usar métodos y reglas científicas para resolver problemas.",
    "Critical Thinking": "Usar la lógica y el razonamiento para evaluar fortalezas y debilidades de distintas soluciones.",
    "Active Learning": "Comprender las implicaciones de información nueva para problemas actuales y futuros.",
    "Learning Strategies": "Elegir y usar métodos de enseñanza/aprendizaje apropiados según la situación.",
    "Monitoring": "Evaluar el propio desempeño y el de otros para mejorar o corregir.",
    "Social Perceptiveness": "Percibir las reacciones de los demás y entender por qué reaccionan así.",
    "Coordination": "Ajustar las propias acciones en relación con las de los demás.",
    "Persuasion": "Convencer a otros de cambiar de opinión o de comportamiento.",
    "Negotiation": "Reunir a las partes y conciliar diferencias para llegar a acuerdos.",
    "Instructing": "Enseñar a otros cómo hacer algo.",
    "Service Orientation": "Buscar activamente formas de ayudar a las personas.",
    "Complex Problem Solving": "Identificar problemas complejos y evaluar opciones para implementar soluciones.",
    "Operations Analysis": "Analizar necesidades y requisitos de un producto para crear un diseño.",
    "Technology Design": "Generar o adaptar equipos y tecnología para atender necesidades del usuario.",
    "Equipment Selection": "Determinar el tipo de herramientas y equipos necesarios para un trabajo.",
    "Installation": "Instalar equipos, máquinas, cableado o programas según especificaciones.",
    "Programming": "Escribir programas de computador para diversos fines.",
    "Operations Monitoring": "Observar indicadores o instrumentos para asegurar el buen funcionamiento de una máquina.",
    "Operation and Control": "Controlar operaciones de equipos o sistemas.",
    "Equipment Maintenance": "Realizar mantenimiento de rutina y determinar cuándo se requiere.",
    "Troubleshooting": "Determinar las causas de errores de operación y decidir qué hacer al respecto.",
    "Repairing": "Reparar máquinas o sistemas con las herramientas necesarias.",
    "Quality Control Analysis": "Hacer pruebas e inspecciones de productos o procesos para evaluar la calidad.",
    "Judgment and Decision Making": "Sopesar costos y beneficios de las acciones posibles para elegir la más adecuada.",
    "Systems Analysis": "Determinar cómo debe funcionar un sistema y cómo lo afectan los cambios.",
    "Systems Evaluation": "Identificar indicadores de desempeño del sistema y acciones para mejorarlo.",
    "Time Management": "Gestionar el propio tiempo y el de los demás.",
    "Management of Financial Resources": "Determinar cómo se gastará el dinero y llevar el control de los gastos.",
    "Management of Material Resources": "Obtener y gestionar el uso adecuado de equipos, instalaciones y materiales.",
    "Management of Personnel Resources": "Motivar, desarrollar y dirigir al personal, eligiendo a los mejores para cada tarea.",
}

# Descripciones (en español) de las herramientas/tecnologías más comunes. La clave
# se busca como subcadena del nombre que entrega O*NET (que suele ser verboso, ej.
# "Structured query language SQL"). Si no hay match, se usa un texto genérico.
_DESCRIPCIONES_TECNOLOGIAS = {
    "python": "Lenguaje de programación de propósito general, muy usado en datos, IA y automatización.",
    "java": "Lenguaje de programación orientado a objetos, común en sistemas empresariales.",
    "javascript": "Lenguaje de programación de la web (interactividad en navegadores y backend con Node.js).",
    "c++": "Lenguaje de programación de alto rendimiento para software de sistemas.",
    "sql": "Lenguaje para consultar y gestionar bases de datos relacionales.",
    "excel": "Hoja de cálculo de Microsoft para análisis y organización de datos.",
    "powerpoint": "Software de presentaciones de Microsoft.",
    "word": "Procesador de texto de Microsoft.",
    "microsoft office": "Suite ofimática (Word, Excel, PowerPoint, etc.).",
    "outlook": "Cliente de correo y calendario de Microsoft.",
    "sharepoint": "Plataforma de Microsoft para gestión documental y colaboración.",
    "tableau": "Herramienta de visualización de datos y tableros (dashboards).",
    "power bi": "Herramienta de Microsoft para visualización de datos e inteligencia de negocios.",
    "sap": "Software empresarial (ERP) para gestionar procesos de negocio.",
    "oracle": "Sistemas de bases de datos y software empresarial de Oracle.",
    "salesforce": "Plataforma CRM en la nube para gestión de clientes y ventas.",
    "autocad": "Software de diseño asistido por computador (CAD) para planos 2D/3D.",
    "solidworks": "Software CAD para diseño mecánico en 3D.",
    "revit": "Software BIM para diseño y modelado de construcción.",
    "matlab": "Entorno de cómputo numérico y análisis para ingeniería y ciencia.",
    "sas": "Software de analítica estadística y gestión de datos.",
    "spss": "Software de análisis estadístico (IBM SPSS).",
    "stata": "Software de análisis estadístico y econométrico.",
    "minitab": "Software de análisis estadístico orientado a control de calidad.",
    "git": "Sistema de control de versiones para código fuente.",
    "linux": "Sistema operativo de código abierto, muy usado en servidores.",
    "sql server": "Sistema gestor de bases de datos de Microsoft.",
    "mysql": "Sistema gestor de bases de datos relacional de código abierto.",
    "postgresql": "Sistema gestor de bases de datos relacional avanzado de código abierto.",
    "photoshop": "Software de edición de imágenes de Adobe.",
    "illustrator": "Software de diseño vectorial de Adobe.",
    "indesign": "Software de maquetación y diseño editorial de Adobe.",
    "premiere": "Software de edición de video de Adobe.",
    "after effects": "Software de motion graphics y efectos visuales de Adobe.",
    "amazon web services": "Plataforma de servicios en la nube de Amazon (AWS).",
    "azure": "Plataforma de servicios en la nube de Microsoft.",
    "google cloud": "Plataforma de servicios en la nube de Google.",
    "docker": "Plataforma de contenedores para empaquetar y desplegar software.",
    "tensorflow": "Biblioteca de código abierto para machine learning y redes neuronales.",
    "pytorch": "Biblioteca de machine learning (aprendizaje profundo).",
    "hadoop": "Framework para procesar grandes volúmenes de datos.",
    "spark": "Motor de procesamiento de datos a gran escala.",
    "jira": "Herramienta de gestión de proyectos y seguimiento de tareas.",
    "quickbooks": "Software de contabilidad para pequeñas y medianas empresas.",
    "wordpress": "Plataforma de gestión de contenidos para sitios web.",
    "html": "Lenguaje de marcado para estructurar páginas web.",
    "css": "Lenguaje de estilos para el diseño de páginas web.",
}


def _traducir_habilidad(nombre: str) -> str:
    """Traduce una habilidad de O*NET al español (o la deja igual si no está en el mapa)."""
    return _TRADUCCIONES_SKILLS.get(nombre, nombre)


def _describir_habilidad(nombre_en: str) -> str:
    """Devuelve la explicación en español de una habilidad (clave = nombre en inglés de O*NET)."""
    return _DESCRIPCIONES_SKILLS.get(
        nombre_en, "Competencia identificada por O*NET como relevante para esta ocupación."
    )


# Traducción de las CATEGORÍAS de tecnología de O*NET (el "tipo" de herramienta).
# Sirven de explicación para cualquier herramienta no listada arriba. Si una
# categoría no está aquí, se muestra su título original (en inglés) como respaldo.
_TRADUCCIONES_CATEGORIAS = {
    "Development environment software": "Software de entorno de desarrollo.",
    "Object oriented development software": "Software de desarrollo orientado a objetos.",
    "Object or component oriented development software": "Software de desarrollo orientado a objetos o componentes.",
    "Application server software": "Software de servidor de aplicaciones.",
    "Web page creation and editing software": "Software de creación y edición de páginas web.",
    "Data base reporting software": "Software de generación de reportes de bases de datos.",
    "Information retrieval or search software": "Software de búsqueda y recuperación de información.",
    "Content workflow software": "Software de flujos de trabajo de contenido.",
    "Web platform development software": "Software para desarrollar plataformas y aplicaciones web.",
    "Enterprise application integration software": "Software para integrar aplicaciones empresariales.",
    "Enterprise resource planning ERP software": "Software de planificación de recursos empresariales (ERP).",
    "Data base management system software": "Software para gestionar bases de datos.",
    "Database management system software": "Software para gestionar bases de datos.",
    "Data base user interface and query software": "Software para consultar bases de datos.",
    "Operating system software": "Sistema operativo.",
    "Spreadsheet software": "Hoja de cálculo.",
    "Word processing software": "Procesador de texto.",
    "Presentation software": "Software de presentaciones.",
    "Electronic mail software": "Software de correo electrónico.",
    "Office suite software": "Suite ofimática.",
    "Analytical or scientific software": "Software analítico o científico.",
    "Business intelligence and data analysis software": "Software de inteligencia de negocios y análisis de datos.",
    "Project management software": "Software de gestión de proyectos.",
    "Customer relationship management CRM software": "Software de gestión de relaciones con clientes (CRM).",
    "Accounting software": "Software de contabilidad.",
    "Financial analysis software": "Software de análisis financiero.",
    "Graphics or photo imaging software": "Software de gráficos o edición de imágenes.",
    "Video creation and editing software": "Software de creación y edición de video.",
    "Desktop publishing software": "Software de autoedición y maquetación.",
    "Computer aided design CAD software": "Software de diseño asistido por computador (CAD).",
    "Computer aided manufacturing CAM software": "Software de manufactura asistida por computador (CAM).",
    "Medical software": "Software médico.",
    "Electronic medical records software": "Software de historia clínica electrónica.",
    "Cloud-based data access and sharing software": "Software de acceso y compartición de datos en la nube.",
    "Configuration management software": "Software de gestión de configuración.",
    "Program testing software": "Software de pruebas de programas.",
    "Network monitoring software": "Software de monitoreo de redes.",
    "Transaction security and virus protection software": "Software de seguridad y antivirus.",
    "Geographic information system GIS software": "Sistema de información geográfica (SIG).",
    "Human resources software": "Software de recursos humanos.",
    "Document management software": "Software de gestión documental.",
    "Data mining software": "Software de minería de datos.",
    "Internet browser software": "Navegador de internet.",
    "Calendar and scheduling software": "Software de calendario y agenda.",
    "Instant messaging software": "Software de mensajería instantánea.",
}


def _describir_tecnologia(nombre: str, categoria: str = None) -> str:
    """Explicación en español de una herramienta.

    Orden de preferencia: (1) descripción específica de la herramienta si es conocida,
    (2) la categoría O*NET traducida, (3) la categoría en inglés, (4) texto genérico.
    Así SIEMPRE hay una explicación con sentido para cada herramienta.
    """
    n = (nombre or "").lower()
    if n.strip() in ("r", "r programming language"):
        return "Lenguaje y entorno para análisis estadístico y ciencia de datos."
    for clave, desc in _DESCRIPCIONES_TECNOLOGIAS.items():
        if clave in n:
            return desc
    if categoria:
        return _TRADUCCIONES_CATEGORIAS.get(categoria, categoria)
    return "Herramienta o tecnología utilizada en esta ocupación según O*NET."


def obtener_competencias(programa: str):
    """Devuelve las competencias y tecnologías de un programa.

    Ambas son listas de objetos {nombre, descripcion} (todo en español), de modo
    que CADA ítem —habilidad o tecnología— tiene su propia explicación clickable.
    """
    code = PROGRAMAS_ONET.get(programa)
    if not code:
        return {"habilidades": [], "tecnologias": []}
    if programa in _cache:
        return _cache[programa]

    skills_en = _extraer_habilidades(_get(f"/online/occupations/{code}/details/skills"), 12)
    tec_en = _extraer_tecnologias(_get(f"/online/occupations/{code}/details/technology_skills"), 12)

    habilidades = [
        {"nombre": _traducir_habilidad(h), "descripcion": _describir_habilidad(h)}
        for h in skills_en
    ]
    tecnologias = [
        {"nombre": t["nombre"], "descripcion": _describir_tecnologia(t["nombre"], t["categoria"])}
        for t in tec_en
    ]
    resultado = {"habilidades": habilidades, "tecnologias": tecnologias}

    # Solo cacheamos si la API respondió con algo (evita "cachear" un fallo).
    if habilidades or tecnologias:
        _cache[programa] = resultado
    return resultado


def listar_programas():
    """Lista de programas con mapeo a O*NET (para poblar el selector del frontend)."""
    return list(PROGRAMAS_ONET.keys())
