"""
ole_service.py — ingreso de graduados por programa (OLE, MinEducación).

QUÉ APORTA QUE NO TENÍAMOS
`Salarios/salarios_service.py` estima el salario de un programa por vía
indirecta: programa → ocupación (PROGRAMA_CNO) → GEIH. Eso mide el ingreso de
quien EJERCE la ocupación, venga de la formación que venga. El OLE mide a los
graduados del programa, y distingue los de La Sabana del resto del país.

Las dos conviven; no se promedian. Ver la cabecera de la migración 010.

⚠️ LA FUENTE NO DA PESOS, DA BANDAS
El OLE publica el conteo de graduados en 7 rangos de SMMLV. La mediana se
estima por interpolación lineal dentro de la banda que la contiene — el método
estándar para datos agrupados. No es un dato medido: es una estimación, y la UI
debe decirlo. Cuando la mediana cae en la banda abierta ('Más de 9 SMMLV') no
hay forma honesta de interpolar y se devuelve `None` con `mediana_abierta`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from Adzuna.adzuna_service import supabase

TABLA_SABANA = "ole_ibc_sabana"
TABLA_NACIONAL = "ole_ibc_nacional"

# Límites de cada banda en SMMLV. El último es abierto por arriba (None).
# El orden importa: se recorre para acumular la distribución.
BANDAS: list[tuple[str, float, float | None]] = [
    ("1 SMMLV", 0.0, 1.0),
    ("Entre 1 y 1,5 SMMLV", 1.0, 1.5),
    ("Entre 1,5 y 2,5 SMMLV", 1.5, 2.5),
    ("Entre 2,5 y 4 SMMLV", 2.5, 4.0),
    ("Entre 4 y 6 SMMLV", 4.0, 6.0),
    ("Entre 6 y 9 SMMLV", 6.0, 9.0),
    ("Más de 9 SMMLV", 9.0, None),
]
_ORDEN = {nombre: i for i, (nombre, _, _) in enumerate(BANDAS)}

# SMMLV del año de corte, para traducir la mediana a pesos. El IBC se observa en
# el año de corte (no en el de graduación), así que este es el salario mínimo
# que corresponde. Al cambiar de corte hay que actualizar ambos.
ANIO_CORTE = 2023
SMMLV_CORTE = 1_160_000

# Programa de La Sabana -> nombre(s) con que aparece en el OLE. Solo hacen falta
# los que NO casan por normalización: renombres y programas heredados.
# Los que faltan (Ciencia de Datos, Ing. en IA, Relaciones Internacionales,
# Comportamiento Organizacional, Ing. de Diseño e Innovación) son programas
# nuevos SIN graduados en el corte 2023: no es un fallo del mapeo, es que
# todavía no existen en la fuente.
ALIAS_OLE: dict[str, list[str]] = {
    "Administración & Servicio": [
        "ADMINISTRACION SERVICIO",
        "ADMINISTRACION DE INSTITUCIONES DE SERVICIO",
    ],
    # El programa cambió de nombre dos veces; los tres son la misma cohorte.
    "Licenciatura en Educación Infantil": [
        "LICENCIATURA EN EDUCACION INFANTIL",
        "LICENCIATURA EN PEDAGOGIA INFANTIL",
        "LICENCIATURA EN EDUCACION PREESCOLAR",
    ],
    "Administración de Mercadeo y Logística Internacionales": [
        "ADMINISTRACION DE MERCADEO Y LOGISTICA INTERNACIONALES",
        "ADMINISTRACION EN MERCADEO Y LOGISTICA INTERNACIONALES",
    ],
}

_PAGINA = 1000
_cache_tablas: bool | None = None


def _normalizar(s: str) -> str:
    """Sin tildes, sin puntuación, en minúsculas: 'Ingeniería Química' -> 'ingenieria quimica'."""
    limpio = unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", limpio).strip()


def _todas_las_filas(consulta_factory) -> list[dict]:
    """Pagina: Supabase corta en 1000 filas sin avisar."""
    filas: list[dict] = []
    inicio = 0
    while True:
        try:
            r = consulta_factory().range(inicio, inicio + _PAGINA - 1).execute()
        except Exception:
            break
        if not r.data:
            break
        filas.extend(r.data)
        if len(r.data) < _PAGINA:
            break
        inicio += _PAGINA
    return filas


def tablas_disponibles() -> bool:
    """True si la migración 010 ya corrió."""
    global _cache_tablas
    if _cache_tablas is None:
        try:
            supabase.table(TABLA_SABANA).select("id").limit(1).execute()
            _cache_tablas = True
        except Exception:
            _cache_tablas = False
    return _cache_tablas


def invalidar_cache() -> None:
    global _cache_tablas
    _cache_tablas = None


def hay_datos() -> bool:
    if not tablas_disponibles():
        return False
    try:
        r = supabase.table(TABLA_SABANA).select("id", count="exact", head=True).execute()
        return (r.count or 0) > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Estadística sobre datos agrupados
# ---------------------------------------------------------------------------
def _mediana_interpolada(conteo: dict[str, int]) -> tuple[float | None, bool]:
    """
    Mediana estimada por interpolación lineal dentro de la banda que la contiene.

    Devuelve (mediana_en_smmlv, cayo_en_banda_abierta). Si cae en 'Más de 9
    SMMLV' no hay límite superior con el que interpolar, así que se devuelve
    None: inventar un techo sería fabricar el dato.
    """
    total = sum(conteo.values())
    if total == 0:
        return None, False

    objetivo = total / 2
    acumulado = 0
    for nombre, lo, hi in BANDAS:
        freq = conteo.get(nombre, 0)
        if freq == 0:
            continue
        if acumulado + freq >= objetivo:
            if hi is None:
                return None, True
            return round(lo + (objetivo - acumulado) / freq * (hi - lo), 2), False
        acumulado += freq
    return None, False


def _distribucion(conteo: dict[str, int]) -> list[dict]:
    """Las 7 bandas en orden, con conteo y porcentaje. Incluye las vacías: un
    hueco en la distribución también informa."""
    total = sum(conteo.values()) or 1
    return [{
        "rango": nombre,
        "graduados": conteo.get(nombre, 0),
        "pct": round(conteo.get(nombre, 0) / total * 100, 1),
    } for nombre, _, _ in BANDAS]


# Por debajo de esto la mediana se mueve con un puñado de personas y no
# describe al programa. No se oculta el dato: se marca para que la UI avise.
MIN_GRADUADOS_FIABLE = 30


def _resumen(conteo: dict[str, int]) -> dict[str, Any] | None:
    total = sum(conteo.values())
    if total == 0:
        return None
    mediana, abierta = _mediana_interpolada(conteo)
    # Cuota por encima de 4 SMMLV: el umbral donde el OLE separa de facto los
    # ingresos profesionales consolidados de los de entrada.
    sobre_4 = sum(c for n, c in conteo.items() if _ORDEN.get(n, 0) >= _ORDEN["Entre 4 y 6 SMMLV"])
    return {
        "graduados": total,
        "mediana_smmlv": mediana,
        "mediana_cop": round(mediana * SMMLV_CORTE) if mediana else None,
        "mediana_abierta": abierta,
        "pct_sobre_4smmlv": round(sobre_4 / total * 100, 1),
        "muestra_corta": total < MIN_GRADUADOS_FIABLE,
        "distribucion": _distribucion(conteo),
    }


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def _nombres_ole(programa: str) -> list[str]:
    """Nombres con los que el OLE conoce este programa (incluye renombres)."""
    if programa in ALIAS_OLE:
        return ALIAS_OLE[programa]
    return []


def _casa(nombre_ole: str, programa: str, alias: list[str]) -> bool:
    if alias:
        return nombre_ole.upper() in {a.upper() for a in alias}
    return _normalizar(nombre_ole) == _normalizar(programa)


def ingreso_por_programa(programa: str, nivel: str = "Universitario") -> dict[str, Any]:
    """
    Ingreso de los graduados de un programa: los de La Sabana frente al país.

    `nivel` filtra por nivel de formación ('Universitario' = pregrado). Se hace
    aquí y no en la consulta porque una maestría y un pregrado del mismo nombre
    no son comparables y mezclarlos inflaría la mediana.
    """
    vacio = {
        "programa": programa, "nivel": nivel, "sin_datos": True,
        "sabana": None, "nacional": None, "anio_corte": ANIO_CORTE,
    }
    if not tablas_disponibles():
        return vacio

    alias = _nombres_ole(programa)

    filas_sab = _todas_las_filas(
        lambda: supabase.table(TABLA_SABANA)
        .select("programa,rango,graduados,anio_grado")
        .eq("nivel_formacion", nivel)
    )
    conteo_sab: dict[str, int] = {}
    anios: list[int] = []
    for f in filas_sab:
        if not _casa(f["programa"], programa, alias):
            continue
        conteo_sab[f["rango"]] = conteo_sab.get(f["rango"], 0) + (f["graduados"] or 0)
        if f.get("anio_grado"):
            anios.append(f["anio_grado"])

    filas_nac = _todas_las_filas(
        lambda: supabase.table(TABLA_NACIONAL)
        .select("programa,rango,graduados,n_ies")
        .eq("nivel_formacion", nivel)
    )
    conteo_nac: dict[str, int] = {}
    n_ies = 0
    for f in filas_nac:
        if not _casa(f["programa"], programa, alias):
            continue
        conteo_nac[f["rango"]] = conteo_nac.get(f["rango"], 0) + (f["graduados"] or 0)
        n_ies = max(n_ies, f.get("n_ies") or 0)

    sabana = _resumen(conteo_sab)
    nacional = _resumen(conteo_nac)
    if not sabana and not nacional:
        return vacio

    # Si La Sabana es la única institución que ofrece el programa, la "referencia
    # nacional" ES La Sabana: la brecha da 0% siempre y parece un hallazgo cuando
    # es una tautología. Pasa con 5 de nuestros programas. Se suprime la
    # comparación y se dice por qué.
    unico_oferente = n_ies <= 1

    # La diferencia solo tiene sentido si ambas medianas son puntuales: compararse
    # contra una banda abierta daría un número que parece exacto y no lo es.
    brecha = None
    if (not unico_oferente and sabana and nacional
            and sabana["mediana_smmlv"] and nacional["mediana_smmlv"]):
        brecha = round((sabana["mediana_smmlv"] / nacional["mediana_smmlv"] - 1) * 100, 1)

    if sabana:
        sabana["anios_grado"] = [min(anios), max(anios)] if anios else None
    if nacional:
        nacional["n_ies"] = n_ies or None

    return {
        "programa": programa,
        "nivel": nivel,
        "sin_datos": False,
        "sabana": sabana,
        # Con un solo oferente el "nacional" es un espejo; no se devuelve para
        # que la UI no pueda pintarlo como si fuera una referencia externa.
        "nacional": None if unico_oferente else nacional,
        "unico_oferente": unico_oferente,
        "brecha_vs_nacional_pct": brecha,
        "anio_corte": ANIO_CORTE,
        "smmlv_corte": SMMLV_CORTE,
    }


# Niveles que cuentan como posgrado. 'Universitario' es el pregrado y queda
# fuera; los técnicos y tecnológicos no los ofrece La Sabana.
NIVELES_POSGRADO = {
    "Especialización", "Especialización médico quirúrgica", "Maestría", "Doctorado",
}


def posgrados_sabana(top: int = 12) -> list[dict]:
    """
    Posgrados de La Sabana ordenados por el ingreso de sus graduados.

    OJO CON LA TENTACIÓN DE CRUZARLO CON EL PREGRADO: en el OLE un posgrado es
    un PROGRAMA APARTE con su propio nombre ('ESPECIALIZACION EN GERENCIA
    ESTRATEGICA'), no el mismo programa en otro nivel. No existe forma en la
    fuente de saber de qué pregrado venía cada graduado, así que no se puede
    construir una escalera pregrado→posgrado por programa. Esto responde otra
    pregunta, la que la fuente sí permite: qué posgrado de la universidad va
    asociado a mayores ingresos.

    Es una asociación, no un efecto causal: quien cursa un MBA ya suele venir de
    un cargo mejor pagado. La UI debe decirlo.
    """
    if not tablas_disponibles():
        return []

    filas = _todas_las_filas(
        lambda: supabase.table(TABLA_SABANA).select("programa,nivel_formacion,rango,graduados")
    )
    por_programa: dict[tuple[str, str], dict[str, int]] = {}
    for f in filas:
        if f["nivel_formacion"] not in NIVELES_POSGRADO:
            continue
        d = por_programa.setdefault((f["programa"], f["nivel_formacion"]), {})
        d[f["rango"]] = d.get(f["rango"], 0) + (f["graduados"] or 0)

    salida = []
    for (prog, nivel), conteo in por_programa.items():
        r = _resumen(conteo)
        # Se descartan los de muestra corta en vez de marcarlos: aquí el dato se
        # usa para ORDENAR, y una mediana de 3 personas colada arriba del
        # ranking desinforma más de lo que aporta.
        if r and not r["muestra_corta"]:
            salida.append({"programa": prog, "nivel": nivel, **r})

    # Mayor mediana primero; los de banda abierta ('> 9 SMMLV') encabezan, que es
    # donde de verdad están.
    salida.sort(key=lambda x: (x["mediana_smmlv"] is None, x["mediana_smmlv"] or 0), reverse=True)
    return salida[:top]


def catalogo_fuente() -> list[dict]:
    """El OLE como fuente seleccionable."""
    if not hay_datos():
        return []
    return [{
        "id": "ole:men",
        "fuente": "ole",
        "pais": None,
        "tipo": "normativo",
        "naturaleza": "observado",
        "label": f"OLE — MinEducación {ANIO_CORTE}",
        "sublabel": "ingreso real de graduados por programa",
        "dimensiones": ["salario"],
    }]
