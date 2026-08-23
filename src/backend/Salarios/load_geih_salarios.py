"""
load_geih_salarios.py — ETL de salarios reales en COP para el Observatorio.

Procesa los microdatos de la GEIH (Gran Encuesta Integrada de Hogares, DANE) y
produce un JSON con estadísticas salariales por ocupación (CNO), listo para que
el backend lo sirva sin volver a tocar los microdatos.

POR QUÉ ASÍ (contexto para quien mantenga esto):
  - La GEIH NO tiene API. Se descarga a mano un ZIP mensual (~70 MB) desde
    https://microdatos.dane.gov.co/index.php/catalog/900 (requiere registro
    gratuito). Sale con ~2 meses de rezago. Para un observatorio universitario
    NO vale la pena mensual: los salarios medianos por ocupación se mueven poco.
    Cadencia recomendada: cada 3-6 meses (ver README/memoria del proyecto).
  - El eje salarial de este observatorio es el PROGRAMA académico. La GEIH no
    trae "programa", pero sí la OCUPACIÓN en código CNO-2020 (columna OFICIO_C8,
    4 dígitos, alineado a ISCO-08). El servicio (salarios_service.py) mapea cada
    programa Sabana -> subgrupo CNO (2 dígitos) y ahí lee el salario.
  - Se agrega SOLO por ocupación CNO (grupo 1 dígito y subgrupo 2 dígitos). El
    nivel educativo y el sector viven en OTROS módulos del ZIP y requieren joins
    frágiles; no aportan al pivote por programa, así que se omiten a propósito.
    (En la versión previa del proyecto hermano esos desgloses salían vacíos por
    intentar mapear un RAMA numérico como si fuera letra CIIU.)

Uso:
    python load_geih_salarios.py --geih_dir "ruta/al/Febrero_2026.zip"
    python load_geih_salarios.py --geih_dir "ruta/al/Febrero_2026.zip" --listar

Salida (por defecto: Salarios/data/geih_salarios.json):
{
  "meta": {"periodo": "Feb 2026", "fuente": "...", "n_ocupados": ..., ...},
  "por_cno_grupo":    {"2": {"codigo","nombre","mediana","p25","p75",...}, ...},
  "por_cno_subgrupo": {"24": {...}, ...},
  "spe_rangos": [ {"rango","min_cop","max_cop","participacion","variacion"}, ...],
  "tiene_geih": true
}
"""

import argparse
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CNO-2020 (alineado a ISCO-08) — nombres en español
# El código OFICIO_C8 de la GEIH es de 4 dígitos: el 1er dígito es el gran grupo,
# los 2 primeros el subgrupo principal.
# ─────────────────────────────────────────────────────────────────────────────
CNO_GRUPOS = {
    "0": "Ocupaciones militares",
    "1": "Directores y gerentes",
    "2": "Profesionales, científicos e intelectuales",
    "3": "Técnicos y profesionales de nivel medio",
    "4": "Personal de apoyo administrativo",
    "5": "Trabajadores de servicios y vendedores",
    "6": "Agricultores y trabajadores agropecuarios",
    "7": "Oficiales, operarios y artesanos",
    "8": "Operadores de instalaciones y máquinas",
    "9": "Ocupaciones elementales",
}

