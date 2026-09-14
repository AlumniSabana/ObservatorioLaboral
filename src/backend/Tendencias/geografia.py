"""
Geografía de las vacantes colombianas: departamento y ciudad.

QUÉ RESUELVE
------------
El motor de tendencias (`tendencias_observaciones`) solo guarda `pais`: no hay
ninguna dimensión geográfica por debajo del país, y `vacantes_historicas`
tampoco copia la ciudad. Este módulo añade esa capa leyendo las tablas CRUDAS
de las dos fuentes colombianas (`vacantes_google` y `vacantes_linkedin`), que sí
guardan `location` y `city`.

Se lee de las tablas crudas a propósito, en vez de añadir una columna a
`vacantes_historicas`: no requiere migración manual en Supabase y las dos tablas
contienen exactamente las mismas vacantes colombianas que el histórico (mismo
conteo, misma pertinencia aplicada al recolectar).

DE DÓNDE SALE EL DEPARTAMENTO
-----------------------------
No hace falta DIVIPOLA ni un diccionario de los ~1.100 municipios: el `location`
crudo YA trae el departamento en la mayoría de los casos, con formas distintas
según la fuente:

    Google Jobs   "Medellín, Antioquia"              -> componente 2
    LinkedIn      "Cali, Valle del Cauca, Colombia"  -> componente 2
    LinkedIn      "Cundinamarca, Colombia"           -> componente 1 (sin ciudad)
    ambas         "Bogotá"                           -> la ciudad ES el distrito

La estrategia es buscar en CUALQUIER componente del texto un nombre de
departamento conocido, lo que tolera las tres formas sin casos especiales.
Medido sobre datos reales (2026-09-14): resuelve el 91% de Google Jobs y el 89%
de LinkedIn Colombia.

Lo que queda sin departamento es casi todo vacantes cuyo `location` es
literalmente "Colombia": son ofertas nacionales o remotas que no declaran
ciudad. NO se reparten ni se fuerzan a ningún departamento — se reportan aparte
como "Sin departamento", igual que el criterio de `seniority.py` sobre no
inventar un valor donde no hay dato.

LO QUE ESTE MÓDULO NO HACE
--------------------------
No calcula CRECIMIENTO ni series mensuales por departamento, y es deliberado:
las vacantes colombianas se concentran en 2 meses (jul-2026 y ago-2026 suman el
94%), porque Google Jobs y LinkedIn solo entregan fechas relativas y cada
recolección alcanza ~2 meses hacia atrás. El motor de tendencias exige un mínimo
de 3 periodos; partido por departamento no hay ni de lejos. Dibujar una flecha
de crecimiento con 2 puntos sería inventar la señal, así que este panel es una
FOTO DEL ESTADO ACTUAL, no una tendencia.

Tampoco desglosa por SECTOR: Google Jobs no entrega sector (la dimensión llega
vacía al histórico) y el `industries` de LinkedIn está vacío porque solo se
recolecta la tarjeta de búsqueda, no el detalle de cada oferta.
"""

from __future__ import annotations

import re
import time as _time
import unicodedata
from collections import Counter
from typing import Any, Dict, List

from Adzuna.adzuna_service import normalize_title, supabase
# Se reutiliza la lista curada de empresas que no dicen su nombre en vez de
# mantener otra aquí: son la misma regla y duplicarlas las hace divergir.
from Tendencias.demanda_actual import _es_empresa_confidencial
from Tendencias.escolaridad import ETIQUETAS as ETIQUETAS_CUOC
from Tendencias.escolaridad import NO_ESPECIFICADO, detectar_escolaridad
from Tendencias.seniority import ETIQUETAS as ETIQUETAS_SENIORITY
from Tendencias.seniority import NO_ESPECIFICADO as SENIORITY_SIN_DATO
from Tendencias.seniority import detectar_seniority
from traducciones import traducir_cargo

# Por debajo de esta cifra el departamento se marca como muestra insuficiente.
# No lo oculta: lo sigue mostrando con el aviso, para que se vea que el dato
# existe pero no aguanta que se lea como un patrón del mercado.
MIN_MUESTRA_DEPARTAMENTO = 30

# Cuántos elementos devuelve cada ranking del panel.
TOP_N = 10

_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 300  # segundos


