"""
trm_service.py — tasas de cambio para convertir salarios de Adzuna (USD, GBP,
CAD, MXN, EUR) a COP.

Por qué hace falta: Adzuna publica el salario en la moneda local de cada
mercado (dólares en EE.UU., libras en Reino Unido, etc.), y para comparar ese
número contra el salario de GEIH (que sí está en pesos) hay que convertir.

Fuente: exchangerate-api.com, API pública sin llave (tier gratuito). Se cachea
en memoria por varias horas: esto es para comparar el ORDEN DE MAGNITUD de un
salario, no una operación financiera, así que no hace falta la tasa exacta del
minuto — y evita golpear la API en cada carga de la página.
"""

from __future__ import annotations

import time
from typing import Any

import requests

_URL = "https://api.exchangerate-api.com/v4/latest/USD"
# 12 horas: suficiente para no pegarle a la API en cada request, sin arrastrar
# una tasa de días atrás si alguien deja el backend corriendo mucho tiempo.
_TTL_SEGUNDOS = 12 * 3600

_cache: dict[str, Any] = {"ts": 0.0, "tasas": None, "fecha": None}

# Moneda local de cada mercado de Adzuna que sí trae salario estructurado.
# Google Jobs (co) y LinkedIn (co_li) no aportan aquí: no tienen salario
# estructurado (Google Jobs trae `salary_raw` como texto libre; LinkedIn no
# trae salario en absoluto).
PAIS_MONEDA = {"us": "USD", "gb": "GBP", "ca": "CAD", "mx": "MXN", "es": "EUR"}


def tasas_a_cop() -> dict[str, float] | None:
    """{'USD': cop_por_usd, 'GBP': cop_por_gbp, ...} o None si nunca se pudo obtener.

    Si la API falla pero ya había una tasa en caché (aunque esté vencida), se
    devuelve esa: mejor una TRM de hace un rato que no mostrar nada.
    """
    ahora = time.time()
    if _cache["tasas"] is not None and ahora - _cache["ts"] < _TTL_SEGUNDOS:
        return _cache["tasas"]
    try:
        r = requests.get(_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        rates = data["rates"]
        cop_por_usd = rates["COP"]
        # `rates[X]` viene como "unidades de X por 1 USD" (base=USD), así que
        # COP por unidad de X = (COP por USD) / (unidades de X por USD).
        tasas = {moneda: cop_por_usd / rates[moneda] for moneda in ("GBP", "CAD", "MXN", "EUR")}
        tasas["USD"] = cop_por_usd
        _cache.update(ts=ahora, tasas=tasas, fecha=data.get("date"))
        return tasas
    except Exception as e:
        print(f"   [!] Error obteniendo TRM ({_URL}): {e}")
        return _cache["tasas"]


def fecha_tasas() -> str | None:
    """Fecha de la TRM actualmente en caché (None si nunca se obtuvo ninguna)."""
    return _cache.get("fecha")
