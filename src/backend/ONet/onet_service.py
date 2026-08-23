"""
Servicio de O*NET: competencias y tecnologías por ocupación, con su importancia.

O*NET (U.S. Dept. of Labor) es una base de datos de ~900 ocupaciones con sus
habilidades, conocimientos y tecnologías. Aquí mapeamos cada programa de La Sabana
a una ocupación O*NET (`PROGRAMAS_ONET`) y consultamos su API para obtener las
competencias y tecnologías de esa ocupación CON su peso de importancia.

Lo consume `Tendencias/skills_demandadas.py` (página "Skills más demandadas"),
que cruza estos pesos con la demanda real de cada programa.

⚠️ Sobre el dato: O*NET describe el mercado de EE.UU. y es NORMATIVO ("qué
requiere la ocupación"), NO demanda colombiana de vacantes.

Acceso: API v2 en https://api-v2.onetcenter.org, autenticación por header
`X-API-Key`. Regístrate en https://services.onetcenter.org/developer/signup y pon
la clave en ONET_API_KEY. Sin la clave, las funciones devuelven listas vacías.
El resultado se cachea en memoria (O*NET cambia pocas veces al año).
"""

import json
from pathlib import Path

import requests

from config import ONET_API_KEY
from traducciones import traducir_tecnologia

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


# ---------------------------------------------------------------------------
# Homologación a las 13 competencias generales (Monitoreo entorno 2025, Alumni
# Sabana): ese estudio rastreó ~656 términos de habilidades blandas en decenas
# de fuentes (LinkedIn, papers, diccionarios de competencias) y los agrupó a
# mano en 13 categorías generales. Aquí se traduce eso a las 35 "Skills" de
# O*NET —vocabulario FIJO y distinto al del estudio— para que la app pueda
# marcar cuáles de sus competencias son homologables a esa taxonomía.
#
# Solo se mapean las ~20 competencias de O*NET que son genuinamente blandas
# (las técnicas — Programación, Ciencia, Diseño de tecnología...— quedan fuera
# por diseño: no son "habilidades blandas", ver `_es_habilidad_tecnica`).
# No todo tiene un hogar natural en las 13 ("Comprensión de lectura" se deja
# sin homologar antes que forzarla en una categoría que no le corresponde).
#
# El criterio de cada asignación: se contrastó contra los términos CRUDOS reales
# que el estudio homologó en cada categoría (ej. "Active listening" aparece
# textual en los crudos de "Comunicación asertiva"; "Coaching" en los de
# "Trabajo en equipo"; "Autoridad y control sobre subordinados" en "Gestión").
# Persuasión/Negociación son la asignación menos obvia (podrían leerse también
# como Comunicación o Solución de problemas) — revisable si no calza con cómo
# lo usa Alumni.
HOMOLOGACION_13 = {
    "Escucha activa": "Comunicación asertiva",
    "Redacción": "Comunicación asertiva",
    "Expresión oral": "Comunicación asertiva",
    "Pensamiento crítico": "Pensamiento estratégico y analítico",
    "Aprendizaje activo": "Aprender a aprender",
    "Estrategias de aprendizaje": "Aprender a aprender",
    "Monitoreo y autoevaluación": "Aprender a aprender",
    "Percepción social": "Trabajo en equipo",
    "Coordinación": "Trabajo en equipo",
    "Enseñanza/instrucción": "Trabajo en equipo",
    "Persuasión": "Liderazgo",
    "Negociación": "Liderazgo",
    "Orientación al servicio": "Servicio",
    "Resolución de problemas complejos": "Solución de problemas",
    "Juicio y toma de decisiones": "Toma de decisiones",
    "Gestión del tiempo": "Gestión",
    "Gestión de recursos financieros": "Gestión",
    "Gestión de recursos materiales": "Gestión",
    "Gestión de personal": "Gestión",
}