# ---------------------------------------------------------------------------
# Catálogo de departamentos (código DANE = llave de unión con el mapa)
# ---------------------------------------------------------------------------
# El código DANE es la llave y NO el nombre: el GeoJSON del mapa trae los
# nombres sin tildes y en la forma larga ("SANTAFE DE BOGOTA D.C"), así que unir
# por texto sería frágil. Los códigos son los de DIVIPOLA.
DEPARTAMENTOS: Dict[str, str] = {
    "05": "Antioquia", "08": "Atlántico", "11": "Bogotá D.C.", "13": "Bolívar",
    "15": "Boyacá", "17": "Caldas", "18": "Caquetá", "19": "Cauca",
    "20": "Cesar", "23": "Córdoba", "25": "Cundinamarca", "27": "Chocó",
    "41": "Huila", "44": "La Guajira", "47": "Magdalena", "50": "Meta",
    "52": "Nariño", "54": "Norte de Santander", "63": "Quindío",
    "66": "Risaralda", "68": "Santander", "70": "Sucre", "73": "Tolima",
    "76": "Valle del Cauca", "81": "Arauca", "85": "Casanare",
    "86": "Putumayo", "88": "San Andrés y Providencia", "91": "Amazonas",
    "94": "Guainía", "95": "Guaviare", "97": "Vaupés", "99": "Vichada",
}


def _plegar(texto: str | None) -> str:
    """Minúsculas sin tildes, para comparar 'Atlantico' con 'Atlántico'."""
    if not texto:
        return ""
    sin_tilde = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tilde if unicodedata.category(c) != "Mn").strip()


# Índice de búsqueda: texto plegado -> código DANE. Arranca con el nombre
# oficial de cada departamento y se le suman las variantes observadas en datos
# reales (abreviaturas, el nombre en inglés que devuelve LinkedIn, las áreas
# metropolitanas y los nombres largos).
_INDICE: Dict[str, str] = {_plegar(n): c for c, n in DEPARTAMENTOS.items()}
_INDICE.update({
    # Bogotá: es distrito capital, no pertenece a Cundinamarca. LinkedIn lo
    # devuelve además traducido ("Capital District") y como área metropolitana.
    "bogota": "11",
    "bogota d.c.": "11",
    "bogota dc": "11",
    "d.c.": "11",
    "distrito capital": "11",
    "capital district": "11",
    "bogota d.c. metropolitan area": "11",
    "santafe de bogota d.c": "11",
    # Áreas metropolitanas que LinkedIn entrega en vez del departamento.
    "medellin metropolitan area": "05",
    "cali metropolitan area": "76",
    "bucaramanga metropolitan area": "68",
    "barranquilla metropolitan area": "08",
    "armenia metropolitan area": "63",
    "pereira metropolitan area": "66",
    # Abreviaturas y nombres largos observados.
    "nte. de santander": "54",
    "n. de santander": "54",
    "archipielago de san andres providencia y santa catalina": "88",
    "san andres": "88",
    "san andres y providencia": "88",
    "valle": "76",
})

# Sufijo de agregación de Google Jobs: "Rionegro, Antioquia (y 6 ubicaciones más)".
_RE_SUFIJO = re.compile(r"\s*\(y\s+\d+\s+ubicaci(?:ón|ones)\s+m[aá]s\)\s*$", re.IGNORECASE)

# Componentes que nunca son un departamento y no vale la pena mirar.
_IGNORAR = {"colombia", ""}


def detectar_departamento(location: str | None, city: str | None = None) -> str | None:
    """Código DANE del departamento inferido de la ubicación cruda.

    Busca un nombre de departamento conocido en CUALQUIER componente del texto,
    lo que cubre por igual "Medellín, Antioquia", "Cali, Valle del Cauca,
    Colombia" y "Cundinamarca, Colombia" sin tratar cada forma por separado.

    Devuelve None cuando la vacante no declara departamento (típicamente
    `location == "Colombia"`): quien llama decide, y aquí se reporta como
    "Sin departamento" en vez de repartirlo.
    """
    partes = [_RE_SUFIJO.sub("", p).strip() for p in (location or "").split(",")]
    # La ciudad va al final: es el respaldo cuando `location` no aporta nada
    # (p. ej. filas cuyo city ya ES un departamento, "Antioquia").
    for parte in [*partes, city or ""]:
        clave = _plegar(parte)
        if clave in _IGNORAR:
            continue
        codigo = _INDICE.get(clave)
        if codigo:
            return codigo
    return None


# Sufijos que LinkedIn le cuelga al nombre de la ciudad y que la parten en
# varios valores ("Medellín" vs "Medellín Metropolitan Area").
_RE_SUFIJO_CIUDAD = re.compile(r"\s+(metropolitan area|ciudad)\s*$", re.IGNORECASE)


