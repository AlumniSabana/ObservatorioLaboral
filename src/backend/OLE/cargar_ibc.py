"""
cargar_ibc.py — ETL del Observatorio Laboral para la Educación (OLE, MinEducación).

Carga la Base IBC en `ole_ibc_sabana` y `ole_ibc_nacional` (ver migración 010).

QUÉ TRAE LA FUENTE
786.458 filas con el conteo de graduados por (IES, programa SNIES, nivel de
formación, sexo, año de grado, RANGO de ingreso). El ingreso viene en 7 bandas
de SMMLV, no en pesos — ver la nota de la migración 010.

Uso:
    python -m OLE.cargar_ibc                  # descarga si hace falta
    python -m OLE.cargar_ibc --archivo X.xlsx
"""

from __future__ import annotations

import argparse
import ssl
import time
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from Adzuna.adzuna_service import supabase

TABLA_SABANA = "ole_ibc_sabana"
TABLA_NACIONAL = "ole_ibc_nacional"

# Ojo: el portal del OLE sirve por HTTP sin TLS en la raíz, pero los recursos de
# /1769/ sí responden por HTTPS. Se usa HTTPS a propósito.
URL_BASE_IBC = "https://ole.mineducacion.gov.co/1769/articles-425926_recurso_1.xlsx"
_CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; ObservatorioLaboralUniSabana/1.0)"}

HOJA = "Base_IBC_2023"
# El XLSX abre con 8 filas de banner institucional antes de los encabezados.
FILA_ENCABEZADO = 8
ANIO_CORTE = 2023

IES_SABANA = "SABANA"

_LOTE = 500
_REINTENTOS = 4


def _entero(v: Any) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _texto(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).strip()
    return t or None


def _subir(tabla: str, filas: list[dict], conflicto: str) -> int:
    """Sube por lotes con reintentos. La red se cae a mitad de cargas largas y
    sin reintentos la pérdida es silenciosa (ya pasó con los anexos del SPE)."""
    # Si dos filas comparten la clave del upsert, Postgres rechaza el LOTE
    # COMPLETO, no solo la fila repetida. Se avisa antes de subir: un fallo así
    # se lee como "cargó casi todo" cuando en realidad faltan 500 filas.
    claves = [tuple(f.get(c) for c in conflicto.split(",")) for f in filas]
    repetidas = len(claves) - len(set(claves))
    if repetidas:
        print(f"   ⚠ {repetidas} filas repiten la clave ({conflicto}) — se caerán sus lotes")

    subidas = 0
    for i in range(0, len(filas), _LOTE):
        trozo = filas[i:i + _LOTE]
        for intento in range(1, _REINTENTOS + 1):
            try:
                supabase.table(tabla).upsert(trozo, on_conflict=conflicto).execute()
                subidas += len(trozo)
                break
            except Exception as e:
                if intento == _REINTENTOS:
                    print(f"   ⚠ lote {i // _LOTE + 1} de {tabla}: {str(e)[:140]}")
                else:
                    time.sleep(2 * intento)
        if (i // _LOTE) % 20 == 0 and i:
            print(f"   … {subidas}/{len(filas)}")
    return subidas


def descargar(destino: Path) -> Path:
    if destino.exists():
        print(f"  usando el archivo local: {destino.name}")
        return destino
    print(f"  descargando {URL_BASE_IBC} (~48 MB) …")
    req = urllib.request.Request(URL_BASE_IBC, headers=_CABECERAS)
    with urllib.request.urlopen(req, timeout=900, context=ssl.create_default_context()) as r:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.read())
    print(f"  guardado: {destino.stat().st_size // 1024 // 1024} MB")
    return destino


# Columnas de texto que forman parte de alguna clave única. La fuente trae
# variantes con espacios de sobra ('ADMINISTRACION DE EMPRESAS ' junto a
# 'ADMINISTRACION DE EMPRESAS'), que pandas agrupa por separado pero Postgres ve
# como la MISMA fila: el lote entero se caía con "ON CONFLICT ... cannot affect
# row a second time" y se perdían 500 filas de golpe. Se normaliza antes de
# agrupar, no al escribir.
_COLS_CLAVE = [
    "PROGRAMA ACADÉMICO", "NIVEL DE FORMACIÓN", "INGRESO", "SEXO",
    "INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)",
]


