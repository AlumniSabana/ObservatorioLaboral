"""
contexto_service.py — resumen factual del Observatorio para el asistente (chatbot).

El chatbot de "Empresas y cultura" responde sobre estructura y cultura
organizacional, clima laboral, ascensos y Great Place to Work. El Observatorio NO
mide cultura ni clima: lo que SÍ tiene son datos duros de mercado (qué empresas
contratan, en qué sectores, con qué salarios y para qué programas).

Este módulo arma ese "lo que sí sabemos" en un texto compacto que se le entrega a
Claude como contexto. La regla del asistente (ver src/app/api/chat/route.ts) es:
usar PRIMERO estos datos —son reales y verificables— y, si la pregunta va más allá
(p. ej. el puesto exacto de una empresa en el ranking GPTW), responder con
conocimiento general DECLARANDO que no proviene del Observatorio y sin inventar
cifras ni posiciones.

Se sirve como texto plano (no JSON) porque su destino es un prompt.
"""

from __future__ import annotations

from typing import Any

from Tendencias.demanda_actual import demanda_actual
from Tendencias.tendencias_service import TODOS

# Todos los mercados con datos históricos (Adzuna 5 países + Google Jobs Colombia).
_PAISES = ["us", "gb", "ca", "mx", "es", "co"]
_TOP = 20


def _lista(items: list[dict], etiqueta: str = "label") -> str:
    return ", ".join(f"{it[etiqueta]} ({it['count']})" for it in items) or "sin datos"


def _bloque_salarios() -> str:
    """Salario mediano mensual en COP por programa (GEIH-DANE)."""
    try:
        from Salarios.salarios_service import programas_disponibles, salario_por_programa
    except Exception:
        return "No disponible."

    filas = []
    for prog in programas_disponibles():
        try:
            info = salario_por_programa(prog)
        except Exception:
            continue
        k = info.get("kpis")
        if not k:
            continue
        cno = (info.get("cno") or {}).get("nombre", "")
        filas.append(f"- {prog}: mediana ${k['mediana']:,} COP "
                     f"(p25 ${k['p25']:,} – p75 ${k['p75']:,}); grupo ocupacional: {cno}")
    return "\n".join(filas) if filas else "No disponible."


def contexto_observatorio() -> str:
    """Texto compacto con TODO lo que el Observatorio sabe y es relevante al chat."""
    try:
        d = demanda_actual(TODOS, TODOS, _PAISES, _TOP)
    except Exception:
        d = {"cargos": [], "sectores": [], "empresas": [], "programas": [],
             "meta": {"total": 0}}

    total = d.get("meta", {}).get("total", 0)

    return f"""DATOS REALES DEL OBSERVATORIO LABORAL (Alumni, Universidad de La Sabana)
Muestra: {total:,} vacantes recolectadas de Adzuna (EE.UU., Reino Unido, Canadá,
México, España) y Google Jobs (Colombia). Son vacantes publicadas, no encuestas.

EMPRESAS QUE MÁS CONTRATAN (por número de vacantes en la muestra):
{_lista(d.get("empresas", []))}

SECTORES CON MÁS CONTRATACIÓN:
{_lista(d.get("sectores", []))}

CARGOS MÁS DEMANDADOS:
{_lista(d.get("cargos", []))}

PROGRAMAS ACADÉMICOS CON MÁS VACANTES ASOCIADAS:
{_lista(d.get("programas", []))}

SALARIOS EN COLOMBIA POR PROGRAMA (GEIH - DANE, mediana mensual en COP):
{_bloque_salarios()}

LÍMITES DE ESTOS DATOS (importante, no los contradigas):
- El Observatorio NO mide cultura organizacional, clima laboral, satisfacción de
  empleados, políticas internas ni tendencias de ascensos dentro de las empresas.
- El Observatorio NO tiene el ranking Great Place to Work (GPTW) ni sus puntajes.
- Las cifras de empresas/sectores/cargos son agregados de los más frecuentes en la
  muestra, no el total del mercado.
- Los salarios provienen de la encuesta GEIH del DANE por ocupación, no por empresa.
"""


def resumen_contexto() -> dict[str, Any]:
    """Payload del endpoint: el texto de contexto y su tamaño aproximado."""
    texto = contexto_observatorio()
    return {"contexto": texto, "caracteres": len(texto)}
