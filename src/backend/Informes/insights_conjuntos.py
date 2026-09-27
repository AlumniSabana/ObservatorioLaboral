"""
insights_conjuntos.py — "Insights Conjuntos": detectar grupos de informes
VALIDADOS afines y sintetizarlos en un solo análisis (Gemini).

Distinto del "Informe de insights" de insights_service.py: allí el Admin marca
a mano qué informes quiere analizar. Aquí la IA PROPONE los grupos y explica
por qué van juntos, y el Admin solo confirma cuál generar.

DOS PASOS, POR DISEÑO
1. `candidatos()` — HÍBRIDO determinista + IA. Primero se calcula en Python el
   solapamiento de skills entre cada par de informes validados (Jaccard sobre
   los términos canónicos, la misma base que `comparativa_informes()` y
   `contraste()`). Solo ENTONCES se le pasa a Gemini ese resumen (pares,
   afinidad, skills compartidas y exclusivas) para que agrupe y redacte el
   motivo en una frase. Así el modelo no puede "inventar" afinidad: trabaja
   sobre cifras ya calculadas, y si falla o devuelve algo inválido hay un
   agrupamiento heurístico de respaldo con los mismos datos.
2. `generar_conjunto(ids)` — prompt propio, distinto del individual: pide
   comparar y SINTETIZAR (convergencias, divergencias, evolución temporal,
   implicaciones para los programas de La Sabana), no describir cada informe
   por separado. Se persiste con tipo 'conjunto' (migración 012) porque la
   vista de Usuario lo muestra en solo lectura.

Ambos operan solo sobre informes 'validado', por la misma razón que el resto
del módulo: un borrador no ha pasado el control humano.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from Adzuna.adzuna_service import supabase
from Informes import insights_repo
from Informes.informes_service import (
    ESTADO_VALIDADO,
    TABLA_INFORMES,
    afinidad_jaccard,
    tablas_disponibles,
    terminos_por_informe,
)
from Informes.insights_service import (
    MODELO,
    _armar_prompt,
    _obtener_informes_validados,
    llamar_gemini,
    parsear_json_modelo,
    titulo_para,
)

# Umbral del agrupamiento heurístico de respaldo: dos informes con menos de este
# solapamiento de skills no se proponen juntos. Es bajo a propósito: los
# informes de mercado usan vocabularios distintos y un 15 % de skills comunes ya
# suele indicar el mismo tema (p. ej. "IA y empleo").
_AFINIDAD_MINIMA = 0.15

# Cuántas skills compartidas / exclusivas se muestran al modelo por par o
# informe. Suficiente para que entienda el tema sin inflar el prompt.
_TOP_SKILLS_PROMPT = 12

SYSTEM_PROMPT_CANDIDATOS = """
Eres un analista del Observatorio Laboral de Alumni Sabana. Te doy una lista de
informes de mercado laboral ya validados y, para cada PAR, su afinidad (Jaccard
de skills compartidas, de 0 a 1), las skills que comparten y las exclusivas de
cada uno. Tu tarea es proponer GRUPOS de informes que valga la pena analizar
juntos porque tratan un tema común o se complementan.

Reglas:
- Cada grupo tiene 2 o más informes. Un informe puede estar en más de un grupo
  solo si aporta a temas realmente distintos.
- Básate en las cifras que te doy (afinidad y skills compartidas). No inventes
  afinidad donde el solapamiento es nulo; si dos informes no comparten skills,
  no los agrupes salvo que sus títulos muestren claramente el mismo tema.