CNO_SUBGRUPOS = {
    "01": "Oficiales de las fuerzas armadas",
    "02": "Suboficiales de las fuerzas armadas",
    "03": "Otros miembros de las fuerzas armadas",
    "11": "Directores ejecutivos y personal directivo de la administración pública",
    "12": "Directores administrativos y comerciales",
    "13": "Directores y gerentes de producción y operaciones",
    "14": "Gerentes de hotelería, comercio y otros servicios",
    "21": "Profesionales de las ciencias y de la ingeniería",
    "22": "Profesionales de la salud",
    "23": "Profesionales de la enseñanza",
    "24": "Profesionales en finanzas y administración",
    "25": "Profesionales de tecnología de la información y las comunicaciones",
    "26": "Profesionales en derecho, ciencias sociales y culturales",
    "31": "Técnicos de las ciencias y la ingeniería",
    "32": "Técnicos de nivel medio de la salud",
    "33": "Técnicos de nivel medio en finanzas y administración",
    "34": "Técnicos de servicios jurídicos, sociales y culturales",
    "35": "Técnicos de la información y las comunicaciones",
    "41": "Oficinistas y auxiliares administrativos",
    "42": "Empleados en trato directo con el público",
    "43": "Empleados contables y de registro de materiales",
    "44": "Otro personal de apoyo administrativo",
    "51": "Trabajadores de los servicios personales",
    "52": "Vendedores",
    "53": "Trabajadores de los cuidados personales",
    "54": "Personal de los servicios de protección",
    "61": "Agricultores y trabajadores calificados agropecuarios",
    "62": "Trabajadores forestales, pesqueros y cazadores calificados",
    "63": "Trabajadores agropecuarios y pesqueros de subsistencia",
    "71": "Oficiales y operarios de la construcción",
    "72": "Oficiales de la metalurgia y la construcción mecánica",
    "73": "Artesanos y operarios de artes gráficas",
    "74": "Trabajadores de electricidad y electrotecnología",
    "75": "Operarios de procesamiento de alimentos y confección",
    "81": "Operadores de instalaciones fijas y máquinas",
    "82": "Ensambladores",
    "83": "Conductores y operadores de equipos móviles",
    "91": "Limpiadores y asistentes",
    "92": "Peones agropecuarios, pesqueros y forestales",
    "93": "Peones de minería, construcción, industria y transporte",
    "94": "Ayudantes de preparación de alimentos",
    "95": "Vendedores ambulantes y ocupaciones afines",
    "96": "Recolectores de desechos y otras ocupaciones elementales",
}

# ─────────────────────────────────────────────────────────────────────────────
# Rangos SPE (datos reales del boletín de Demanda Laboral, Feb 2026 — Tabla 7).
# Participación = % de vacantes en cada rango; variación = cambio anual (a/a).
# Fuente: Servicio Público de Empleo (SPE) Colombia. Actualizar al re-descargar.
# ─────────────────────────────────────────────────────────────────────────────
SPE_RANGOS_FIJOS = [
    {"rango": "Hasta $1.000.000",         "min_cop": 0,         "max_cop": 1_000_000,  "participacion": 1.1,  "variacion": -49.6},
    {"rango": "$1.000.001 – $1.500.000",  "min_cop": 1_000_001, "max_cop": 1_500_000,  "participacion": 4.6,  "variacion": -91.2},
    {"rango": "$1.500.001 – $2.000.000",  "min_cop": 1_500_001, "max_cop": 2_000_000,  "participacion": 54.6, "variacion": 193.5},
    {"rango": "$2.000.001 – $3.000.000",  "min_cop": 2_000_001, "max_cop": 3_000_000,  "participacion": 12.4, "variacion": 9.0},
    {"rango": "$3.000.001 – $4.000.000",  "min_cop": 3_000_001, "max_cop": 4_000_000,  "participacion": 4.2,  "variacion": 64.3},
    {"rango": "Más de $4.000.000",        "min_cop": 4_000_001, "max_cop": 99_000_000, "participacion": 1.9,  "variacion": 18.6},
    {"rango": "A convenir",               "min_cop": None,      "max_cop": None,        "participacion": 21.2, "variacion": -34.8},
]

# Nombres de módulos y de sus columnas clave en la GEIH.
_PART_OCUPADOS = "Ocupados"           # nombre base del CSV empieza por esto
_PART_CARACTERISTICAS = "caracter"    # "Características generales, ... y educación.CSV"
_COLS_INGRESO = ("INGLABO", "INGTOTOB", "INGTOT")   # ingreso laboral mensual
_COLS_OFICIO = ("OFICIO_C8", "OFICIO", "P6430")     # ocupación CNO (4 dígitos)
_COLS_EDUCACION = ("P3042", "P6210")                # nivel educativo más alto alcanzado
_JOIN_KEYS = ("DIRECTORIO", "SECUENCIA_P", "ORDEN") # identifican a la persona entre módulos

# Nivel educativo GEIH (P3042, "nivel más alto alcanzado", rediseño 2021+) -> etiqueta.
# El orden es el del código: sirve para ordenar la escalera educativa en el frontend.
NIVEL_EDU = {
    "1": "Ninguno",
    "2": "Preescolar",
    "3": "Básica primaria",
    "4": "Básica secundaria",
    "5": "Media académica",
    "6": "Media técnica",
    "7": "Normalista",
    "8": "Técnica profesional",
    "9": "Tecnológica",
    "10": "Universitaria (pregrado)",
    "11": "Especialización",
    "12": "Maestría",
    "13": "Doctorado",
}

