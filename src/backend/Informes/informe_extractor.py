"""
informe_extractor.py — extrae skills de un informe PDF con OCR + diccionario.

MÉTODO (el mismo de Reto-Alumni, por decisión del proyecto)
  1. TEXTO   Google Document AI (OCR) si está configurado; si no, pypdf.
             Document AI es el que permite leer informes ESCANEADOS.
  2. SKILLS  Coincidencia contra el diccionario del proyecto
             (`Tendencias/skills_extractor`, construido de O*NET + Ocupacol),
             con límites de palabra para no capturar subcadenas.

Es un proceso DETERMINISTA: no interviene ningún modelo de lenguaje, así que no
hay riesgo de que se invente una skill. Cada fila que se guarda corresponde a un
término que aparece impreso en el documento.

Aun así se registra la PÁGINA y una CITA del contexto de la primera aparición, para
que cualquier cifra del dashboard sea rastreable hasta el PDF.

MIGRACIÓN FUTURA A CLAUDE: `procesar_pdf(..., metodo='claude')` queda reservado.
El resto del pipeline (verificación, guardado, contraste) no cambia.

LIMITACIÓN CONOCIDA (heredada del método): la métrica es el CONTEO de menciones,
que no está normalizado por la longitud del informe. Un PDF de 200 páginas
producirá conteos mayores que uno de 30 para la misma skill. Por eso el conteo se
usa para ORDENAR dentro de un mismo informe, y los informes se comparan entre sí
por POSICIÓN en el ranking, nunca por el conteo bruto.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from config import DOCAI_PROCESSOR, GCP_LOCATION, GCP_PROJECT_ID
from Informes.pdf_texto import (
    normalizar_para_cotejo,
    texto_por_pagina,
    tiene_capa_de_texto,
)

# Caracteres de contexto que se guardan alrededor de la primera aparición.
_VENTANA_CITA = 90


# ── 1. Obtención del texto ──────────────────────────────────────────────────

def documentai_configurado() -> bool:
    """True si hay proyecto y procesador de Document AI en el entorno."""
    return bool(GCP_PROJECT_ID and DOCAI_PROCESSOR)


def _texto_documentai(pdf_bytes: bytes) -> tuple[dict[int, str], dict]:
    """
    Texto por página con Google Document AI (OCR).

    Se trocea por página usando los `text_segments` del layout de cada una, para
    conservar la trazabilidad (página + cita) que el dashboard necesita.
    """
    from google.cloud import documentai

    client = documentai.DocumentProcessorServiceClient()
    nombre = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, DOCAI_PROCESSOR)

    peticion = documentai.ProcessRequest(
        name=nombre,
        raw_document=documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf"),
    )
    doc = client.process_document(request=peticion).document

    paginas: dict[int, str] = {}
    for i, pagina in enumerate(doc.pages, start=1):
        trozos = []
        for seg in pagina.layout.text_anchor.text_segments:
            ini = int(seg.start_index or 0)
            fin = int(seg.end_index or 0)
            trozos.append(doc.text[ini:fin])
        paginas[i] = "".join(trozos)

    meta = {
        "metodo_extraccion": "document_ai",
        "paginas": len(doc.pages),
        "idioma_detectado": (
            doc.pages[0].detected_languages[0].language_code
            if doc.pages and doc.pages[0].detected_languages else "desconocido"
        ),
    }
    return paginas, meta


def obtener_texto(pdf_bytes: bytes) -> tuple[dict[int, str], dict]:
    """
    Texto por página, con Document AI si está configurado y pypdf como respaldo.

    Se prefiere Document AI porque es el único que lee PDFs escaneados. Si falla
    (credenciales, cuota, tamaño), se degrada a pypdf en vez de abortar: un informe
    nativo se procesa igual de bien.
    """
    if documentai_configurado():
        try:
            return _texto_documentai(pdf_bytes)
        except Exception as e:
            print(f"   ⚠ Document AI no disponible ({e}); se usa pypdf.")

    paginas = texto_por_pagina(pdf_bytes)
    return paginas, {"metodo_extraccion": "pypdf", "paginas": len(paginas),
                     "idioma_detectado": "desconocido"}


# ── 2. Coincidencia con el diccionario ──────────────────────────────────────

# Vocabulario propio de los informes del sector, que el diccionario base NO cubre.
#
# POR QUÉ HACE FALTA: el diccionario del proyecto sale de O*NET, que usa nombres de
# taxonomía formal ("Reading Comprehension", "Social Perceptiveness"). Los informes
# de mercado usan jerga de industria ("Machine Learning", "Leadership", "Data
# Analysis"). Sin esta capa, ingerir un Job Skills Report devuelve casi nada:
# medido sobre un informe de prueba, 1 de 4 skills.
#
# Cada término se busca tal cual en el texto; la canonicalización posterior lo
# traduce al español cuando existe equivalente. Ampliar esta lista es la forma más
# barata de mejorar la cobertura.
_TERMINOS_INFORMES = [
    # Datos e IA
    "Machine Learning", "Deep Learning", "Artificial Intelligence", "Generative AI",
    "Data Analysis", "Data Analytics", "Data Science", "Data Visualization",
    "Big Data", "Business Intelligence", "Statistics", "Prompt Engineering",
    # Negocio y gestión
    "Leadership", "Project Management", "Product Management", "Strategy",
    "Change Management", "Risk Management", "Stakeholder Management",
    "Digital Marketing", "Customer Service", "Sales", "Finance", "Accounting",
    # Transversales
    "Communication", "Teamwork", "Collaboration", "Problem Solving",
    "Adaptability", "Resilience", "Creativity", "Innovation", "Empathy",
    "Emotional Intelligence", "Time Management", "Negotiation",
    # Tecnología general
    "Cybersecurity", "Cloud Computing", "Software Development", "DevOps",
    "Automation", "Software Engineering", "UX Design", "Sustainability",
]


def _terminos_del_diccionario(idioma: str) -> list[str]:
    """Términos a buscar, según el idioma del informe (sin duplicados)."""
    from Tendencias.skills_extractor import cargar_diccionario

    d = cargar_diccionario()
    if idioma == "es":
        base = list(d.get("busqueda_rapida", []))
    else:
        # En inglés: nombres en inglés de las blandas + técnicas (universales).
        base = list((d.get("blandas", {}).get("mapping_en") or {}).values())
        base += list(d.get("tecnicas", {}).get("terminos") or [])

    # Los términos de informe se añaden en ambos idiomas: hasta los informes en
    # español dejan estos anglicismos sin traducir ("Machine Learning").
    vistos: set[str] = set()
    salida: list[str] = []
    for t in base + _TERMINOS_INFORMES:
        clave = t.lower()
        if clave not in vistos:
            vistos.add(clave)
            salida.append(t)
    return salida


def extraer_skills_de_paginas(paginas: dict[int, str], idioma: str = "en") -> list[dict]:
    """
    Busca cada término del diccionario en el texto y devuelve sus apariciones.

    Por término se registra: menciones totales, la página de la primera aparición y
    una cita del contexto. La coincidencia exige límites de palabra, de modo que
    'R' no case dentro de 'Research' ni 'IA' dentro de 'Familia'.
    """
    paginas_norm = {n: normalizar_para_cotejo(t) for n, t in paginas.items()}
    encontrados: list[dict] = []

    for termino in _terminos_del_diccionario(idioma):
        termino_norm = normalizar_para_cotejo(termino)
        if len(termino_norm) < 2:
            continue  # términos de 1 carácter generan ruido puro

        patron = re.compile(rf"(?<!\w){re.escape(termino_norm)}(?!\w)")
        menciones = 0
        primera_pagina: int | None = None
        cita = ""

        for n in sorted(paginas_norm):
            hallazgos = list(patron.finditer(paginas_norm[n]))
            if not hallazgos:
                continue
            menciones += len(hallazgos)
            if primera_pagina is None:
                primera_pagina = n
                pos = hallazgos[0].start()
                texto = paginas_norm[n]
                ini = max(0, pos - _VENTANA_CITA // 2)
                cita = texto[ini:pos + len(termino_norm) + _VENTANA_CITA // 2].strip()

        if menciones:
            encontrados.append({
                "termino_original": termino,
                "metrica": "conteo",
                "valor": float(menciones),
                "posicion": None,          # se asigna abajo, por ranking de menciones
                "pagina": primera_pagina,
                "cita": cita,
                # Determinista: el término se halló literalmente en el texto.
                "verificada": True,
                "confianza": 1.0,
            })

    # La posición ordena por menciones dentro de ESTE informe. Es lo comparable
    # entre informes (el conteo bruto no lo es: depende del largo del PDF).
    encontrados.sort(key=lambda x: -x["valor"])
    for i, e in enumerate(encontrados, start=1):
        e["posicion"] = i
    return encontrados


# ── 3. Pipeline ─────────────────────────────────────────────────────────────

def procesar_pdf(pdf_bytes: bytes, filename: str, idioma: str = "en",
                 metodo: str = "ocr") -> dict[str, Any]:
    """
    Pipeline completo: texto (OCR) -> skills por diccionario -> borrador.

    NO guarda nada: devuelve el borrador para que el usuario lo revise y confirme.
    `metodo='claude'` queda reservado para la migración futura.
    """
    if metodo == "claude":
        raise NotImplementedError(
            "La extracción con Claude aún no está habilitada. Usa metodo='ocr'."
        )

    paginas, meta_texto = obtener_texto(pdf_bytes)

    if not tiene_capa_de_texto(paginas):
        detalle = (
            "El PDF no tiene texto seleccionable y Google Document AI no está "
            "configurado, así que no se puede leer. Configura Document AI "
            "(GCP_PROJECT_ID, DOCAI_PROCESSOR) para procesar informes escaneados."
            if not documentai_configurado()
            else "No se pudo extraer texto del PDF ni siquiera con OCR."
        )
        raise ValueError(detalle)

    items = extraer_skills_de_paginas(paginas, idioma)

    return {
        "hash_pdf": hashlib.sha256(pdf_bytes).hexdigest(),
        "paginas": meta_texto.get("paginas", len(paginas)),
        "metodo_extraccion": meta_texto.get("metodo_extraccion"),
        "idioma_detectado": meta_texto.get("idioma_detectado"),
        "metadatos_sugeridos": {
            "titulo": _detectar_titulo(paginas, filename),
            "editor": _detectar_editor(paginas),
            "anio_referencia": _detectar_anio(paginas, filename),
            "cobertura": "global",
        },
        "extraidos": len(items),
        "descartados": 0,          # el método es determinista: no hay nada que descartar
        "tasa_verificacion": 1.0,
        "items": items,
    }


# Editores habituales de informes de mercado laboral. Se buscan por nombre en las
# primeras páginas; gana el que más veces aparezca. La clave es el texto a buscar
# (en minúsculas) y el valor, cómo debe escribirse.
_EDITORES_CONOCIDOS = {
    "coursera": "Coursera",
    "linkedin": "LinkedIn",
    "world economic forum": "World Economic Forum",
    "weforum": "World Economic Forum",
    "mckinsey": "McKinsey",
    "deloitte": "Deloitte",
    "pwc": "PwC",
    "accenture": "Accenture",
    "boston consulting": "Boston Consulting Group",
    "gartner": "Gartner",
    "forrester": "Forrester",
    "udemy": "Udemy",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "manpower": "ManpowerGroup",
    "randstad": "Randstad",
    "ibm": "IBM",
    "microsoft": "Microsoft",
    "oecd": "OECD",
    "organizacion internacional del trabajo": "OIT",
    "international labour": "OIT",
}


def _detectar_editor(paginas: dict[int, str]) -> str | None:
    """
    Quién publica el informe, buscando editores conocidos en las primeras páginas.

    Se cuenta cuántas veces aparece cada uno y gana el más repetido: la portada y
    los pies de página suelen repetir el nombre del editor, mientras que otras
    marcas se mencionan de pasada.
    """
    cabecera = normalizar_para_cotejo(
        " ".join(paginas.get(n, "") for n in sorted(paginas)[:6])
    )
    conteos = {
        nombre: len(re.findall(rf"(?<!\w){re.escape(clave)}(?!\w)", cabecera))
        for clave, nombre in _EDITORES_CONOCIDOS.items()
    }
    conteos = {k: v for k, v in conteos.items() if v > 0}
    return max(conteos, key=lambda k: conteos[k]) if conteos else None


def _detectar_titulo(paginas: dict[int, str], filename: str) -> str:
    """
    Título del informe. Se prefiere el encabezado corrido del documento
    ("Job Skills Report 2025 | Introduction" -> "Job Skills Report 2025"), que es
    más limpio que el nombre del archivo ("Job-Skills-Report-2024 (2) (1)").
    """
    primeras = " ".join(paginas.get(n, "") for n in sorted(paginas)[:3])
    for linea in primeras.split("\n"):
        linea = linea.strip()
        # El encabezado corrido suele venir como "<Título>  |  <Sección>".
        if "|" in linea:
            candidato = linea.split("|")[0].strip()
            if 8 <= len(candidato) <= 90 and re.search(r"[A-Za-z]{4}", candidato):
                return candidato
    # Respaldo: el nombre del archivo, limpiando guiones y sufijos de descarga.
    base = filename.rsplit(".", 1)[0]
    base = re.sub(r"\s*\(\d+\)", "", base)          # "(2) (1)" de las descargas
    return re.sub(r"[-_]+", " ", base).strip()


def _detectar_anio(paginas: dict[int, str], filename: str) -> int | None:
    """
    Año de referencia del informe.

    Primero se busca junto a una palabra de título ('Report 2024'), que es la fecha
    editorial; si no aparece, el año más repetido al principio del documento; y por
    último el del nombre del archivo.
    """
    from collections import Counter
    from datetime import date

    validos = set(range(2010, date.today().year + 2))
    cabecera = " ".join(paginas.get(n, "") for n in sorted(paginas)[:3])

    m = re.search(
        r"\b(?:report|informe|survey|reporte|index|outlook|study|skills)\s+(20\d{2})\b",
        cabecera, re.IGNORECASE,
    )
    if m and int(m.group(1)) in validos:
        return int(m.group(1))

    años = [int(a) for a in re.findall(r"\b(20\d{2})\b", cabecera[:2000]) if int(a) in validos]
    if años:
        return Counter(años).most_common(1)[0][0]

    m = re.search(r"(20\d{2})", filename)
    return int(m.group(1)) if m and int(m.group(1)) in validos else None
