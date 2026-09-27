"""
Semáforo de la cuota de SerpApi (Google Jobs).

QUÉ RESUELVE
------------
Google Jobs se recolecta vía SerpApi, cuyo plan gratuito da 250 búsquedas al
mes (1 página = 1 búsqueda) que se renuevan el día 19. Una corrida completa de
`procesar_vacantes_google` gasta hasta `SERPAPI_MAX_BUSQUEDAS` (240 por
defecto). Si el Admin pulsa "Actualizar histórico" con el cupo a medias, la
corrida sale PARCIAL y además quema lo que queda; y si el cupo está en cero,
SerpApi responde 429 a la primera y la corrida se aborta (ver
`google_jobs_service._buscar_pagina_google`). Este módulo le dice al Admin,
ANTES de pulsar, en qué situación está.

DE DÓNDE SALE EL DATO
---------------------
`GET https://serpapi.com/account.json?api_key=…` NO consume búsquedas (es el
endpoint de cuenta, no el de búsqueda). Devuelve, entre otros, verificado en
vivo el 2026-09-27:

    plan_searches_left      búsquedas del plan que quedan este ciclo
    searches_per_month      cupo mensual del plan (250 en el plan gratuito)
    this_month_usage        búsquedas ya gastadas en el ciclo
    extra_credits           créditos extra comprados (fuera del plan)
    total_searches_left     plan + extra
    plan_renewal_date       fecha en que se renueva el cupo (2026-10-19)

REGLA DEL SEMÁFORO (definida por el Tech Lead)
---------------------------------------------
Sea `restantes` = plan_searches_left, `presupuesto` = SERPAPI_MAX_BUSQUEDAS y
`dias_para_reset` = días hasta el próximo día 19.

    🟢 verde     restantes >= presupuesto         cabe una corrida completa
    🟡 amarillo  0 < restantes < presupuesto      la corrida sería parcial;
                                                  si dias_para_reset <= 2 se
                                                  sugiere esperar al reset
    🔴 rojo      restantes == 0, o la cuenta no responde y no hay estimación

Si la API de cuenta falla, se ESTIMA con el uso local: cada corrida de Google
Jobs anota cuántas búsquedas gastó (`registrar_uso_local`) en un archivo de
esta carpeta, y se restan del cupo mensual las anotadas desde el último día
19. La estimación se marca como tal (`estimado=True`): solo cuenta lo que
gastó ESTE backend, no otras herramientas que usen la misma clave.

Se muestran siempre los números (restantes/total, uso del mes, días para el
reset) y un texto de recomendación, para que la decisión sea del Admin.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

from config import SERPAPI_KEY, SERPAPI_MAX_BUSQUEDAS

URL_CUENTA = "https://serpapi.com/account.json"
TIMEOUT = 15

# Día del mes en que SerpApi renueva el cupo del plan (verificado contra
# `plan_renewal_date` de la cuenta real: 2026-10-19).
DIA_RESET = 19

# Cupo mensual que se asume si la API no responde y hay que estimar. El plan
# gratuito da 250; con otro plan, ajustar SERPAPI_BUSQUEDAS_MES en .env.
try:
    BUSQUEDAS_MES_DEFECTO = int(os.getenv("SERPAPI_BUSQUEDAS_MES", "250"))
except ValueError:
    BUSQUEDAS_MES_DEFECTO = 250

# Registro local de búsquedas gastadas por este backend (para la estimación).
# Ignorado por Git: es estado operativo, no código.
USO_LOCAL_PATH = Path(__file__).parent / "_uso_serpapi.json"

VERDE, AMARILLO, ROJO = "verde", "amarillo", "rojo"


def proximo_reset(hoy: date | None = None) -> date:
    """Próximo día 19. Si HOY es 19, el cupo se renovó hoy: el próximo es el del mes siguiente."""
    hoy = hoy or datetime.now(timezone.utc).date()
    if hoy.day < DIA_RESET:
        return hoy.replace(day=DIA_RESET)
    anio, mes = (hoy.year + 1, 1) if hoy.month == 12 else (hoy.year, hoy.month + 1)
    return date(anio, mes, DIA_RESET)


def ultimo_reset(hoy: date | None = None) -> date:
    """Día 19 más reciente (inicio del ciclo de facturación en curso)."""
    hoy = hoy or datetime.now(timezone.utc).date()
    if hoy.day >= DIA_RESET:
        return hoy.replace(day=DIA_RESET)
    anio, mes = (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)
    return date(anio, mes, DIA_RESET)


def consultar_cuenta(timeout: int = TIMEOUT) -> Dict[str, Any]:
    """Lee la cuenta de SerpApi. NO consume búsquedas. Lanza si falla."""
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY no configurada")
    r = requests.get(URL_CUENTA, params={"api_key": SERPAPI_KEY}, timeout=timeout)
    r.raise_for_status()
    datos = r.json()
    if "plan_searches_left" not in datos:
        raise RuntimeError(f"Respuesta de cuenta sin 'plan_searches_left': {list(datos)[:8]}")
    return datos


# ── Uso local (respaldo para estimar) ───────────────────────────────────────

def _leer_uso_local() -> List[Dict[str, Any]]:
    try:
        with open(USO_LOCAL_PATH, encoding="utf-8") as fh:
            return list(json.load(fh))
    except Exception:
        return []


def registrar_uso_local(busquedas: int, fuente: str = "google_jobs") -> None:
    """Anota búsquedas gastadas por una corrida (lo llama el orquestador)."""
    if busquedas <= 0:
        return
    registros = _leer_uso_local()
    registros.append({
        "fecha": datetime.now(timezone.utc).isoformat(),
        "busquedas": int(busquedas),
        "fuente": fuente,
    })
    # Solo interesa el ciclo actual y el anterior: lo demás es histórico muerto.
    corte = ultimo_reset().replace(day=1)
    registros = [r for r in registros if str(r.get("fecha", ""))[:10] >= corte.isoformat()]
    try:
        tmp = USO_LOCAL_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(registros, fh)
        os.replace(tmp, USO_LOCAL_PATH)
    except Exception:
        pass  # sin disco escribible, la estimación simplemente no existirá


def uso_local_ciclo(hoy: date | None = None) -> int | None:
    """Búsquedas anotadas localmente desde el último día 19. None si no hay registro."""
    registros = _leer_uso_local()
    if not registros:
        return None
    desde = ultimo_reset(hoy).isoformat()
    return sum(int(r.get("busquedas") or 0) for r in registros if str(r.get("fecha", ""))[:10] >= desde)


# ── Semáforo ────────────────────────────────────────────────────────────────

def _clasificar(restantes: int | None, presupuesto: int, dias: int, estimado: bool) -> tuple[str, str]:
    """Aplica la regla del Tech Lead. Devuelve (color, recomendación)."""
    if restantes is None:
        return ROJO, (
            "No se pudo leer la cuenta de SerpApi ni hay uso local para estimar. "
            "Revisa SERPAPI_KEY y la conectividad antes de recolectar Google Jobs."
        )
    aviso = " (cifra ESTIMADA con el uso local, no confirmada por SerpApi)" if estimado else ""
    if restantes <= 0:
        return ROJO, (
            f"Cupo mensual agotado{aviso}: Google Jobs respondería 429 y la corrida se abortaría. "
            f"Espera al reset del día {DIA_RESET} (faltan {dias} días)."
        )
    if restantes >= presupuesto:
        return VERDE, (
            f"Quedan {restantes} búsquedas{aviso}: cabe una corrida completa de Google Jobs "
            f"(presupuesto {presupuesto})."
        )
    texto = (
        f"Quedan {restantes} búsquedas{aviso}, menos que el presupuesto ({presupuesto}): "
        f"la recolección de Google Jobs saldría PARCIAL."
    )
    if dias <= 2:
        texto += f" El cupo se renueva en {dias} día(s): conviene esperar al reset."
    else:
        texto += f" El cupo se renueva en {dias} días; puedes correr parcial ahora o esperar."
    return AMARILLO, texto


def estado_cuota(presupuesto: int | None = None, hoy: date | None = None) -> Dict[str, Any]:
    """Estado completo del semáforo. Nunca lanza: si algo falla lo dice en `error`."""
    presupuesto = presupuesto if presupuesto is not None else SERPAPI_MAX_BUSQUEDAS
    hoy = hoy or datetime.now(timezone.utc).date()
    reset = proximo_reset(hoy)
    dias = (reset - hoy).days

    salida: Dict[str, Any] = {
        "presupuesto": presupuesto,
        "dia_reset": DIA_RESET,
        "fecha_reset": reset.isoformat(),
        "dias_para_reset": dias,
        "consultado_en": datetime.now(timezone.utc).isoformat(),
        "estimado": False,
        "fuente_dato": None,
        "restantes": None,
        "total": None,
        "uso_mes": None,
        "extra_credits": None,
        "total_con_extras": None,
        "plan": None,
        "fecha_renovacion_api": None,
        "error": None,
    }

    try:
        cuenta = consultar_cuenta()
        salida.update({
            "fuente_dato": "serpapi_api",
            "restantes": int(cuenta.get("plan_searches_left") or 0),
            "total": int(cuenta.get("searches_per_month") or 0),
            "uso_mes": int(cuenta.get("this_month_usage") or 0),
            "extra_credits": int(cuenta.get("extra_credits") or 0),
            "total_con_extras": int(cuenta.get("total_searches_left") or 0),
            "plan": cuenta.get("plan_name"),
            "fecha_renovacion_api": cuenta.get("plan_renewal_date"),
        })
        # Si SerpApi dice otra fecha de renovación, manda la suya.
        if cuenta.get("plan_renewal_date"):
            try:
                fecha_api = date.fromisoformat(str(cuenta["plan_renewal_date"])[:10])
                salida["fecha_reset"] = fecha_api.isoformat()
                salida["dias_para_reset"] = dias = max(0, (fecha_api - hoy).days)
            except ValueError:
                pass
    except Exception as e:
        salida["error"] = f"No se pudo consultar la cuenta de SerpApi: {e}"
        uso = uso_local_ciclo(hoy)
        if uso is not None:
            salida.update({
                "fuente_dato": "estimacion_local",
                "estimado": True,
                "total": BUSQUEDAS_MES_DEFECTO,
                "uso_mes": uso,
                "restantes": max(0, BUSQUEDAS_MES_DEFECTO - uso),
            })
        else:
            salida["fuente_dato"] = "ninguna"

    color, recomendacion = _clasificar(salida["restantes"], presupuesto, dias, salida["estimado"])
    salida["semaforo"] = color
    salida["recomendacion"] = recomendacion
    return salida