# Filtro de outliers: por debajo de ~medio SMMLV o por encima de 50M es ruido/typo.
_MIN_COP = 300_000
_MAX_COP = 50_000_000


def _estadisticas(serie: pd.Series) -> dict | None:
    """Estadísticas salariales básicas en COP, o None si hay muy pocos datos."""
    s = pd.to_numeric(serie, errors="coerce").dropna()
    s = s[(s >= _MIN_COP) & (s <= _MAX_COP)]
    if len(s) < 30:  # umbral de muestra: por debajo, la mediana no es fiable
        return None
    return {
        "mediana": int(s.median()),
        "media":   int(s.mean()),
        "p25":     int(s.quantile(0.25)),
        "p75":     int(s.quantile(0.75)),
        "p10":     int(s.quantile(0.10)),
        "p90":     int(s.quantile(0.90)),
        "n":       int(len(s)),
    }


def _leer_modulo(geih_dir: Path, empieza_por: str,
                 columnas: dict[str, tuple]) -> pd.DataFrame:
    """
    Lee un módulo de la GEIH (CSV dentro del ZIP o en carpeta) trayendo solo las
    columnas pedidas. `empieza_por` filtra por el INICIO del nombre base del
    archivo (así "Ocupados" no captura "No ocupados"). `columnas` mapea el nombre
    de salida deseado -> tupla de nombres candidatos en el CSV (se toma el 1º que
    exista). Lanza ValueError si algún candidato no aparece.

    La GEIH viene en latin-1 y a veces con ';'. sep=None + engine python
    autodetecta el delimitador.
    """
    def _procesar(buffer_factory, nombre) -> pd.DataFrame:
        cabecera = pd.read_csv(buffer_factory(), encoding="latin-1", sep=None,
                               engine="python", nrows=0)
        cols = list(cabecera.columns)
        resol = {}  # candidato_real -> nombre_salida
        for salida, candidatos in columnas.items():
            hit = next((c for c in candidatos if c in cols), None)
            if hit is None:
                raise ValueError(
                    f"'{nombre}': no encuentro columna para '{salida}' "
                    f"(candidatos {candidatos}). Disponibles (muestra): {cols[:20]}"
                )
            resol[hit] = salida
        df = pd.read_csv(buffer_factory(), encoding="latin-1", sep=None,
                         engine="python", usecols=list(resol))
        return df.rename(columns=resol)

    def _coincide(nombre_archivo: str) -> bool:
        base = nombre_archivo.rsplit("/", 1)[-1].lower()
        return base.startswith(empieza_por.lower())

    if geih_dir.suffix.lower() == ".zip":
        with zipfile.ZipFile(geih_dir) as z:
            objetivo = next(
                (n for n in z.namelist()
                 if _coincide(n) and n.upper().endswith(".CSV")),
                None,
            )
            if objetivo is None:
                raise FileNotFoundError(
                    f"No hay CSV que empiece por '{empieza_por}' dentro de "
                    f"{geih_dir.name}. Contenido: "
                    f"{[n for n in z.namelist() if not n.endswith('/')][:12]}"
                )
            print(f"  ✓ Módulo: {objetivo}")
            data = z.read(objetivo)
            return _procesar(lambda: io.BytesIO(data), objetivo)

    # Carpeta
    candidatos = [f for f in geih_dir.rglob("*")
                  if f.is_file() and f.suffix.upper() == ".CSV" and _coincide(f.name)]
    if not candidatos:
        raise FileNotFoundError(f"No se encontró CSV que empiece por '{empieza_por}' en {geih_dir}")
    ruta = max(candidatos, key=lambda f: f.stat().st_size)
    print(f"  ✓ Módulo: {ruta.name}")
    return _procesar(lambda: ruta, ruta.name)