- `motivo`: UNA frase en español, concreta, que cite 2-4 skills compartidas o el
  tema común (p. ej. "Ambos miden el peso de la IA generativa y las power
  skills en el empleo de entrada").
- `titulo_grupo`: 3-8 palabras, en español.
- `afinidad`: número de 0 a 1, coherente con las afinidades por par que te doy
  (para 3+ informes usa el promedio de sus pares).
- Si no encuentras ningún grupo razonable, devuelve la lista vacía.

Responde SOLO con JSON con esta forma exacta:
{"grupos": [{"informe_ids": ["id1", "id2"], "titulo_grupo": "...", "motivo": "...", "afinidad": 0.42}]}
""".strip()

SYSTEM_PROMPT_CONJUNTO = """
Eres un analista experto del Observatorio Laboral de Alumni Sabana. Se te
entregan los datos YA EXTRAÍDOS Y VERIFICADOS de un GRUPO de informes de
mercado laboral que fueron agrupados por afinidad temática (cada skill trae su
posición dentro del informe, su página y una cita literal), más un resumen
calculado de qué skills comparten y cuáles son exclusivas de cada uno.

Tu tarea es escribir un INSIGHT CONJUNTO: no describas cada informe por
separado, SINTETIZA lo que dicen en conjunto para un lector no técnico.

Normas obligatorias:
- Básate ÚNICAMENTE en los datos de abajo. No inventes cifras, skills ni
  afirmaciones. Cuando cites una skill o cifra, di de qué informe viene.
- Las skills COMPARTIDAS son la señal más fuerte (varios editores coinciden);
  dales prioridad. Las EXCLUSIVAS de un informe son matices o sesgos de ese
  editor: preséntalas así.
- Si los informes son de años distintos, comenta si algo cambió entre ellos
  (evolución), con prudencia: son editores y universos distintos.
- Distingue "Habilidades técnicas" de "Power Skills" (la etiqueta ya viene en
  los datos, úsala tal cual).
- Si algún informe tiene `antiguo` verdadero (más de 2 años), adviértelo.
- Estas cifras son DECLARADAS por cada editor, no medidas por el Observatorio:
  no las presentes como datos propios.
- Español claro y profesional. Formato Markdown con encabezados (##), negritas
  y listas; si usas tabla, cada fila en su propia línea y pocas columnas.

Estructura:
## Por qué estos informes van juntos
## En qué coinciden (señal fuerte)
## En qué difieren o se complementan
## Evolución en el tiempo (solo si hay años distintos)
## Qué implica para la empleabilidad de los egresados de La Sabana
## Límites de esta lectura
""".strip()


# ── Paso 1: candidatos ──────────────────────────────────────────────────────

def _metas_validados() -> list[dict[str, Any]]:
    if not tablas_disponibles():
        return []
    return (
        supabase.table(TABLA_INFORMES)
        .select("id,titulo,editor,anio_referencia,cobertura")
        .eq("estado", ESTADO_VALIDADO).order("anio_referencia")
        .execute().data
    ) or []


def _pares(metas: list[dict], terminos: dict[str, dict]) -> list[dict[str, Any]]:
    """Solapamiento de cada par de informes, ordenado por afinidad descendente."""
    pares = []
    for a, b in combinations(metas, 2):
        ta, tb = terminos.get(a["id"]) or {}, terminos.get(b["id"]) or {}
        comunes = set(ta) & set(tb)
        pares.append({
            "informe_ids": [a["id"], b["id"]],
            "afinidad": afinidad_jaccard(set(ta), set(tb)),
            "n_compartidas": len(comunes),
            "compartidas": sorted(
                comunes, key=lambda t: (ta.get(t) or 999) + (tb.get(t) or 999)
            )[:_TOP_SKILLS_PROMPT],
        })
    pares.sort(key=lambda p: -p["afinidad"])
    return pares


def _exclusivas(informe_id: str, terminos: dict[str, dict]) -> list[str]:
    """Skills que SOLO aparecen en ese informe, mejor posicionadas primero."""
    propias = terminos.get(informe_id) or {}
    otras: set[str] = set()
    for otro, t in terminos.items():
        if otro != informe_id:
            otras |= set(t)
    solo = set(propias) - otras
    return sorted(solo, key=lambda t: propias.get(t) or 999)[:_TOP_SKILLS_PROMPT]


def _grupos_heuristicos(pares: list[dict]) -> list[dict[str, Any]]:
    """
    Respaldo sin IA: cada par con afinidad >= umbral es un grupo. El motivo se
    redacta con las skills compartidas. Es lo que se devuelve si Gemini falla,
    para que el botón nunca quede en blanco por un problema del modelo.
    """
    grupos = []
    for p in pares:
        if p["afinidad"] < _AFINIDAD_MINIMA:
            continue
        top = ", ".join(p["compartidas"][:4]) or "varias skills"
        grupos.append({
            "informe_ids": p["informe_ids"],
            "titulo_grupo": "Informes con skills en común",
            "motivo": f"Comparten {p['n_compartidas']} skills, entre ellas {top}.",
            "afinidad": p["afinidad"],
        })
    return grupos


def _validar_grupos(crudo: Any, ids_validos: set[str]) -> list[dict[str, Any]]:
    """
    Filtra lo que devolvió el modelo: ids reales, 2+ por grupo, sin duplicados.
    El modelo puede alucinar un id o repetir un grupo; nada de eso llega a la UI.
    """
    grupos_crudos = crudo.get("grupos") if isinstance(crudo, dict) else crudo
    if not isinstance(grupos_crudos, list):
        return []
    salida, vistos = [], set()
    for g in grupos_crudos:
        if not isinstance(g, dict):
            continue
        ids = [i for i in (g.get("informe_ids") or []) if isinstance(i, str) and i in ids_validos]
        ids = list(dict.fromkeys(ids))          # sin repetidos, orden estable
        clave = tuple(sorted(ids))
        if len(ids) < 2 or clave in vistos:
            continue
        vistos.add(clave)
        try:
            afinidad = max(0.0, min(1.0, float(g.get("afinidad") or 0)))
        except (TypeError, ValueError):
            afinidad = 0.0
        salida.append({
            "informe_ids": ids,
            "titulo_grupo": str(g.get("titulo_grupo") or "Grupo de informes afines")[:120],
            "motivo": str(g.get("motivo") or "").strip()[:400],
            "afinidad": round(afinidad, 3),
        })
    salida.sort(key=lambda g: -g["afinidad"])
    return salida


def candidatos() -> dict[str, Any]:
    """
    Grupos de informes validados candidatos a un insight conjunto.

    Devuelve `{"grupos": [...], "informes": [...], "pares": [...], "metodo":
    "gemini"|"heuristico", "aviso": str|None}`. Con menos de 2 validados no hay
    nada que agrupar y NO se llama al modelo.
    """
    metas = _metas_validados()
    if len(metas) < 2:
        return {
            "grupos": [], "informes": metas, "pares": [], "metodo": None,
            "aviso": "Se necesitan al menos 2 informes validados para proponer grupos.",
        }

    ids = [m["id"] for m in metas]
    terminos = terminos_por_informe(ids)
    pares = _pares(metas, terminos)

    # Resumen que ve el modelo: cifras ya calculadas, nunca el PDF.
    lineas = ["Informes validados:"]
    for m in metas:
        excl = ", ".join(_exclusivas(m["id"], terminos)) or "ninguna"
        lineas.append(
            f"- id={m['id']} | {m['editor']} — {m['titulo']} ({m['anio_referencia']}, "
            f"{m.get('cobertura') or 'global'}) | {len(terminos.get(m['id']) or {})} skills "
            f"| exclusivas: {excl}"
        )
    lineas.append("\nPares (afinidad Jaccard de skills):")
    for p in pares:
        comp = ", ".join(p["compartidas"]) or "ninguna"
        lineas.append(
            f"- {p['informe_ids'][0]} ↔ {p['informe_ids'][1]}: afinidad {p['afinidad']}, "
            f"{p['n_compartidas']} compartidas ({comp})"
        )

    metodo, aviso = "gemini", None
    try:
        texto = llamar_gemini(
            SYSTEM_PROMPT_CANDIDATOS, "\n".join(lineas), max_tokens=2048, json_mode=True
        )
        grupos = _validar_grupos(parsear_json_modelo(texto), set(ids))
    except (RuntimeError, ValueError) as e:
        # Sin modelo (cuota, key, JSON roto) se responde igual con la heurística,
        # y se dice por qué: el Admin debe saber que el motivo no lo redactó la IA.
        grupos = _grupos_heuristicos(pares)
        metodo, aviso = "heuristico", f"Se usó el agrupamiento por solapamiento de skills: {e}"

    return {
        "grupos": grupos,
        "informes": metas,
        "pares": pares,
        "metodo": metodo,
        "modelo": MODELO if metodo == "gemini" else None,
        "aviso": aviso,
    }


# ── Paso 2: generación del insight conjunto ─────────────────────────────────

def generar_conjunto(
    informe_ids: list[str],
    motivo_grupo: str | None = None,
    creado_por: str | None = None,
) -> dict[str, Any]:
    """
    Insight conjunto sobre 2+ informes validados; lo persiste (tipo 'conjunto').

    ValueError si quedan menos de 2 informes validados entre los pedidos: con
    uno solo no hay nada que "conjuntar" (para eso está el insight individual).
    RuntimeError si falla Gemini.
    """
    informes = _obtener_informes_validados(informe_ids)
    if len(informes) < 2:
        raise ValueError(
            "Un insight conjunto necesita al menos 2 informes validados. "
            f"Se encontraron {len(informes)} entre los ids indicados."
        )

    ids = [i["id"] for i in informes]
    omitidos = [i for i in informe_ids if i not in set(ids)]
    terminos = terminos_por_informe(ids)

    # Resumen de solapamiento calculado en Python: ancla al modelo a las
    # coincidencias reales en vez de dejarle "descubrirlas" en el texto.
    resumen = ["### Resumen de solapamiento (calculado por el Observatorio)"]
    for p in _pares(informes, terminos):
        comp = ", ".join(p["compartidas"]) or "ninguna"
        resumen.append(
            f"- {p['informe_ids'][0]} ↔ {p['informe_ids'][1]}: afinidad {p['afinidad']}, "
            f"skills compartidas: {comp}"
        )
    for inf in informes:
        excl = ", ".join(_exclusivas(inf["id"], terminos)) or "ninguna"
        resumen.append(f"- Exclusivas de {inf['id']}: {excl}")
    if motivo_grupo:
        resumen.append(f"- Motivo del agrupamiento propuesto: {motivo_grupo}")

    texto = llamar_gemini(
        SYSTEM_PROMPT_CONJUNTO,
        "\n".join(resumen) + "\n\n### Datos de cada informe\n\n" + _armar_prompt(informes),
    )

    guardado = insights_repo.guardar(
        tipo=insights_repo.TIPO_CONJUNTO,
        informe_ids=ids,
        titulo=titulo_para(informes, "Insight conjunto"),
        contenido=texto,
        modelo=MODELO,
        informes=informes,
        motivo_grupo=motivo_grupo,
        creado_por=creado_por,
    )

    return {
        "texto": texto,
        "titulo": titulo_para(informes, "Insight conjunto"),
        "informes": [{
            "id": i["id"], "titulo": i["titulo"], "editor": i["editor"],
            "anio_referencia": i["anio_referencia"], "antiguo": i["antiguo"],
        } for i in informes],
        "omitidos": omitidos,
        "motivo_grupo": motivo_grupo,
        "persistido": guardado is not None,
        "insight_id": guardado["id"] if guardado else None,
        "aviso": None if guardado else insights_repo.AVISO_SIN_TABLA,
    }