# Las 13 categorías del estudio, en el orden en que aparecen ahí (por volumen
# de menciones). Sirve para que el frontend garantice que estén representadas
# en la gráfica de tendencias aunque su demanda de mercado no las meta en el
# top-N por sí solas — ver `evolucion_skills`.
CATEGORIAS_HOMOLOGADAS_13 = [
    "Apropiación y gestión de la tecnología",
    "Gestión",
    "Liderazgo",
    "Adaptación al cambio",
    "Comunicación asertiva",
    "Pensamiento estratégico y analítico",
    "Aprender a aprender",
    "Solución de problemas",
    "Trabajo en equipo",
    "Creatividad",
    "Servicio",
    "Toma de decisiones",
    "Responsabilidad ambiental y de recursos",
]


def homologada_a(nombre_es: str) -> str | None:
    """La categoría de las 13 a la que se homologa esta competencia, o None."""
    return HOMOLOGACION_13.get(nombre_es)


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


# ---------------------------------------------------------------------------
# Competencias y tecnologías CON PUNTAJE, para el ranking de "skills más
# demandadas". Cada skill trae su PESO en la ocupación, para ponderar: una skill
# vale según cuánto la requiere la ocupación (importancia O*NET) y cuánta demanda
# tiene esa ocupación en el mercado real (que se calcula aparte, en
# Tendencias/skills_demandadas.py).
# ---------------------------------------------------------------------------

_cache_scored = {}


def _skills_con_score(data, max_n: int = 20):
    """[(nombre_en, importancia 0-100, id_onet)] desde la respuesta de skills de O*NET.

    Se guarda el `id` (p. ej. '2.B.3.e') porque es la forma OFICIAL de O*NET de
    distinguir sus 35 "Skills" entre sí — no hay que adivinar por el nombre.
    Ver `_ES_HABILIDAD_TECNICA`.
    """
    def buscar(o):
        if isinstance(o, list):
            if o and isinstance(o[0], dict) and "name" in o[0]:
                return o
            for it in o:
                r = buscar(it)
                if r:
                    return r
        elif isinstance(o, dict):
            for v in o.values():
                r = buscar(v)
                if r:
                    return r
        return None

    out = []
    for it in (buscar(data) or [])[:max_n]:
        nombre = it.get("name")
        imp = it.get("importance")
        if nombre and imp:
            out.append((nombre, float(imp), it.get("id", "")))
    return out


# Del taxonomía oficial de O*NET (Content Model), grupo "2.B.3 Technical" dentro
# de las 35 Skills: Operations Analysis, Technology Design, Equipment Selection,
# Installation, Programming, Operation Monitoring, Operation and Control,
# Equipment Maintenance, Troubleshooting, Repairing, Quality Control Analysis.
# Se suman Mathematics y Science (2.A.1.e/f): son "Basic Skills > Content" en la
# taxonomía de O*NET, no "Technical", pero para quien ve el perfil son igual de
# técnicas y no pertenecen junto a cosas como "Persuasión" o "Negociación" bajo
# "Competencias clave" — que es justo lo que reportó el feedback del 12 ago 2026
# ("Programación, Ciencia, Matemáticas aparecen como Competencias clave").
def _es_habilidad_tecnica(element_id: str) -> bool:
    return element_id.startswith("2.B.3.") or element_id in ("2.A.1.e", "2.A.1.f")


# IDs oficiales de O*NET para las 35 Skills (Content Model, estable). Solo se
# listan las que hacen falta para derivar `NOMBRES_TECNICOS_ES` sin tener que
# volver a llamar a la API — el resto de `competencias_scored()` sí usa el id
# real que devuelve cada ocupación, este mapa es nada más para este cálculo.
_IDS_SKILLS_TECNICAS = {
    "Mathematics": "2.A.1.e",
    "Science": "2.A.1.f",
    "Operations Analysis": "2.B.3.a",
    "Technology Design": "2.B.3.b",
    "Equipment Selection": "2.B.3.c",
    "Installation": "2.B.3.d",
    "Programming": "2.B.3.e",
    "Operations Monitoring": "2.B.3.f",
    "Operation and Control": "2.B.3.g",
    "Equipment Maintenance": "2.B.3.h",
    "Troubleshooting": "2.B.3.i",
    "Repairing": "2.B.3.j",
    "Quality Control Analysis": "2.B.3.k",
}