def _escalera_educativa(grp: pd.DataFrame) -> dict:
    """Salario por nivel educativo dentro de un grupo (dict {cod_edu: stats})."""
    salida = {}
    for codigo_f, sub in grp.groupby("_educ"):
        codigo = str(int(codigo_f))
        nombre = NIVEL_EDU.get(codigo)
        if not nombre:
            continue
        stats = _estadisticas(sub["_ingreso"])
        if stats:
            salida[codigo] = {"codigo": codigo, "nombre": nombre,
                              "orden": int(codigo), **stats}
    return salida


def _desglose_educativo(geih_dir: Path, ocupados: pd.DataFrame) -> tuple[dict, dict]:
    """
    Cruza Ocupados con el módulo de Características (variable P3042) por persona y
    devuelve (nacional, por_subgrupo):

      - nacional: escalera salarial por nivel educativo sobre TODO el país
        (responde "cuánto sube el salario con posgrado" en general).
      - por_subgrupo: {subgrupo_CNO(2 díg.): {nivel_educativo: stats}} — la misma
        escalera pero DENTRO de cada gran grupo ocupacional. Es lo que permite que,
        al filtrar por programa, la escalera refleje su ocupación (controla por
        oficio, así que el premio del posgrado sale más limpio).

    Devuelve ({}, {}) si el módulo no está o le falta la columna: es opcional y no
    debe tumbar el resto del ETL. La muestra pequeña se poda sola: `_estadisticas`
    descarta cualquier celda con n<30, así que los subgrupos solo conservan los
    niveles con datos fiables (típicamente pregrado y posgrados).
    """
    try:
        cols = {**{k: (k,) for k in _JOIN_KEYS}, "_educ": _COLS_EDUCACION}
        car = _leer_modulo(geih_dir, _PART_CARACTERISTICAS, cols)
    except (FileNotFoundError, ValueError) as e:
        print(f"  ⚠ Nivel educativo omitido: {e}")
        return {}, {}

    m = ocupados.merge(car, on=list(_JOIN_KEYS), how="left")
    m["_educ"] = pd.to_numeric(m["_educ"], errors="coerce")
    m = m[m["_educ"].notna()]

    nacional = _escalera_educativa(m)

    por_subgrupo = {}
    for g2, grp in m.groupby("_g2"):
        if g2 not in CNO_SUBGRUPOS:
            continue
        escalera = _escalera_educativa(grp)
        if escalera:  # solo subgrupos con al menos un nivel fiable
            por_subgrupo[g2] = escalera

    return nacional, por_subgrupo


def procesar_geih(geih_dir: Path, periodo: str = "Feb 2026") -> dict:
    """Procesa la GEIH y arma el dict de salarios (ver docstring del módulo)."""
    # Ocupados con ingreso, ocupación CNO y llaves de cruce (para el join educativo).
    cols_ocu = {"_ingreso": _COLS_INGRESO, "_oficio": _COLS_OFICIO,
                **{k: (k,) for k in _JOIN_KEYS}}
    df = _leer_modulo(geih_dir, _PART_OCUPADOS, cols_ocu)

    df["_ingreso"] = pd.to_numeric(df["_ingreso"], errors="coerce")
    con = df[df["_ingreso"] > 0].copy()

    # Normalizar el código CNO a solo dígitos y quedarnos con grupo/subgrupo.
    con["_cno"] = con["_oficio"].astype(str).str.extract(r"(\d+)")[0]
    con = con[con["_cno"].notna()]
    con["_g1"] = con["_cno"].str[:1]
    con["_g2"] = con["_cno"].str[:2]

    validos = con[(con["_ingreso"] >= _MIN_COP) & (con["_ingreso"] <= _MAX_COP)]

    resultado = {
        "meta": {
            "periodo": periodo,
            "fuente": "GEIH DANE (ingreso laboral real) + SPE Colombia (rangos de vacantes)",
            "n_ocupados": int(len(df)),
            "con_ingreso": int(len(con)),
            "mediana_nacional": int(validos["_ingreso"].median()) if len(validos) else None,
            "nota": "Salarios mensuales en COP. Agregación por ocupación CNO-2020 (OFICIO_C8).",
        },
        "por_cno_grupo": {},
        "por_cno_subgrupo": {},
        "por_nivel_educativo": {},        # escalera educativa NACIONAL
        "por_subgrupo_educacion": {},     # escalera educativa DENTRO de cada subgrupo CNO
        "spe_rangos": SPE_RANGOS_FIJOS,
        "tiene_geih": True,
    }

    # ── Por gran grupo CNO (1 dígito) ──────────────────────────────────────
    for g1, grp in con.groupby("_g1"):
        nombre = CNO_GRUPOS.get(g1)
        if not nombre:
            continue
        stats = _estadisticas(grp["_ingreso"])
        if stats:
            resultado["por_cno_grupo"][g1] = {"codigo": g1, "nombre": nombre, **stats}

    # ── Por subgrupo CNO (2 dígitos) ───────────────────────────────────────
    for g2, grp in con.groupby("_g2"):
        nombre = CNO_SUBGRUPOS.get(g2)
        if not nombre:
            continue
        stats = _estadisticas(grp["_ingreso"])
        if stats:
            resultado["por_cno_subgrupo"][g2] = {"codigo": g2, "nombre": nombre, **stats}

    # ── Nivel educativo (nacional + por subgrupo CNO, cruce con Características) ─
    nacional, por_subgrupo = _desglose_educativo(geih_dir, con)
    resultado["por_nivel_educativo"] = nacional
    resultado["por_subgrupo_educacion"] = por_subgrupo

    print(f"  📊 Ocupados: {len(df):,} | Con ingreso: {len(con):,}")
    print(f"  📋 Grupos CNO: {len(resultado['por_cno_grupo'])} | "
          f"Subgrupos CNO: {len(resultado['por_cno_subgrupo'])} | "
          f"Niveles educativos (nac.): {len(resultado['por_nivel_educativo'])} | "
          f"Subgrupos con escalera: {len(resultado['por_subgrupo_educacion'])}")
    if resultado["meta"]["mediana_nacional"]:
        print(f"  💰 Mediana nacional: ${resultado['meta']['mediana_nacional']:,} COP")
    return resultado