def _ciudad_de(location: str | None, city: str | None) -> str | None:
    """Ciudad legible, o None si la fila solo declara país/departamento.

    Cuando la 'ciudad' es en realidad el departamento (filas cuyo location es
    "Cundinamarca, Colombia") no se inventa un municipio: se devuelve None y el
    panel lo agrupa como "Sin ciudad especificada".
    """
    bruto = _RE_SUFIJO.sub("", (city or "").strip())
    bruto = _RE_SUFIJO_CIUDAD.sub("", bruto).strip()
    if not bruto or _plegar(bruto) in _IGNORAR:
        return None
    # Si el propio texto es un departamento, no es una ciudad.
    if _plegar(bruto) in _INDICE:
        # Bogotá es la excepción: es ciudad Y distrito.
        return "Bogotá" if _INDICE[_plegar(bruto)] == "11" else None
    return bruto


def _top_ciudades(spellings: Dict[str, Counter], n: int = TOP_N) -> List[Dict[str, Any]]:
    """Ranking de ciudades unificando las grafías de una misma ciudad.

    Las fuentes escriben el mismo municipio de varias formas ("Medellín" y
    "Medellin", "Tocancipá" y "Tocancipa"), lo que sin unificar lo parte en dos
    filas del ranking. Se agrupa por la forma sin tildes y se muestra la grafía
    MÁS FRECUENTE, que en la práctica es siempre la correcta con tildes: así no
    hace falta mantener un diccionario de municipios y sirve para los que
    lleguen en el futuro.
    """
    totales = Counter({clave: sum(c.values()) for clave, c in spellings.items()})
    salida = []
    for clave, total in totales.most_common(n):
        etiqueta = spellings[clave].most_common(1)[0][0]
        salida.append({"nombre": etiqueta, "vacantes": total})
    return salida


# ---------------------------------------------------------------------------
# Lectura de las dos fuentes colombianas
# ---------------------------------------------------------------------------

def _leer_tabla(tabla: str, campos: str, filtro: tuple | None = None) -> List[Dict[str, Any]]:
    """Lee una tabla completa paginando (Supabase corta en 1000 filas)."""
    filas: List[Dict[str, Any]] = []
    inicio, pagina = 0, 1000
    while True:
        consulta = supabase.table(tabla).select(campos)
        if filtro:
            consulta = consulta.eq(*filtro)
        resp = consulta.range(inicio, inicio + pagina - 1).execute()
        if not resp.data:
            break
        filas.extend(resp.data)
        if len(resp.data) < pagina:
            break
        inicio += pagina
    return filas


def _vacantes_colombianas(fuentes: List[str] | None = None) -> List[Dict[str, Any]]:
    """Vacantes de Colombia de ambas fuentes, ya normalizadas a un mismo shape.

    `fuentes` acepta los mismos códigos de mercado que usa el selector del
    frontend: 'co' (Google Jobs) y 'co_li' (LinkedIn Colombia). None = ambas.
    """
    quiere = set(fuentes or ["co", "co_li"])
    salida: List[Dict[str, Any]] = []

    if "co" in quiere:
        for f in _leer_tabla(
            "vacantes_google", "title,company,location,city,programa_relacionado"
        ):
            salida.append({**f, "fuente": "Google Jobs"})

    if "co_li" in quiere:
        for f in _leer_tabla(
            "vacantes_linkedin",
            "title,company,location,city,programa_relacionado",
            ("pais", "co"),
        ):
            salida.append({**f, "fuente": "LinkedIn"})

    return salida