# Nombres en ESPAÑOL de las competencias que O*NET clasifica como técnicas.
# Usado para filtrarlas de vistas que solo deben mostrar habilidades blandas
# (ranking y gráfica de tendencia de la página Competencias) sin tener que
# repetir la lógica de IDs en cada sitio que lo necesite.
NOMBRES_TECNICOS_ES = {
    _traducir_habilidad(nombre_en) for nombre_en in _IDS_SKILLS_TECNICAS
}


def _tecnologias_con_score(data, max_n: int = 25):
    """[(nombre, categoria, peso 0-100)] desde technology_skills de O*NET.

    Peso: el `percentage` de empleadores si viene; si no, un proxy por relevancia
    (hot/in-demand pesa más que una herramienta cualquiera).
    """
    if not isinstance(data, dict):
        return []
    items = []
    for cat in data.get("category", []) or []:
        cat_title = cat.get("title")
        for ex in cat.get("example", []) or []:
            nombre = ex.get("title") or ex.get("name")
            if not nombre:
                continue
            pct = ex.get("percentage")
            hot = bool(ex.get("hot_technology")) or bool(ex.get("in_demand"))
            peso = float(pct) if pct else (70.0 if hot else 40.0)
            items.append((nombre, cat_title, peso))
    items.sort(key=lambda x: -x[2])
    return items[:max_n]


def competencias_scored(programa: str):
    """Competencias y tecnologías de un programa, CADA UNA con su peso O*NET.

    Devuelve {"competencias": [{nombre, descripcion, peso}],
              "tecnologias":  [{nombre, descripcion, peso}]}
    con los nombres ya en español. `peso` es 0-100 (importancia O*NET para las
    competencias; % de empleadores/relevancia para las tecnologías).
    """
    code = PROGRAMAS_ONET.get(programa)
    if not code:
        return {"competencias": [], "tecnologias": []}
    if programa in _cache_scored:
        return _cache_scored[programa]

    skills = _skills_con_score(_get(f"/online/occupations/{code}/details/skills"))
    tecs = _tecnologias_con_score(_get(f"/online/occupations/{code}/details/technology_skills"))

    # `competencias`/`tecnologias` se quedan COMPLETAS, igual que siempre: las
    # usa Tendencias/skills_demandadas.py para el ranking de mercado y el KPI de
    # "emergentes" de la página Competencias, que necesita el pool entero para
    # tener señal de tendencia (se probó sacar Programación/Ciencia/Matemáticas
    # de ahí y el KPI se quedó con un solo término emergente — esas tres son
    # justo las más volátiles del grupo, y sin ellas lo que queda es demasiado
    # transversal/plano para mostrar movimiento real).
    competencias = [
        {
            "nombre": _traducir_habilidad(nombre),
            "descripcion": _describir_habilidad(nombre),
            "peso": peso,
            # Categoría de las 13 homologadas (Monitoreo entorno 2025, Alumni
            # Sabana) a la que pertenece, o None si no es homologable.
            "homologada": homologada_a(_traducir_habilidad(nombre)),
        }
        for nombre, peso, element_id in skills
    ]
    tecnologias = [
        {
            "nombre": traducir_tecnologia(nombre),
            "descripcion": _describir_tecnologia(nombre, categoria),
            "peso": peso,
        }
        for nombre, categoria, peso in tecs
    ]
    # Subconjunto de `competencias` que O*NET clasifica como técnicas (ver
    # `_es_habilidad_tecnica`). Se lista APARTE, sin sacarlas de `competencias`:
    # quien solo necesite el pool de mercado (arriba) las ignora sin más, y quien
    # muestra un programa suelto (Perfil ocupacional) las mueve a tecnologías en
    # su propia vista, donde no rompe ninguna estadística agregada.
    competencias_tecnicas = sorted({
        _traducir_habilidad(nombre) for nombre, _, element_id in skills
        if _es_habilidad_tecnica(element_id)
    })
    resultado = {
        "competencias": competencias,
        "tecnologias": tecnologias,
        "competencias_tecnicas": competencias_tecnicas,
    }
    if competencias or tecnologias:
        _cache_scored[programa] = resultado
    return resultado


