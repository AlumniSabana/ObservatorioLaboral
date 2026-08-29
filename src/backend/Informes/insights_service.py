"""
insights_service.py — informe de insights (Gemini) sobre 1+ informes YA
INGERIDOS Y VALIDADOS.

Distinto del "Lector de documentos" (Documentos/document_service.py, con
Claude): aquel sube un PDF nuevo y efímero, sin guardar nada. Esto opera sobre
informes que YA viven en la tabla `informes` (con sus `informes_observaciones`
verificadas), y por eso NO vuelve a leer el PDF: arma el prompt con los datos
ya extraídos y auditados (skill, métrica, posición, página, cita), que es
exactamente lo que ya se le muestra al humano que los validó.

Usa Gemini (REST, sin SDK) porque es el modelo que este proyecto ya usa para el
asistente de "Empresas y cultura" (ver src/app/api/chat/route.ts) — se reutiliza
la misma variable de entorno GEMINI_API_KEY.

Solo acepta informes en estado 'validado': un borrador no ha pasado el control
humano de `informe_extractor.py` y no debería alimentar ningún reporte, ni
siquiera uno narrativo.
"""

from __future__ import annotations

from typing import Any

import requests

from Adzuna.adzuna_service import supabase
from config import GEMINI_API_KEY
from Informes.informes_service import TABLA_INFORMES, TABLA_OBS, tablas_disponibles
from Informes.power_skills import clasificar_habilidad

MODELO = "gemini-3.6-flash"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"

SYSTEM_PROMPT = """
Eres un analista experto del Observatorio Laboral de Alumni Sabana. Se te entregan
los datos YA EXTRAÍDOS Y VERIFICADOS de uno o más informes de mercado laboral
(cada skill trae su posición dentro del informe, su página y una cita literal del
documento). Tu tarea es escribir un INFORME DE INSIGHTS que ayude a un lector no
técnico a entender qué dicen esos documentos y qué implica para la empleabilidad.

Normas obligatorias:
- Básate ÚNICAMENTE en los datos que se te dan abajo. No inventes cifras, skills
  ni afirmaciones que no estén respaldadas por ellos.
- Cuando cites una cifra o una skill concreta, indica de qué informe viene.
- Si se te dan VARIOS informes, dedica una sección a comparar coincidencias y
  diferencias entre ellos (qué skills aparecen en más de uno, cuáles son propias
  de un solo informe, si hay contradicciones).
- Distingue siempre "Habilidades técnicas" (herramientas, tecnologías, dominios
  de conocimiento) de "Power Skills" (comunicación, liderazgo, adaptabilidad y
  demás competencias interpersonales/de autogestión) — esa etiqueta ya viene
  calculada en los datos, úsala tal cual.
- Un informe de hace más de 2 años puede estar desactualizado: si `antiguo` es
  verdadero para alguno, dilo explícitamente al lector.
- Recuerda que estas cifras son DECLARADAS por el editor del informe (Coursera,
  WEF, etc.), no medidas por el Observatorio: no las presentes como si fueran
  datos propios del Observatorio.
- Responde siempre en español, claro y profesional, fácil de leer a la primera.
- Formato Markdown: usa encabezados (##), negritas y listas. Si usas una tabla,
  escribe cada fila en su propia línea (incluida la fila separadora
  | --- | --- |) y prefiere tablas de pocas columnas.

Estructura sugerida (adáptala si un solo informe no da para todas las secciones):
## Resumen ejecutivo
## Habilidades técnicas destacadas
## Power Skills destacadas
## Coincidencias y diferencias entre informes (solo si hay 2+)
## Qué implica para la empleabilidad
""".strip()