def main():
    aqui = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Procesa la GEIH del DANE y genera geih_salarios.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python load_geih_salarios.py --geih_dir "C:/ruta/Febrero_2026.zip"
  python load_geih_salarios.py --geih_dir "data/GEIH/Febrero_2026.zip" --listar
""",
    )
    parser.add_argument("--geih_dir", default=str(aqui / "data" / "GEIH"),
                        help="Ruta al ZIP o carpeta del GEIH")
    parser.add_argument("--salida", default=str(aqui / "data" / "geih_salarios.json"))
    parser.add_argument("--periodo", default="Feb 2026")
    parser.add_argument("--listar", action="store_true",
                        help="Solo lista los archivos del ZIP/carpeta sin procesar")
    args = parser.parse_args()

    geih_path = Path(args.geih_dir)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}\n  PROCESADOR GEIH — Observatorio Laboral UniSabana\n{'='*55}")
    print(f"  Ruta: {geih_path}")

    if args.listar:
        if geih_path.suffix.lower() == ".zip" and geih_path.exists():
            with zipfile.ZipFile(geih_path) as z:
                for n in sorted(x for x in z.namelist() if not x.endswith("/")):
                    print(f"    {n}  ({z.getinfo(n).file_size/1024:.0f} KB)")
        else:
            print("  ⚠ Ruta no es un ZIP existente.")
        return

    if not geih_path.exists():
        # Sin GEIH: se guarda igual el JSON con solo los rangos SPE (siempre útiles).
        print(f"\n  ⚠ No se encontró: {geih_path}")
        print("  → Guardando JSON solo con rangos SPE (sin desglose GEIH).")
        resultado = {
            "meta": {"periodo": args.periodo,
                     "fuente": "SPE Colombia (GEIH no disponible)",
                     "n_ocupados": 0, "con_ingreso": 0, "mediana_nacional": None,
                     "nota": "Descarga el ZIP GEIH y pásalo con --geih_dir."},
            "por_cno_grupo": {}, "por_cno_subgrupo": {}, "por_nivel_educativo": {},
            "por_subgrupo_educacion": {},
            "spe_rangos": SPE_RANGOS_FIJOS, "tiene_geih": False,
        }
    else:
        resultado = procesar_geih(geih_path, periodo=args.periodo)

    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ Guardado en: {salida}")
    print(f"  • Tiene GEIH real : {'Sí' if resultado['tiene_geih'] else 'No — solo SPE'}")


if __name__ == "__main__":
    main()