# ---------------------------------------------------------------------------
# Perfil ocupacional O*NET: intereses RIASEC + Job Zone + descripción.
# Alimenta la página "Perfil Ocupacional" (sección de contexto vocacional).
# ---------------------------------------------------------------------------

# RIASEC (modelo de Holland). Orden canónico R-I-A-S-E-C.
_RIASEC_ORDEN = ["Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"]
_RIASEC_ES = {
    "Realistic": ("R", "Realista"),
    "Investigative": ("I", "Investigador"),
    "Artistic": ("A", "Artístico"),
    "Social": ("S", "Social"),
    "Enterprising": ("E", "Emprendedor"),
    "Conventional": ("C", "Convencional"),
}

# Job Zone (1-5): nivel de preparación que requiere la ocupación.
_JOB_ZONE_ES = {
    1: ("Poca preparación", "Requiere poca o ninguna preparación previa."),
    2: ("Algo de preparación", "Requiere formación breve y algo de experiencia."),
    3: ("Preparación media", "Requiere formación técnica o tecnológica y experiencia."),
    4: ("Preparación alta", "Requiere un título universitario y experiencia considerable."),
    5: ("Preparación extensa", "Requiere posgrado y amplia experiencia especializada."),
}

# Descripción breve en español por ocupación de referencia (código SOC). Conjunto
# cerrado de los 29 programas; si falta o la API no responde, cae a la descripción
# en inglés de O*NET (fallback). Coherente con las traducciones del backend.
_DESCRIPCIONES_OCUPACION_ES = {
    "11-1021.00": "Planifican, dirigen y coordinan las operaciones de una organización a nivel general.",
    "43-4051.00": "Atienden y resuelven las solicitudes de los clientes sobre productos y servicios.",
    "11-2021.00": "Diseñan y dirigen estrategias de mercadeo para posicionar productos y servicios.",
    "13-1111.00": "Analizan procesos y proponen mejoras para aumentar la eficiencia de las organizaciones.",
    "13-2051.00": "Evalúan inversiones y datos financieros para orientar decisiones económicas.",
    "35-1011.00": "Dirigen la cocina, crean menús y supervisan la preparación de alimentos.",
    "13-1071.00": "Gestionan la selección, el desarrollo y el bienestar del talento humano.",
    "19-3033.00": "Evalúan y acompañan la salud mental y el comportamiento de las personas.",
    "27-2012.00": "Planifican y dirigen la producción de contenidos audiovisuales y multimedia.",
    "27-3031.00": "Gestionan la comunicación y la reputación de las organizaciones ante sus públicos.",
    "27-3023.00": "Investigan, redactan y difunden noticias e información de interés público.",
    "25-2011.00": "Educan y acompañan el desarrollo integral de niños en la primera infancia.",
    "29-1141.00": "Brindan cuidado clínico a los pacientes y coordinan su atención en salud.",
    "29-1123.00": "Rehabilitan el movimiento y la función física de los pacientes.",
    "19-3094.00": "Analizan sistemas políticos, políticas públicas y asuntos de gobierno.",
    "23-1011.00": "Asesoran y representan a personas y organizaciones en asuntos legales.",
    "25-1126.00": "Investigan y enseñan filosofía y pensamiento crítico a nivel superior.",
    "29-1215.00": "Diagnostican y tratan enfermedades brindando atención médica integral.",
    "15-2051.00": "Extraen conocimiento de grandes volúmenes de datos con métodos analíticos.",
    "17-2051.00": "Diseñan y supervisan obras de infraestructura civil como vías y edificaciones.",
    "17-2031.00": "Aplican la ingeniería a sistemas biológicos y a la producción biotecnológica.",
    "27-1021.00": "Diseñan productos y soluciones que combinan función, innovación y estética.",
    "17-2112.00": "Optimizan procesos, recursos y sistemas productivos en las organizaciones.",
    "15-1252.00": "Diseñan, desarrollan y mantienen software y sistemas informáticos.",
    "17-2141.00": "Diseñan y desarrollan sistemas y máquinas mecánicas.",
    "17-2041.00": "Diseñan procesos y plantas para transformar materias primas mediante química.",
    "15-1221.00": "Investigan y desarrollan nuevas tecnologías de computación e inteligencia artificial.",
}