def _obtener_informes_validados(informe_ids: list[str]) -> list[dict[str, Any]]:
    """Metadatos + observaciones de los informes pedidos, filtrando a validados.

    Devuelve solo los que existen Y están validados. El llamador decide qué
    hacer si faltan algunos (ver generar_insights).
    """
    if not tablas_disponibles() or not informe_ids:
        return []

    metas = (
        supabase.table(TABLA_INFORMES).select("*")
        .in_("id", informe_ids).eq("estado", "validado")
        .execute().data
    ) or []
    if not metas:
        return []

    ids_validos = [m["id"] for m in metas]
    obs = (
        supabase.table(TABLA_OBS).select("*")
        .in_("informe_id", ids_validos).eq("dimension", "skill")
        .order("posicion")
        .execute().data
    ) or []

    por_informe: dict[str, list[dict]] = {i: [] for i in ids_validos}
    for o in obs:
        por_informe.setdefault(o["informe_id"], []).append(o)

    from datetime import date
    anio_actual = date.today().year

    return [{
        **meta,
        "antiguo": (anio_actual - meta["anio_referencia"]) > 2,
        "observaciones": por_informe.get(meta["id"], []),
    } for meta in metas]


def _armar_prompt(informes: list[dict[str, Any]]) -> str:
    """Texto estructurado con los datos de cada informe, para el turno de usuario."""
    bloques = []
    for inf in informes:
        obs = inf["observaciones"]
        lineas_skills = []
        for o in obs:
            termino = o.get("termino") or o["termino_original"]
            cat = clasificar_habilidad(termino)
            partes = [f"- {termino} ({cat})"]
            if o.get("posicion") is not None:
                partes.append(f"posición #{o['posicion']}")
            if o.get("valor") is not None:
                partes.append(f"valor {o['valor']} ({o.get('metrica', '')})")
            if o.get("pagina") is not None:
                partes.append(f"pág. {o['pagina']}")
            if o.get("cita"):
                partes.append(f'cita: "{o["cita"][:200]}"')
            lineas_skills.append(", ".join(partes))

        bloques.append(
            f"### Informe: {inf['editor']} — {inf['titulo']} ({inf['anio_referencia']})\n"
            f"- Cobertura: {inf.get('cobertura') or 'global'}\n"
            f"- Universo medido: {inf.get('universo') or 'no especificado'}\n"
            f"- Antiguo (>2 años): {'sí' if inf['antiguo'] else 'no'}\n"
            f"- Total de skills extraídas: {len(obs)}\n"
            f"- Skills (orden = posición en el informe):\n" + "\n".join(lineas_skills)
        )
    return "\n\n".join(bloques)


def generar_insights(informe_ids: list[str]) -> dict[str, Any]:
    """Genera (síncronamente) el informe de insights con Gemini.

    Lanza ValueError si no hay ningún informe VALIDADO entre los ids pedidos, o
    RuntimeError si falta la API key o Gemini responde con error.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY no está configurada en el backend (src/backend/.env)."
        )

    informes = _obtener_informes_validados(informe_ids)
    if not informes:
        raise ValueError(
            "Ninguno de los informes indicados existe y está validado. "
            "Solo se pueden usar informes en estado 'validado'."
        )

    encontrados = {i["id"] for i in informes}
    omitidos = [i for i in informe_ids if i not in encontrados]

    prompt_datos = _armar_prompt(informes)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{
            "role": "user",
            "parts": [{"text": f"Datos de los informes seleccionados:\n\n{prompt_datos}"}],
        }],
        "generationConfig": {"maxOutputTokens": 8192},
    }

    r = requests.post(_URL, params={"key": GEMINI_API_KEY}, json=body, timeout=60)
    if not r.ok:
        detalle = r.text[:500]
        sin_cuota = r.status_code == 429 or "RESOURCE_EXHAUSTED" in detalle
        if sin_cuota:
            raise RuntimeError(
                "Se agotó la cuota de la API de Gemini. Revisa el plan en Google AI Studio."
            )
        raise RuntimeError(f"Gemini respondió {r.status_code}: {detalle}")

    data = r.json()
    candidatos = data.get("candidates") or []
    partes = candidatos[0].get("content", {}).get("parts", []) if candidatos else []
    texto = "".join(p.get("text", "") for p in partes).strip()
    if not texto:
        raise RuntimeError("Gemini no devolvió texto (respuesta vacía o bloqueada).")

    return {
        "texto": texto,
        "informes": [{
            "id": i["id"], "titulo": i["titulo"], "editor": i["editor"],
            "anio_referencia": i["anio_referencia"], "antiguo": i["antiguo"],
        } for i in informes],
        "omitidos": omitidos,
    }
