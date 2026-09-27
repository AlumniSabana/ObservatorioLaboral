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

PERSISTENCIA: cada insight generado se guarda en `insights_generados`
(migración 012, vía Informes/insights_repo.py) con tipo 'individual', porque la
vista de Usuario de /informes lo lee después en modo solo lectura. Si la tabla
no existe, el texto se devuelve igual con `persistido: false`.

`llamar_gemini()` es la única función de este proyecto que habla con la API de
Gemini desde el backend; insights_conjuntos.py la reutiliza en vez de duplicar
el manejo de cuota, errores y respuestas vacías.
"""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from Adzuna.adzuna_service import supabase
from config import GEMINI_API_KEY
from Informes import insights_repo
from Informes.informes_service import TABLA_INFORMES, TABLA_OBS, tablas_disponibles
from Informes.power_skills import clasificar_habilidad

MODELO = "gemini-3.6-flash"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"

# Reintentos ante 503 UNAVAILABLE (ver llamar_gemini). Pocos y cortos: el
# endpoint es síncrono y el usuario está esperando con un spinner.
_REINTENTOS_503 = 2
_ESPERA_503_SEG = 4

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


def llamar_gemini(
    system_prompt: str,
    texto_usuario: str,
    max_tokens: int = 8192,
    json_mode: bool = False,
    timeout: int = 90,
) -> str:
    """
    Una llamada síncrona a Gemini (REST) y el texto de la respuesta.

    `json_mode=True` pide `responseMimeType: application/json`, que obliga al
    modelo a devolver JSON válido — lo usan los candidatos a insights conjuntos,
    donde hay que parsear la salida en vez de mostrarla.

    Lanza RuntimeError si falta la API key, si se agotó la cuota o si la
    respuesta viene vacía/bloqueada. No captura nada más: el endpoint decide el
    código HTTP.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY no está configurada en el backend (src/backend/.env)."
        )

    generation: dict[str, Any] = {"maxOutputTokens": max_tokens}
    if json_mode:
        generation["responseMimeType"] = "application/json"

    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": texto_usuario}]}],
        "generationConfig": generation,
    }

    # Un 503 UNAVAILABLE ("high demand") es transitorio y frecuente en horas
    # pico: se reintenta un par de veces con espera creciente antes de fallar.
    # La cuota agotada (429) NO se reintenta: repetir solo empeora el problema.
    for intento in range(_REINTENTOS_503 + 1):
        r = requests.post(_URL, params={"key": GEMINI_API_KEY}, json=body, timeout=timeout)
        if r.ok:
            break
        detalle = r.text[:500]
        transitorio = r.status_code == 503 or "UNAVAILABLE" in detalle
        if transitorio and intento < _REINTENTOS_503:
            time.sleep(_ESPERA_503_SEG * (intento + 1))
            continue
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
    return texto


def parsear_json_modelo(texto: str) -> Any:
    """
    JSON de una respuesta del modelo, tolerando el envoltorio ```json ... ```
    que a veces añade aunque se pida JSON puro. Lanza ValueError si no parsea.
    """
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.strip("`")
        if limpio.lower().startswith("json"):
            limpio = limpio[4:]
    try:
        return json.loads(limpio)
    except json.JSONDecodeError as e:
        raise ValueError(f"El modelo no devolvió JSON válido: {e}") from e


def titulo_para(informes: list[dict[str, Any]], prefijo: str) -> str:
    """'Insights: Coursera 2025 · WEF 2026' — etiqueta corta y estable para listar."""
    return f"{prefijo}: " + " · ".join(
        f"{i['editor']} {i['anio_referencia']}" for i in informes
    )


def generar_insights(informe_ids: list[str], creado_por: str | None = None) -> dict[str, Any]:
    """Genera (síncronamente) el informe de insights con Gemini y lo persiste.

    Lanza ValueError si no hay ningún informe VALIDADO entre los ids pedidos, o
    RuntimeError si falta la API key o Gemini responde con error.
    """
    informes = _obtener_informes_validados(informe_ids)
    if not informes:
        raise ValueError(
            "Ninguno de los informes indicados existe y está validado. "
            "Solo se pueden usar informes en estado 'validado'."
        )

    encontrados = {i["id"] for i in informes}
    omitidos = [i for i in informe_ids if i not in encontrados]

    prompt_datos = _armar_prompt(informes)
    texto = llamar_gemini(
        SYSTEM_PROMPT, f"Datos de los informes seleccionados:\n\n{prompt_datos}"
    )

    # Se guarda DESPUÉS de tener el texto: si Gemini falla no queda basura.
    guardado = insights_repo.guardar(
        tipo=insights_repo.TIPO_INDIVIDUAL,
        informe_ids=[i["id"] for i in informes],
        titulo=titulo_para(informes, "Insights"),
        contenido=texto,
        modelo=MODELO,
        informes=informes,
        creado_por=creado_por,
    )

    return {
        "texto": texto,
        "informes": [{
            "id": i["id"], "titulo": i["titulo"], "editor": i["editor"],
            "anio_referencia": i["anio_referencia"], "antiguo": i["antiguo"],
        } for i in informes],
        "omitidos": omitidos,
        "persistido": guardado is not None,
        "insight_id": guardado["id"] if guardado else None,
        "aviso": None if guardado else insights_repo.AVISO_SIN_TABLA,
    }