def leer(ruta: Path) -> pd.DataFrame:
    d = pd.read_excel(ruta, sheet_name=HOJA, header=FILA_ENCABEZADO)
    for c in _COLS_CLAVE:
        if c in d.columns:
            # \s+ y no strip(): también hay dobles espacios interiores.
            d[c] = d[c].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    print(f"  leídas {len(d):,} filas · {int(d['GRADUADOS'].sum()):,} graduados")
    return d


def cargar_sabana(d: pd.DataFrame) -> int:
    """Detalle completo de La Sabana: se guarda tal cual, sin agregar."""
    sab = d[d["INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)"].str.contains(
        IES_SABANA, case=False, na=False)]
    if sab.empty:
        print("  ⚠ no se encontró La Sabana en el archivo")
        return 0

    g = sab.groupby(
        ["CÓDIGO SNIES DEL PROGRAMA", "PROGRAMA ACADÉMICO", "NIVEL DE FORMACIÓN",
         "SEXO", "AÑO DE GRADO", "INGRESO"], dropna=False,
    )["GRADUADOS"].sum().reset_index()

    filas = []
    for r in g.itertuples(index=False, name=None):
        cod, prog, nivel, sexo, anio, rango, grad = r
        if not _texto(prog) or not _texto(nivel) or not _texto(rango):
            continue
        filas.append({
            "codigo_snies": _entero(cod),
            "programa": _texto(prog),
            "nivel_formacion": _texto(nivel),
            # `sexo` entra en la clave única; NULL rompería el upsert en Postgres
            # (NULL != NULL), así que los vacíos van con centinela explícito.
            "sexo": _texto(sexo) or "Sin especificar",
            "anio_grado": _entero(anio),
            "rango": _texto(rango),
            "graduados": _entero(grad) or 0,
            "anio_corte": ANIO_CORTE,
        })

    print(f"  La Sabana: {len(filas)} filas · "
          f"{int(sab['GRADUADOS'].sum()):,} graduados · "
          f"{sab['PROGRAMA ACADÉMICO'].nunique()} programas")
    return _subir(TABLA_SABANA, filas,
                  "codigo_snies,nivel_formacion,sexo,anio_grado,rango,anio_corte")


def cargar_nacional(d: pd.DataFrame) -> int:
    """
    Referencia del país agregada por NOMBRE de programa.

    Se agrega por nombre y no por código SNIES porque cada institución registra
    su propio código para el mismo programa: el código no compara entre IES.
    """
    g = d.groupby(["PROGRAMA ACADÉMICO", "NIVEL DE FORMACIÓN", "INGRESO"], dropna=False).agg(
        graduados=("GRADUADOS", "sum"),
        # Cuenta CÓDIGOS de institución, no nombres: una universidad con varias
        # seccionales aporta varios códigos. Es "sedes que lo ofrecen", que para
        # medir con cuánta oferta se compara el programa es lo que interesa.
        n_ies=("CÓDIGO DE LA INSTITUCIÓN", "nunique"),
    ).reset_index()

    filas = []
    for r in g.itertuples(index=False, name=None):
        prog, nivel, rango, grad, n_ies = r
        if not _texto(prog) or not _texto(nivel) or not _texto(rango):
            continue
        filas.append({
            "programa": _texto(prog),
            "nivel_formacion": _texto(nivel),
            "rango": _texto(rango),
            "graduados": _entero(grad) or 0,
            "n_ies": _entero(n_ies),
            "anio_corte": ANIO_CORTE,
        })

    print(f"  Nacional: {len(filas)} filas agregadas")
    return _subir(TABLA_NACIONAL, filas, "programa,nivel_formacion,rango,anio_corte")


def main() -> None:
    aqui = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="Carga la Base IBC del OLE")
    p.add_argument("--archivo", default=str(aqui / "data" / "base_ibc_2023.xlsx"))
    p.add_argument("--solo", choices=["sabana", "nacional"],
                   help="cargar solo una de las dos tablas")
    args = p.parse_args()

    print(f"\n{'='*62}\n  OLE — Ingreso de graduados (MinEducación, corte {ANIO_CORTE})\n{'='*62}")
    d = leer(descargar(Path(args.archivo)))

    n_s = cargar_sabana(d) if args.solo != "nacional" else 0
    n_n = cargar_nacional(d) if args.solo != "sabana" else 0
    print(f"\n  ✅ {n_s} filas de La Sabana y {n_n} nacionales cargadas.")


if __name__ == "__main__":
    main()
