"""
cargar_anexos.py — ETL de los anexos del SPE (ocupaciones y competencias).

Lee `Anexo_ocupaciones_competencias.xlsx` del Servicio Público de Empleo y lo
carga en `spe_ocupaciones` y `spe_competencias` (ver migración 007).

POR QUÉ ESTA FUENTE
Las skills del Observatorio eran DERIVADAS (O*NET normativo de EE.UU. × demanda
por programa). Estos anexos traen competencias OBSERVADAS en vacantes reales de
Colombia y en español, sobre ~1,8 millones de ofertas. Además su CIUO de 2 dígitos
es la misma taxonomía que el CNO que ya mapea cada programa, así que enchufa
directo sin inventar equivalencias.

FORMATO DE ORIGEN
Cada hoja de competencias viene en formato ANCHO: unas columnas identificadoras
(Mes, Departamento, CIUO, Ocupación) y una columna POR competencia con el número
de menciones. Aquí se convierten a formato largo (una fila por competencia), que
es lo que permite consultarlas y compararlas entre sí.

Uso:
    python -m SPE.cargar_anexos "ruta/Anexo_ocupaciones_competencias.xlsx" --anio 2023
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pandas as pd

from Adzuna.adzuna_service import supabase

TABLA_OCUP = "spe_ocupaciones"
TABLA_COMP = "spe_competencias"

# Columnas que identifican la fila (no son competencias) en las hojas anchas.
_COLS_ID = {"Categoria", "Mes", "Departamento", "Municipio", "Divipola",
            "CIUO 2 digitos", "Ocupación"}

# Hoja del anexo -> categoría con la que se guarda. Separar herramientas de
# competencias blandas es lo que permite luego mostrarlas por separado.
_HOJAS_COMPETENCIAS = {
    "Competencias transversales": "transversal",
    "Competencias digitales": "digital",
    "Conocimiento digital básico": "digital_basico",
    "Conocimiento en ofimática": "ofimatica",
    "Conocimiento en programas": "programa",
    "Lenguajes": "lenguaje",
    "Practicas y procesos": "practica",
    "Habilidades digitales": "habilidad_digital",
}

# Centinela para las vacantes que el SPE no clasificó (CIUO y Ocupación vacíos).
# Se guardan en vez de descartarse para que los totales del anexo reconcilien y
# se pueda decir cuántas ofertas quedaron sin clasificar. Ningún programa mapea a
# este código, así que nunca contaminan un ranking por programa.
CIUO_SIN_CLASIFICAR = "ND"

_LOTE = 500
_REINTENTOS = 4   # ante cortes de red al subir lotes grandes


def _periodo(anio: int, mes: Any) -> str | None:
    """(2023, 9) -> '2023-09-01'. None si el mes no es utilizable."""
    try:
        m = int(mes)
    except (TypeError, ValueError):
        return None
    return f"{anio:04d}-{m:02d}-01" if 1 <= m <= 12 else None


def _texto(v: Any) -> str | None:
    """
    Valor de texto listo para JSON, o None.

    Pandas devuelve NaN (un float) para las celdas vacías, y NaN NO es JSON
    válido: si se cuela en el lote, Supabase rechaza la petición ENTERA y se
    pierden las 500 filas de golpe. Esto fue exactamente lo que hizo desaparecer
    el 19,6% de las menciones en la primera carga.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    texto = str(v).strip()
    return texto or None


def _subir(tabla: str, filas: list[dict], conflicto: str) -> int:
    """
    Sube en lotes con upsert (reejecutar el ETL actualiza, no duplica).

    Reintenta cada lote: subir ~190k filas tarda varios minutos y un corte de red
    puntual tumbaba lotes enteros de 500 filas. En la primera carga eso hizo
    desaparecer el 19,6% de las menciones SIN que se notara, que es la peor forma
    de fallar: una base a medias parece completa.
    """
    subidas = 0
    fallidos = 0
    for i in range(0, len(filas), _LOTE):
        trozo = filas[i:i + _LOTE]
        for intento in range(1, _REINTENTOS + 1):
            try:
                supabase.table(tabla).upsert(trozo, on_conflict=conflicto).execute()
                subidas += len(trozo)
                break
            except Exception as e:
                if intento == _REINTENTOS:
                    fallidos += len(trozo)
                    print(f"   ⚠ lote {i // _LOTE + 1} de {tabla} tras {intento} intentos: {str(e)[:120]}")
                else:
                    time.sleep(2 * intento)  # espera creciente ante fallos de red
    if fallidos:
        # Que no pase inadvertido: un ETL a medias es peor que uno que falla.
        print(f"   ❌ {fallidos} filas NO se cargaron en {tabla}. Vuelve a ejecutar el ETL.")
    return subidas


