"""
informes_service.py — informes PDF de terceros como fuente de datos.

Gestiona el catálogo de informes ingeridos (`informes`) y sus cifras
(`informes_observaciones`), y los expone como una FUENTE más para el selector del
frontend, junto a Adzuna, Google Jobs y O*NET.

DOS REGLAS QUE NO SE DEBEN ROMPER
1. Un informe NO se promedia con las vacantes. Se muestra como columna de
   CONTRASTE. Un ranking declarado por Coursera y un share mensual de Adzuna no
   son la misma magnitud; combinarlos produciría un número sin significado.
2. Nada llega al selector hasta que un humano lo valida (`estado='validado'`).
   La extracción automática deja el informe en 'borrador'.

CICLO DE VIDA DE UN INFORME Y EL HASH DEL PDF
  borrador -> validado -> retirado -> (re-subir el mismo PDF) -> borrador ...

El sha256 del PDF (`hash_pdf`, índice único en la BD) evita ingerir dos veces
el mismo documento. Pero "retirado" significa "sacado del selector, datos
conservados", NO "prohibido para siempre": si el Administrador vuelve a subir
ese PDF (por ejemplo tras ampliar el diccionario de skills o corregir el
título), el informe retirado se REACTIVA: conserva su `id` (así los insights
ya generados que lo citan siguen apuntando al documento correcto), se
reemplazan sus observaciones por las nuevas y vuelve a 'borrador' para pasar
otra vez por la validación humana. Ver `informe_por_hash()` y
`guardar_informe()`.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from Adzuna.adzuna_service import supabase
from Informes.power_skills import clasificar_habilidad

TABLA_INFORMES = "informes"
TABLA_OBS = "informes_observaciones"

ESTADO_BORRADOR = "borrador"
ESTADO_VALIDADO = "validado"
ESTADO_RETIRADO = "retirado"

# Métricas que definen un ORDEN dentro del informe y por tanto pueden ponerse al
# lado del ranking de vacantes (se compara la POSICIÓN, nunca el valor bruto: el
# conteo de menciones depende de cuántas páginas tenga el PDF).
#
# Quedan fuera a propósito los porcentajes ('35% de nuestros matriculados'): son
# relativos al universo del propio informe y no son comparables con un share de
# vacantes. Se muestran en la ficha del informe, no en la columna comparativa.
METRICAS_ORDENABLES = ("posicion_ranking", "conteo", "indice_propietario")

_cache_tablas: bool | None = None


def tablas_disponibles() -> bool:
    """
    True si la migración 006 ya se ejecutó. Se cachea.

    Permite que toda la funcionalidad degrade con elegancia: si las tablas no
    existen, `catalogo_fuentes()` devuelve [] y el selector simplemente no muestra
    informes, en vez de romper /tendencias/opciones para todo el mundo.
    """
    global _cache_tablas
    if _cache_tablas is None:
        try:
            supabase.table(TABLA_INFORMES).select("id").limit(1).execute()
            _cache_tablas = True
        except Exception:
            _cache_tablas = False
    return _cache_tablas


def invalidar_cache() -> None:
    """Reevalúa si las tablas existen (llamar tras correr la migración)."""
    global _cache_tablas
    _cache_tablas = None


def slug(editor: str, titulo: str, anio: int) -> str:
    """'Coursera', 'Job Skills Report', 2024 -> 'coursera-job-skills-report-2024'."""
    crudo = f"{editor} {titulo} {anio}"
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", crudo)
        if unicodedata.category(c) != "Mn"
    )
    limpio = re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")
    return re.sub(r"-{2,}", "-", limpio)[:80]


# ── Escritura ───────────────────────────────────────────────────────────────

def guardar_informe(catalogo: dict[str, Any], items: list[dict]) -> dict[str, Any]:
    """
    Persiste el informe (en estado 'borrador') y sus observaciones.

    `catalogo` ya viene revisado por el usuario en el formulario; `items` son las
    filas extraídas y verificadas. Se canonicaliza aquí el término al español.
    """
    if not tablas_disponibles():
        raise RuntimeError(
            "Las tablas de informes no existen. Ejecuta migrations/006_informes.sql "
            "en el SQL Editor de Supabase."
        )

    from Tendencias.skills_extractor import canonicalizar, get_categoria

    # ¿Este PDF ya pasó por aquí? Un informe ACTIVO (borrador/validado) bloquea;
    # uno RETIRADO se reactiva conservando su id (ver docstring del módulo).
    previo = informe_por_hash(catalogo.get("hash_pdf") or "")
    reactivado = False
    if previo and previo["estado"] != ESTADO_RETIRADO:
        raise ValueError(f"Ese informe ya fue ingerido: {previo['id']}")
    if previo:
        informe_id = previo["id"]
        reactivado = True
        # Las observaciones viejas se borran ENTERAS, no se funden: si el
        # diccionario cambió, una skill que ya no se detecta no debe sobrevivir
        # del ingreso anterior (el upsert de abajo solo añade/actualiza).
        supabase.table(TABLA_OBS).delete().eq("informe_id", informe_id).execute()
    else:
        informe_id = catalogo.get("id") or slug(
            catalogo.get("editor", "informe"),
            catalogo.get("titulo", ""),
            int(catalogo.get("anio_referencia") or 0),
        )
    # `universo` ya no se pide en la UI, pero la columna es NOT NULL en la BD; se
    # manda vacío para no exigir otra migración. Si algún informe lo trae, se guarda.
    fila = {**catalogo, "id": informe_id, "estado": ESTADO_BORRADOR}
    fila.setdefault("universo", "")
    if reactivado:
        # Vuelve a empezar el ciclo: la validación anterior ya no aplica a los
        # datos nuevos, y la fecha de ingesta debe reflejar esta re-subida.
        fila.update({
            "validado_por": None,
            "validado_en": None,
            "ingestado_en": datetime.now(timezone.utc).isoformat(),
        })
    supabase.table(TABLA_INFORMES).upsert(fila, on_conflict="id").execute()

    observaciones = []
    for it in items:
        original = (it.get("termino_original") or "").strip()
        if not original:
            continue
        # Si no mapea a nuestra taxonomía se conserva con termino=NULL: descartarlo
        # sesgaría el resultado hacia lo que ya conocemos y ocultaría lo nuevo.
        canonico = canonicalizar(original)
        observaciones.append({
            "informe_id": informe_id,
            "dimension": it.get("dimension", "skill"),
            "termino_original": original,
            "termino": canonico or None,
            "categoria": get_categoria(canonico) if canonico else None,
            "metrica": it.get("metrica", "posicion_ranking"),
            "valor": it.get("valor"),
            "posicion": it.get("posicion"),
            "pagina": it.get("pagina"),
            "cita": it.get("cita"),
            "verificada": bool(it.get("verificada")),
            "confianza": it.get("confianza"),
        })

    if observaciones:
        supabase.table(TABLA_OBS).upsert(
            observaciones, on_conflict="informe_id,dimension,termino_original,metrica"
        ).execute()

    return {
        "id": informe_id,
        "estado": ESTADO_BORRADOR,
        "observaciones": len(observaciones),
        "reactivado": reactivado,
    }


def _exigir_existente(informe_id: str) -> dict[str, Any]:
    """
    Fila mínima (id, estado) del informe, o ValueError si no existe.

    Un UPDATE ... WHERE id = X sobre un id inexistente no falla en PostgREST:
    afecta 0 filas y devuelve 200. Sin esta comprobación, validar o retirar un
    id mal escrito respondía {"estado": "validado"} como si hubiera ocurrido.
    """
    r = supabase.table(TABLA_INFORMES).select("id,estado").eq("id", informe_id).execute()
    if not r.data:
        raise ValueError(f"No existe el informe '{informe_id}'.")
    return r.data[0]


def validar_informe(informe_id: str, validado_por: str) -> dict[str, Any]:
    """Marca el informe como validado: recién ahí aparece en el selector de fuentes."""
    if not tablas_disponibles():
        raise RuntimeError("Las tablas de informes no existen (migración 006).")
    _exigir_existente(informe_id)
    supabase.table(TABLA_INFORMES).update({
        "estado": ESTADO_VALIDADO,
        "validado_por": validado_por,
        "validado_en": datetime.now(timezone.utc).isoformat(),
    }).eq("id", informe_id).execute()
    return {"id": informe_id, "estado": ESTADO_VALIDADO}


def retirar_informe(informe_id: str) -> dict[str, Any]:
    """
    Saca el informe del selector sin borrar sus datos. Es reversible: volver a
    subir el mismo PDF lo reactiva (ver docstring del módulo).
    """
    if not tablas_disponibles():
        raise RuntimeError("Las tablas de informes no existen (migración 006).")
    _exigir_existente(informe_id)
    supabase.table(TABLA_INFORMES).update({"estado": ESTADO_RETIRADO}).eq("id", informe_id).execute()
    return {"id": informe_id, "estado": ESTADO_RETIRADO}


def eliminar_informe(informe_id: str) -> dict[str, Any]:
    """Borra un informe. Solo si sigue en borrador (las observaciones caen en cascada)."""
    r = supabase.table(TABLA_INFORMES).select("estado").eq("id", informe_id).execute()
    if not r.data:
        raise ValueError(f"No existe el informe '{informe_id}'.")
    if r.data[0]["estado"] != "borrador":
        raise ValueError("Solo se pueden eliminar informes en borrador; usa 'retirar'.")
    supabase.table(TABLA_INFORMES).delete().eq("id", informe_id).execute()
    return {"id": informe_id, "eliminado": True}


def informe_por_hash(hash_pdf: str) -> dict[str, Any] | None:
    """
    Ficha mínima (id, estado, titulo, editor, anio_referencia) del informe que ya
    usó ese PDF, o None. Devuelve el ESTADO a propósito: el llamador decide si
    bloquea (activo) o reactiva (retirado).
    """
    if not tablas_disponibles() or not hash_pdf:
        return None
    r = (
        supabase.table(TABLA_INFORMES)
        .select("id,estado,titulo,editor,anio_referencia")
        .eq("hash_pdf", hash_pdf).limit(1).execute()
    )
    return r.data[0] if r.data else None


def existe_hash(hash_pdf: str) -> str | None:
    """
    Id del informe ACTIVO (borrador o validado) que ya usó ese PDF, o None.

    Un informe RETIRADO no cuenta como existente: antes sí lo hacía y eso
    bloqueaba para siempre volver a subir un PDF retirado ("Ese informe ya fue
    ingerido"), porque el hash seguía en la tabla. Retirar es reversible.
    """
    fila = informe_por_hash(hash_pdf)
    if fila and fila["estado"] != ESTADO_RETIRADO:
        return fila["id"]
    return None


# ── Lectura ─────────────────────────────────────────────────────────────────

def listar_informes(estado: str = "todos") -> list[dict]:
    """Informes del catálogo con su número de observaciones."""
    if not tablas_disponibles():
        return []
    q = supabase.table(TABLA_INFORMES).select("*").order("anio_referencia", desc=True)
    if estado != "todos":
        q = q.eq("estado", estado)
    informes = q.execute().data or []

    for inf in informes:
        obs = supabase.table(TABLA_OBS).select("verificada").eq("informe_id", inf["id"]).execute().data or []
        inf["n_observaciones"] = len(obs)
        inf["n_verificadas"] = sum(1 for o in obs if o.get("verificada"))
    return informes


def catalogo_fuentes() -> list[dict]:
    """
    Informes validados con la forma de "fuente" que consume el selector.

    `naturaleza='declarado'` y `universo` viajan a propósito: la UI los imprime en
    la cabecera de la columna para que nadie lea una cifra declarada por un tercero
    como si fuera demanda observada.
    """
    if not tablas_disponibles():
        return []
    try:
        filas = (
            supabase.table(TABLA_INFORMES).select("*")
            .eq("estado", "validado").order("anio_referencia", desc=True).execute().data
        ) or []
    except Exception:
        return []

    return [{
        "id": f"informe:{f['id']}",
        "fuente": "informe",
        "pais": None,
        "tipo": "informe",
        "naturaleza": "declarado",
        "granularidad_temporal": "anual",
        "label": f"{f['editor']} — {f['titulo']}",
        "sublabel": f"{f.get('cobertura') or 'global'} · {f['anio_referencia']}",
        "dimensiones": ["skill"],
        "anio_referencia": f["anio_referencia"],
        "universo": f.get("universo"),
        "sesgos_conocidos": f.get("sesgos_conocidos"),
        "url": f.get("url"),
    } for f in filas]


def detalle_informe(informe_id: str, top: int = 20) -> dict[str, Any]:
    """
    Un informe con sus propias cifras, para pintar sus gráficas individuales.

    Devuelve el top de skills (ordenado por su posición dentro del informe) y el
    reparto por categoría. Es una vista del informe EN SÍ MISMO, sin cruzarlo con
    las vacantes: sirve para leer qué dice ese documento.

    El reparto por categoría usa `clasificar_habilidad()` (Habilidades técnicas
    vs Power Skills), NO la `categoria` de 4 valores (técnica/blanda/
    conocimiento/destreza) que guarda cada observación: esa taxonomía viene de
    O*NET/Ocupacol, pensada para vacantes, y sobre informes de tendencias
    tecnológicas clasifica mal (ver docstring de Informes/power_skills.py).
    """
    if not tablas_disponibles():
        return {"informe": None, "items": [], "por_categoria": []}

    metas = supabase.table(TABLA_INFORMES).select("*").eq("id", informe_id).execute().data or []
    if not metas:
        return {"informe": None, "items": [], "por_categoria": []}

    obs = (
        supabase.table(TABLA_OBS).select("*")
        .eq("informe_id", informe_id).eq("dimension", "skill")
        .execute().data
    ) or []
    obs.sort(key=lambda o: (o.get("posicion") or 9999))

    items = [{
        "termino": o.get("termino") or o["termino_original"],
        "termino_original": o["termino_original"],
        "categoria": o.get("categoria") or "sin categoría",
        "valor": o.get("valor"),
        "posicion": o.get("posicion"),
        "pagina": o.get("pagina"),
        "cita": o.get("cita"),
    } for o in obs[:top]]

    # Reparto por categoría sobre TODAS las observaciones, no solo el top.
    # Se clasifica por el TÉRMINO (canónico si existe, si no el original), no
    # por la `categoria` guardada: ver docstring de arriba.
    conteo: dict[str, int] = {}
    for o in obs:
        cat = clasificar_habilidad(o.get("termino") or o.get("termino_original"))
        conteo[cat] = conteo.get(cat, 0) + 1

    return {
        "informe": {
            "id": metas[0]["id"],
            "titulo": metas[0]["titulo"],
            "editor": metas[0]["editor"],
            "anio_referencia": metas[0]["anio_referencia"],
            "cobertura": metas[0].get("cobertura"),
            "paginas": metas[0].get("paginas"),
            "idioma": metas[0].get("idioma"),
            "estado": metas[0]["estado"],
            "total_skills": len(obs),
        },
        "items": items,
        "por_categoria": [{"categoria": c, "n": n} for c, n in
                          sorted(conteo.items(), key=lambda x: -x[1])],
    }


def comparativa_informes(top: int = 12) -> dict[str, Any]:
    """
    Skills más citadas COMPARADAS entre todos los informes validados.

    Se compara la POSICIÓN de cada skill en cada informe, nunca el conteo de
    menciones: ese depende del largo del PDF y no es comparable entre documentos.
    """
    if not tablas_disponibles():
        return {"informes": [], "terminos": []}

    metas = (
        supabase.table(TABLA_INFORMES).select("*")
        .eq("estado", "validado").order("anio_referencia").execute().data
    ) or []
    if len(metas) < 2:
        return {"informes": [], "terminos": []}   # con uno solo no hay qué comparar

    ids = [m["id"] for m in metas]
    obs = (
        supabase.table(TABLA_OBS).select("informe_id,termino,termino_original,posicion")
        .in_("informe_id", ids).eq("dimension", "skill").execute().data
    ) or []

    por_termino: dict[str, dict] = {}
    for o in obs:
        clave = o.get("termino") or o["termino_original"]
        entrada = por_termino.setdefault(clave, {"termino": clave, "posiciones": {}})
        entrada["posiciones"][o["informe_id"]] = o.get("posicion")

    # Primero las que aparecen en más informes y mejor posicionadas.
    ordenados = sorted(
        por_termino.values(),
        key=lambda t: (-len(t["posiciones"]),
                       min((p or 999) for p in t["posiciones"].values())),
    )[:top]

    return {
        "informes": [{"id": m["id"], "label": f"{m['editor']} {m['anio_referencia']}",
                      "anio_referencia": m["anio_referencia"]} for m in metas],
        "terminos": ordenados,
    }


def contraste(informes_ids: list[str], dimension: str = "skill", top: int = 25) -> dict[str, Any]:
    """
    Datos de los informes elegidos para la vista de contraste de Skills.

    Devuelve los términos que SÍ mapean a nuestra taxonomía (para cruzarlos con el
    ranking) y, aparte, los que no mapean — esos se muestran como "solo en este
    informe", nunca mezclados en el ranking.
    """
    vacio = {"informes": [], "terminos": [], "no_mapeados": []}
    if not tablas_disponibles() or not informes_ids:
        return vacio

    ids = [i.replace("informe:", "") for i in informes_ids]
    metas = supabase.table(TABLA_INFORMES).select("*").in_("id", ids).execute().data or []
    if not metas:
        return vacio

    from datetime import date
    anio_actual = date.today().year

    obs = (
        supabase.table(TABLA_OBS).select("*")
        .in_("informe_id", ids).eq("dimension", dimension)
        .in_("metrica", list(METRICAS_ORDENABLES))   # solo lo comparable entra aquí
        .execute().data
    ) or []

    por_termino: dict[str, dict] = {}
    no_mapeados: list[dict] = []
    for o in obs:
        if not o.get("verificada"):
            continue  # sin cita comprobada no se publica
        if not o.get("termino"):
            no_mapeados.append({
                "termino_original": o["termino_original"],
                "informe_id": o["informe_id"],
                "posicion": o.get("posicion"),
            })
            continue
        entrada = por_termino.setdefault(o["termino"], {
            "termino": o["termino"],
            "termino_original": o["termino_original"],
            "categoria": o.get("categoria"),
            "por_informe": {},
        })
        entrada["por_informe"][o["informe_id"]] = {
            "posicion": o.get("posicion"),
            "metrica": o["metrica"],
            "pagina": o.get("pagina"),
            "cita": o.get("cita"),
        }

    terminos = sorted(
        por_termino.values(),
        key=lambda t: min((v.get("posicion") or 999) for v in t["por_informe"].values()),
    )[:top]

    return {
        "informes": [{
            "id": m["id"],
            "label": f"{m['editor']} — {m['titulo']}",
            "universo": m.get("universo"),
            "naturaleza": "declarado",
            "anio_referencia": m["anio_referencia"],
            # Un informe de hace más de 2 años se marca: el mercado cambia.
            "antiguo": (anio_actual - m["anio_referencia"]) > 2,
            "sesgos_conocidos": m.get("sesgos_conocidos"),
        } for m in metas],
        "terminos": terminos,
        "no_mapeados": no_mapeados[:20],
    }


# ── Similitud entre informes (sin IA) ───────────────────────────────────────
#
# Base común de "Reportes similares" (vista de Usuario) y de los candidatos a
# Insights Conjuntos (Admin). Se calcula con el solapamiento de SKILLS, no con
# el texto del PDF: las observaciones ya están extraídas y verificadas, así que
# es barato (dos consultas) y determinista, y no hay que pagar una llamada a un
# modelo cada vez que un Usuario abre su informe.

def terminos_por_informe(ids: list[str]) -> dict[str, dict[str, int | None]]:
    """
    {informe_id: {termino: posicion}} para la dimensión 'skill'.

    Se usa el término canónico cuando existe (así "Communication" y
    "comunicación" cuentan como la misma skill) y el original si no mapea.
    """
    if not tablas_disponibles() or not ids:
        return {}
    obs = (
        supabase.table(TABLA_OBS)
        .select("informe_id,termino,termino_original,posicion")
        .in_("informe_id", ids).eq("dimension", "skill")
        .execute().data
    ) or []
    salida: dict[str, dict[str, int | None]] = {i: {} for i in ids}
    for o in obs:
        clave = (o.get("termino") or o["termino_original"]).strip().lower()
        salida.setdefault(o["informe_id"], {})[clave] = o.get("posicion")
    return salida


def afinidad_jaccard(a: set[str], b: set[str]) -> float:
    """|A ∩ B| / |A ∪ B|, en [0, 1]. 0 si alguno está vacío."""
    if not a or not b:
        return 0.0
    return round(len(a & b) / len(a | b), 3)


def _compartidas_ordenadas(ta: dict[str, int | None], tb: dict[str, int | None], top: int) -> list[str]:
    """Skills comunes, primero las mejor posicionadas en AMBOS informes."""
    comunes = set(ta) & set(tb)
    return sorted(comunes, key=lambda t: (ta.get(t) or 999) + (tb.get(t) or 999))[:top]


def similares(informe_id: str, top: int = 5, top_skills: int = 8) -> dict[str, Any]:
    """
    Informes VALIDADOS que más skills comparten con el dado.

    Solo se comparan contra validados: un Usuario no debe ver como "similar" un
    borrador que nadie ha revisado. El informe de partida puede estar en
    cualquier estado (el Usuario consulta el suyo mientras sigue pendiente).
    """
    vacio = {"informe_id": informe_id, "similares": [], "n_candidatos": 0}
    if not tablas_disponibles():
        return vacio

    candidatos = (
        supabase.table(TABLA_INFORMES)
        .select("id,titulo,editor,anio_referencia,cobertura")
        .eq("estado", ESTADO_VALIDADO).neq("id", informe_id)
        .execute().data
    ) or []
    if not candidatos:
        return vacio

    terminos = terminos_por_informe([informe_id] + [c["id"] for c in candidatos])
    base = terminos.get(informe_id) or {}
    if not base:
        return {**vacio, "n_candidatos": len(candidatos)}

    filas = []
    for c in candidatos:
        otros = terminos.get(c["id"]) or {}
        afinidad = afinidad_jaccard(set(base), set(otros))
        if afinidad <= 0:
            continue   # sin ninguna skill en común no hay nada que mostrar
        filas.append({
            "id": c["id"],
            "titulo": c["titulo"],
            "editor": c["editor"],
            "anio_referencia": c["anio_referencia"],
            "cobertura": c.get("cobertura"),
            "afinidad": afinidad,
            "n_compartidas": len(set(base) & set(otros)),
            "compartidas": _compartidas_ordenadas(base, otros, top_skills),
        })
    filas.sort(key=lambda f: -f["afinidad"])
    return {"informe_id": informe_id, "similares": filas[:top], "n_candidatos": len(candidatos)}
