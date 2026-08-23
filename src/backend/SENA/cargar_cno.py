"""
cargar_cno.py — ETL del CNO 2025 del SENA (habilidades y conocimientos en español).

Descarga (o lee) el XLSX del Observatorio Laboral y Ocupacional del SENA y lo carga
en `sena_cno_ocupaciones` y `sena_cno_atributos` (ver migración 009).

POR QUÉ IMPORTA
Es el equivalente colombiano de O*NET: habilidades y conocimientos por ocupación,
oficiales, en español y llaveados por código CNO — el mismo que ya usa
`PROGRAMA_CNO`. Hasta ahora las skills venían de O*NET (EE.UU., inglés) y se
traducían a mano en `traducciones.py`.

Uso:
    python -m SENA.cargar_cno                 # descarga la versión vigente
    python -m SENA.cargar_cno --archivo X.xlsx
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

TABLA_OCUP = "sena_cno_ocupaciones"
TABLA_ATR = "sena_cno_atributos"

URL_CNO = "https://observatorio.sena.edu.co/Content/xls/cno/CNO_2025_(9-06-2026).xlsx"
# El servidor del SENA rechaza clientes sin User-Agent de navegador.
_CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; ObservatorioLaboralUniSabana/1.0)"}

# Hoja -> (tipo, columna del nombre, columna de la descripción).
# Se identifican por posición porque los encabezados son larguísimos
# ("Nombre de la habilidad - C.N.O.") y cambian entre versiones del archivo.
_HOJAS = {
    "Habilidades - C.N.O.": ("habilidad", 3, 4),
    "Conocimientos - C.N.O.": ("conocimiento", 3, 4),
    "Funciones - C.N.O.": ("funcion", 3, None),
    # Denominaciones tiene 4 columnas: el nombre del sinónimo va en la última.
    "Denominaciones - C.N.O.": ("denominacion", 3, None),
}

_LOTE = 500
_REINTENTOS = 4


def _texto(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).strip()
    return t or None


def _codigo(v: Any) -> str | None:
    """El código llega como número ('25.0') o texto; se normaliza a dígitos."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).strip()
    if t.endswith(".0"):
        t = t[:-2]
    return t or None


def _subir(tabla: str, filas: list[dict], conflicto: str) -> int:
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
                    print(f"   ⚠ lote {i // _LOTE + 1} de {tabla}: {str(e)[:120]}")
                else:
                    time.sleep(2 * intento)
    return subidas


def descargar(destino: Path) -> Path:
    """Baja el XLSX vigente del SENA (o reutiliza el que ya esté en disco)."""
    if destino.exists():
        print(f"  usando el archivo local: {destino.name}")
        return destino
    print(f"  descargando {URL_CNO} …")
    req = urllib.request.Request(URL_CNO, headers=_CABECERAS)
    with urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()) as r:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.read())
    print(f"  guardado: {destino.stat().st_size // 1024} KB")
    return destino


def cargar_ocupaciones(ruta: Path) -> int:
    """Hoja de ocupaciones + descripciones (se unen por código)."""
    d = pd.read_excel(ruta, sheet_name="Ocupaciones - C.N.O.")
    try:
        desc = pd.read_excel(ruta, sheet_name="Descripciones - C.N.O.")
        mapa_desc = {
            _codigo(r[0]): _texto(r[-1])
            for r in desc.itertuples(index=False, name=None)
        }
    except Exception:
        mapa_desc = {}

    filas = []
    for r in d.itertuples(index=False, name=None):
        cod = _codigo(r[0])
        nombre = _texto(r[1])
        if not cod or not nombre:
            continue
        filas.append({
            "codigo": cod,
            "nivel": len(cod),
            "nombre": nombre,
            "descripcion": mapa_desc.get(cod),
        })
    print(f"  Ocupaciones: {len(filas)}")
    return _subir(TABLA_OCUP, filas, "codigo")


def cargar_atributos(ruta: Path) -> int:
    """Habilidades, conocimientos, funciones y denominaciones."""
    disponibles = set(pd.ExcelFile(ruta).sheet_names)
    total = 0

    for hoja, (tipo, i_nombre, i_desc) in _HOJAS.items():
        if hoja not in disponibles:
            print(f"  (sin hoja '{hoja}')")
            continue
        d = pd.read_excel(ruta, sheet_name=hoja)
        cols = list(d.columns)

        filas = []
        vistos: set[tuple] = set()
        for r in d.itertuples(index=False, name=None):
            cod_ocup = _codigo(r[0])
            if not cod_ocup or i_nombre >= len(cols):
                continue
            # En 'Denominaciones' el nombre real es la última columna.
            nombre = _texto(r[i_nombre]) or _texto(r[-1])
            if not nombre:
                continue
            clave = (cod_ocup, tipo, nombre)
            if clave in vistos:
                continue  # la restricción UNIQUE es (ocupación, tipo, nombre)
            vistos.add(clave)
            filas.append({
                "codigo_ocupacion": cod_ocup,
                "nivel": len(cod_ocup),
                "tipo": tipo,
                "codigo": _codigo(r[2]) if len(cols) > 2 else None,
                "nombre": nombre,
                "descripcion": _texto(r[i_desc]) if i_desc is not None and i_desc < len(cols) else None,
            })

        subidas = _subir(TABLA_ATR, filas, "codigo_ocupacion,tipo,nombre")
        print(f"  {hoja:26} {subidas} filas ({tipo})")
        total += subidas
    return total


def main() -> None:
    aqui = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="Carga el CNO 2025 del SENA")
    p.add_argument("--archivo", default=str(aqui / "data" / "CNO_2025.xlsx"))
    args = p.parse_args()

    print(f"\n{'='*58}\n  CNO 2025 (SENA) — Observatorio Laboral UniSabana\n{'='*58}")
    ruta = descargar(Path(args.archivo))
    n_o = cargar_ocupaciones(ruta)
    n_a = cargar_atributos(ruta)
    print(f"\n  ✅ {n_o} ocupaciones y {n_a} atributos cargados.")


if __name__ == "__main__":
    main()