def _enriquecer(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Precalcula UNA VEZ por fila lo que sale del título y de la ubicación.

    Sin esto, `traducir_cargo` (cascada de 4 niveles) y las heurísticas de CUOC
    y seniority se ejecutaban dos veces sobre cada vacante —una al agregar su
    departamento y otra al agregar el nacional—, y el endpoint tardaba ~5 s.
    Precalculado baja a décimas.
    """
    for f in filas:
        titulo = f.get("title") or ""
        nivel = detectar_escolaridad(titulo)
        f["_cargo"] = traducir_cargo(normalize_title(titulo))
        f["_ciudad"] = _ciudad_de(f.get("location"), f.get("city")) or "Sin ciudad especificada"
        f["_cuoc"] = ETIQUETAS_CUOC[nivel] if nivel != NO_ESPECIFICADO else None
        # Etiqueta legible, no el código interno: este valor se pinta tal cual.
        # Los títulos que no declaran nivel quedan en None y no entran al
        # ranking: son el 88% (la mayoría de las ofertas no dice seniority en el
        # título) y como barra taparían por completo los niveles que sí se
        # declaran, que es lo único informativo aquí.
        sen = detectar_seniority(titulo)
        f["_seniority"] = ETIQUETAS_SENIORITY[sen] if sen != SENIORITY_SIN_DATO else None
        f["_departamento"] = detectar_departamento(f.get("location"), f.get("city"))
    return filas


def _cache_vacantes(fuentes: List[str] | None) -> List[Dict[str, Any]]:
    """Caché por combinación de fuentes: son ~6.000 filas y 6 viajes a Supabase."""
    clave = ",".join(sorted(fuentes or ["co", "co_li"]))
    ahora = _time.time()
    hit = _CACHE.get(clave)
    if hit and (ahora - hit[0]) < _CACHE_TTL:
        return hit[1]
    filas = _enriquecer(_vacantes_colombianas(fuentes))
    _CACHE[clave] = (ahora, filas)
    return filas


def invalidar_cache() -> None:
    """Vacía el caché (llamar tras recolectar para ver los cambios ya)."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Agregación por departamento
# ---------------------------------------------------------------------------

def _top(contador: Counter, n: int = TOP_N) -> List[Dict[str, Any]]:
    return [{"nombre": k, "vacantes": v} for k, v in contador.most_common(n)]


def _panel(filas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construye el panel de analíticas de un conjunto de vacantes."""
    cargos: Counter = Counter()
    empresas: Counter = Counter()
    # ciudad plegada -> Counter de las grafías con que aparece (ver _top_ciudades).
    ciudades: Dict[str, Counter] = {}
    cuoc: Counter = Counter()
    seniority: Counter = Counter()
    fuentes: Counter = Counter()

    # Los campos con guion bajo los precalcula `_enriquecer` al leer de la BD.
    for f in filas:
        if f["_cargo"]:
            cargos[f["_cargo"]] += 1

        empresa = (f.get("company") or "").strip()
        if empresa and not _es_empresa_confidencial(empresa):
            empresas[empresa] += 1

        ciudad = f["_ciudad"]
        ciudades.setdefault(_plegar(ciudad), Counter())[ciudad] += 1

        if f["_cuoc"]:
            cuoc[f["_cuoc"]] += 1

        if f["_seniority"]:
            seniority[f["_seniority"]] += 1
        fuentes[f.get("fuente")] += 1

    return {
        "vacantes": len(filas),
        "cargos_distintos": len(cargos),
        "empresas_distintas": len(empresas),
        "ciudades_distintas": len([c for c in ciudades if c != _plegar("Sin ciudad especificada")]),
        "top_cargos": _top(cargos),
        "top_empresas": _top(empresas),
        "ciudades": _top_ciudades(ciudades),
        "grupos_cuoc": _top(cuoc, 6),
        "seniority": _top(seniority, 6),
        "por_fuente": _top(fuentes, 5),
        "muestra_suficiente": len(filas) >= MIN_MUESTRA_DEPARTAMENTO,
    }


def resumen_departamentos(
    programa: str | None = None,
    fuentes: List[str] | None = None,
) -> Dict[str, Any]:
    """Analítica de vacantes colombianas por departamento.

    Devuelve el panel completo de CADA departamento con datos, más el agregado
    nacional y el bloque de vacantes sin departamento declarado. El frontend
    recibe todo de una vez y resuelve el clic en el mapa sin otra petición: son
    ~6.000 vacantes, agregarlas enteras es más barato que una llamada por clic.

    `programa` filtra por programa académico (None o 'TODOS' = sin filtrar).
    `fuentes` limita a 'co' (Google Jobs) y/o 'co_li' (LinkedIn Colombia).
    """
    filas = _cache_vacantes(fuentes)

    if programa and programa != "TODOS":
        filas = [f for f in filas if f.get("programa_relacionado") == programa]

    por_codigo: Dict[str, List[Dict[str, Any]]] = {}
    sin_departamento: List[Dict[str, Any]] = []

    for f in filas:
        codigo = f["_departamento"]
        if codigo:
            por_codigo.setdefault(codigo, []).append(f)
        else:
            sin_departamento.append(f)

    departamentos = [
        {
            "codigo": codigo,
            "nombre": DEPARTAMENTOS[codigo],
            **_panel(grupo),
        }
        for codigo, grupo in por_codigo.items()
    ]
    departamentos.sort(key=lambda d: d["vacantes"], reverse=True)

    con_depto = sum(d["vacantes"] for d in departamentos)

    return {
        "departamentos": departamentos,
        "nacional": _panel(filas),
        "sin_departamento": {
            "vacantes": len(sin_departamento),
            **(_panel(sin_departamento) if sin_departamento else {}),
        },
        "meta": {
            "total": len(filas),
            "con_departamento": con_depto,
            "sin_departamento": len(sin_departamento),
            "cobertura": round(con_depto / len(filas) * 100, 1) if filas else 0.0,
            "departamentos_con_datos": len(departamentos),
            "min_muestra": MIN_MUESTRA_DEPARTAMENTO,
            "programa": programa or "TODOS",
            "fuentes": sorted(fuentes or ["co", "co_li"]),
            # El panel es una foto del estado actual, no una serie: ver el
            # docstring del módulo sobre por qué no hay crecimiento.
            "incluye_crecimiento": False,
        },
    }