def cargar_ocupaciones(ruta: Path, anio: int, etiqueta: str) -> int:
    """Hoja 'Ocupación': ofertas por mes, municipio y CIUO."""
    d = pd.read_excel(ruta, sheet_name="Ocupación")
    # Se accede por NOMBRE de columna (no por posición) para que un cambio de
    # orden en un anexo futuro no cargue los datos en el campo equivocado.
    col_ofertas = next((c for c in d.columns if "ofertas" in str(c).lower()), None)
    if col_ofertas is None:
        raise ValueError(f"No encuentro la columna de ofertas en 'Ocupación': {list(d.columns)}")

    filas = []
    for r in d.to_dict("records"):
        periodo = _periodo(anio, r.get("Mes"))
        if periodo is None:
            continue
        try:
            ciuo_txt = str(int(float(r.get("CIUO 2 digitos"))))
        except (TypeError, ValueError):
            ciuo_txt = CIUO_SIN_CLASIFICAR
        divipola = r.get("Divipola")
        filas.append({
            "periodo": periodo,
            "anio": anio,
            "mes": int(r["Mes"]),
            "departamento": _texto(r.get("Departamento")),
            "municipio": _texto(r.get("Municipio")),
            "divipola": str(int(divipola)) if pd.notna(divipola) else "0",
            "ciuo2": ciuo_txt,
            "ocupacion": _texto(r.get("Ocupación")),
            "ofertas": int(r.get(col_ofertas) or 0),
            "fuente_anexo": etiqueta,
        })
    print(f"  Ocupación: {len(filas)} filas")
    return _subir(TABLA_OCUP, filas, "periodo,divipola,ciuo2")


def cargar_competencias(ruta: Path, anio: int, etiqueta: str) -> int:
    """Todas las hojas de competencias, convertidas de formato ancho a largo."""
    total = 0
    disponibles = set(pd.ExcelFile(ruta).sheet_names)

    for hoja, categoria in _HOJAS_COMPETENCIAS.items():
        if hoja not in disponibles:
            print(f"  (sin hoja '{hoja}')")
            continue

        d = pd.read_excel(ruta, sheet_name=hoja)
        columnas_valor = [c for c in d.columns if c not in _COLS_ID]
        if not columnas_valor:
            continue

        # Ancho -> largo: una fila por (ocupación, competencia).
        largo = d.melt(
            id_vars=[c for c in d.columns if c in _COLS_ID],
            value_vars=columnas_valor,
            var_name="competencia",
            value_name="menciones",
        )
        # Solo interesa lo que se pidió al menos una vez.
        largo = largo[pd.to_numeric(largo["menciones"], errors="coerce").fillna(0) > 0]

        filas = []
        for r in largo.to_dict("records"):
            periodo = _periodo(anio, r.get("Mes"))
            if periodo is None:
                continue
            try:
                ciuo_txt = str(int(float(r.get("CIUO 2 digitos"))))
            except (TypeError, ValueError):
                ciuo_txt = CIUO_SIN_CLASIFICAR
            filas.append({
                "periodo": periodo,
                "anio": anio,
                "mes": int(r["Mes"]),
                # El anexo deja el departamento vacío en los totales nacionales.
                "departamento": _texto(r.get("Departamento")) or "NACIONAL",
                "ciuo2": ciuo_txt,
                "ocupacion": _texto(r.get("Ocupación")),
                "categoria": categoria,
                "competencia": str(r["competencia"]).strip(),
                "menciones": int(r["menciones"]),
                "fuente_anexo": etiqueta,
            })

        subidas = _subir(TABLA_COMP, filas, "periodo,departamento,ciuo2,categoria,competencia")
        print(f"  {hoja:32} {subidas} filas ({categoria})")
        total += subidas
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="Carga los anexos del SPE en Supabase")
    p.add_argument("excel", help="Ruta a Anexo_ocupaciones_competencias.xlsx")
    p.add_argument("--anio", type=int, required=True, help="Año de los datos (ej. 2023)")
    p.add_argument("--etiqueta", default=None, help="Identificador del anexo (ej. 'ene-sep 2023')")
    args = p.parse_args()

    ruta = Path(args.excel)
    if not ruta.exists():
        raise SystemExit(f"No existe: {ruta}")
    etiqueta = args.etiqueta or ruta.stem

    print(f"\n{'='*58}\n  ANEXOS DEL SPE — Observatorio Laboral UniSabana\n{'='*58}")
    print(f"  Archivo: {ruta.name} | año: {args.anio}\n")

    n_ocup = cargar_ocupaciones(ruta, args.anio, etiqueta)
    n_comp = cargar_competencias(ruta, args.anio, etiqueta)

    print(f"\n  ✅ {n_ocup} filas de ocupaciones y {n_comp} de competencias cargadas.")


if __name__ == "__main__":
    main()