_CACHE_PERFIL_PATH = Path(__file__).resolve().parent / "_cache_perfil_onet.json"
_cache_perfil: dict | None = None


def _riasec_desde_api(code: str) -> list[dict]:
    """Intereses RIASEC (0-100) en orden R-I-A-S-E-C, traducidos. [] si no hay datos."""
    data = _get(f"/online/occupations/{code}/details/interests")
    if not isinstance(data, dict):
        return []
    valores = {}
    for el in data.get("element", []) or []:
        nombre = el.get("name")
        val = el.get("occupational_interest")
        if nombre in _RIASEC_ES and val is not None:
            valores[nombre] = float(val)
    salida = []
    for nombre_en in _RIASEC_ORDEN:
        if nombre_en in valores:
            cod, nombre_es = _RIASEC_ES[nombre_en]
            salida.append({"codigo": cod, "nombre": nombre_es, "valor": round(valores[nombre_en], 1)})
    return salida


def perfil_onet(programa: str) -> dict:
    """
    Contexto vocacional O*NET de un programa: intereses RIASEC, Job Zone (nivel de
    preparación) y descripción de la ocupación de referencia. Cacheado en memoria
    y disco. Si no hay ONET_API_KEY o la ocupación no está mapeada, degrada con
    gracia (riasec=[], job_zone=None, descripcion=None) para que la UI lo oculte.

    Nota de mantenimiento: al cambiar traducciones aquí, borrar `_cache_perfil_onet.json`.
    """
    global _cache_perfil
    if _cache_perfil is None:
        if _CACHE_PERFIL_PATH.exists():
            try:
                with open(_CACHE_PERFIL_PATH, encoding="utf-8") as fh:
                    _cache_perfil = json.load(fh)
            except Exception:
                _cache_perfil = {}
        else:
            _cache_perfil = {}

    if programa in _cache_perfil:
        return _cache_perfil[programa]

    code = PROGRAMAS_ONET.get(programa)
    vacio = {"codigo_soc": code, "ocupacion_ref": None, "descripcion": None,
             "job_zone": None, "riasec": [], "bright_outlook": False}
    if not code:
        return vacio

    detalle = _get(f"/online/occupations/{code}") or {}
    jz = _get(f"/online/occupations/{code}/details/job_zone") or {}

    job_zone = None
    nivel = jz.get("code")
    if isinstance(nivel, int) and nivel in _JOB_ZONE_ES:
        etiqueta, frase = _JOB_ZONE_ES[nivel]
        job_zone = {"nivel": nivel, "etiqueta": etiqueta, "descripcion": frase}

    descripcion = _DESCRIPCIONES_OCUPACION_ES.get(code) or detalle.get("description")

    resultado = {
        "codigo_soc": code,
        "ocupacion_ref": detalle.get("title"),
        "descripcion": descripcion,
        "job_zone": job_zone,
        "riasec": _riasec_desde_api(code),
        "bright_outlook": bool((detalle.get("tags") or {}).get("bright_outlook")),
    }

    # Solo se cachea si vino con contenido real (no persistir un fallo de la API).
    if resultado["riasec"] or resultado["job_zone"]:
        _cache_perfil[programa] = resultado
        try:
            with open(_CACHE_PERFIL_PATH, "w", encoding="utf-8") as fh:
                json.dump(_cache_perfil, fh, ensure_ascii=False)
        except Exception:
            pass
    return resultado
