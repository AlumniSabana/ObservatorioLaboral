"""
cargar_tendencias.py — ETL del `Anexo_tendencias` del SPE (serie mensual nacional).

Complementa a `cargar_anexos.py`: aquel carga la FOTO del periodo por ocupación y
territorio; este carga cómo se movió el mercado MES A MES a nivel nacional.

Es la primera serie temporal OBSERVADA de Colombia que entra al Observatorio: las
que había eran de Adzuna (mercados extranjeros) o derivadas de O*NET.

Uso:
    python -m SPE.cargar_tendencias "SPE/data/Anexo_tendencias_2023_ene-sep.xlsx"
"""

from __future__ import annotations

import argparse
import time
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

from Adzuna.adzuna_service import supabase

TABLA = "spe_tendencias"

# Hoja del anexo -> dimensión con la que se guarda.
_HOJAS = {
    "Ocupaciones": "ocupacion",
    "Competencias transversales": "transversal",
    "Competencias digitales": "digital",
}

# El anexo trae el mes escrito en español ("Octubre"), no numérico.
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_LOTE = 500
_REINTENTOS = 4


def _num_mes(valor: Any) -> int | None:
    """'Octubre' -> 10. Acepta también el número directo."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        n = int(valor)
        return n if 1 <= n <= 12 else None
    texto = "".join(
        c for c in unicodedata.normalize("NFD", str(valor).strip().lower())
        if unicodedata.category(c) != "Mn"
    )
    return _MESES.get(texto)


def _subir(filas: list[dict]) -> int:
    """Upsert por lotes, con reintentos ante cortes de red."""
    subidas = 0
    for i in range(0, len(filas), _LOTE):
        trozo = filas[i:i + _LOTE]
        for intento in range(1, _REINTENTOS + 1):
            try:
                supabase.table(TABLA).upsert(trozo, on_conflict="periodo,dimension,termino").execute()
                subidas += len(trozo)
                break
            except Exception as e:
                if intento == _REINTENTOS:
                    print(f"   ⚠ lote {i // _LOTE + 1}: {str(e)[:120]}")
                else:
                    time.sleep(2 * intento)
    return subidas


def cargar(ruta: Path, etiqueta: str) -> int:
    """Convierte las hojas (formato ancho) a filas por mes/término y las sube."""
    disponibles = set(pd.ExcelFile(ruta).sheet_names)
    total = 0

    for hoja, dimension in _HOJAS.items():
        if hoja not in disponibles:
            print(f"  (sin hoja '{hoja}')")
            continue

        d = pd.read_excel(ruta, sheet_name=hoja)
        columnas_valor = [c for c in d.columns if c not in ("Año", "Mes")]

        filas = []
        for r in d.to_dict("records"):
            mes = _num_mes(r.get("Mes"))
            anio = r.get("Año")
            if mes is None or pd.isna(anio):
                continue
            anio = int(anio)
            for termino in columnas_valor:
                valor = pd.to_numeric(r.get(termino), errors="coerce")
                if pd.isna(valor):
                    continue
                filas.append({
                    "periodo": f"{anio:04d}-{mes:02d}-01",
                    "anio": anio,
                    "mes": mes,
                    "dimension": dimension,
                    "termino": str(termino).strip(),
                    "valor": float(valor),
                    "fuente_anexo": etiqueta,
                })

        subidas = _subir(filas)
        print(f"  {hoja:30} {subidas} filas ({dimension})")
        total += subidas
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="Carga el Anexo_tendencias del SPE")
    p.add_argument("excel", help="Ruta a Anexo_tendencias.xlsx")
    p.add_argument("--etiqueta", default=None)
    args = p.parse_args()

    ruta = Path(args.excel)
    if not ruta.exists():
        raise SystemExit(f"No existe: {ruta}")

    print(f"\n{'='*58}\n  SERIE MENSUAL DEL SPE — Observatorio Laboral\n{'='*58}")
    n = cargar(ruta, args.etiqueta or ruta.stem)
    print(f"\n  ✅ {n} puntos de serie cargados.")


if __name__ == "__main__":
    main()
