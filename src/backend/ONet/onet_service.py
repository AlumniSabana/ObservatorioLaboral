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
    """Saca los nombres de tecnologías de la respuesta de technology_skills.

    O*NET agrupa las tecnologías en categorías, y los nombres reales (Python,
    Excel, etc.) viven en listas anidadas 'example'. Damos prioridad a esos.
    """
    if not data:
        return []
    nombres = []

    def add(n):
        if n and n not in nombres and len(nombres) < max_n:
            nombres.append(n)

    def walk(o):
        if len(nombres) >= max_n:
            return
        if isinstance(o, dict):
            ejemplos = o.get("example")
            if isinstance(ejemplos, list):
                for ex in ejemplos:
                    if isinstance(ex, dict):
                        add(ex.get("name") or ex.get("title"))
                    elif isinstance(ex, str):
                        add(ex)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)

    walk(data)
    # Si no había estructura 'example', caemos a la extracción genérica por nombre.
    if not nombres:
        return _extraer_habilidades(data, max_n)
    return nombres


def obtener_competencias(programa: str):
    """Devuelve {"habilidades": [...], "tecnologias": [...]} para un programa."""
    code = PROGRAMAS_ONET.get(programa)
    if not code:
        return {"habilidades": [], "tecnologias": []}
    if programa in _cache:
        return _cache[programa]

    habilidades = _extraer_habilidades(_get(f"/online/occupations/{code}/details/skills"), 12)
    tecnologias = _extraer_tecnologias(_get(f"/online/occupations/{code}/details/technology_skills"), 12)
    resultado = {"habilidades": habilidades, "tecnologias": tecnologias}

    # Solo cacheamos si la API respondió con algo (evita "cachear" un fallo).
    if habilidades or tecnologias:
        _cache[programa] = resultado
    return resultado


def listar_programas():
    """Lista de programas con mapeo a O*NET (para poblar el selector del frontend)."""
    return list(PROGRAMAS_ONET.keys())
