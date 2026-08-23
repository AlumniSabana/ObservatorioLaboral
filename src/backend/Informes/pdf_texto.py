"""
pdf_texto.py — texto plano de un PDF, página por página.

Es la base de la VERIFICACIÓN ANTI-ALUCINACIÓN del extractor: Claude debe devolver
una cita literal y su página, y aquí se obtiene el texto real contra el que se
comprueba. Sin esto no habría forma de auditar lo que el modelo afirma.

Solo PDFs con capa de texto. Un PDF escaneado (imagen) devuelve texto vacío y el
extractor lo rechaza con un mensaje claro: es preferible no ingerir un informe a
ingerirlo sin poder comprobar de dónde salió cada cifra.
"""

from __future__ import annotations

import io
import re
import unicodedata


def texto_por_pagina(pdf_bytes: bytes) -> dict[int, str]:
    """{n_pagina (1-based): texto}. Devuelve {} si no se puede leer."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(
            "Falta la librería 'pypdf' para leer PDFs. Instálala con: pip install pypdf"
        )

    try:
        lector = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF: {e}")

    paginas: dict[int, str] = {}
    for i, pagina in enumerate(lector.pages, start=1):
        try:
            paginas[i] = pagina.extract_text() or ""
        except Exception:
            paginas[i] = ""
    return paginas


def tiene_capa_de_texto(paginas: dict[int, str], minimo_chars: int = 200) -> bool:
    """True si el PDF trae texto seleccionable (no es un escaneo)."""
    return sum(len(t) for t in paginas.values()) >= minimo_chars


def normalizar_para_cotejo(texto: str) -> str:
    """
    Normaliza para comparar citas: minúsculas, sin tildes, sin guiones suaves ni
    ligaduras, y con los espacios colapsados.

    Hace falta porque el texto extraído de un PDF casi nunca coincide carácter a
    carácter con lo que "ve" el modelo: aparecen guiones de corte de línea, saltos
    en medio de una frase, comillas tipográficas y ligaduras (ﬁ, ﬂ).
    """
    if not texto:
        return ""
    # Ligaduras y guiones/comillas tipográficas -> equivalente simple.
    reemplazos = {
        "ﬁ": "fi", "ﬂ": "fl", "­": "", "‐": "-", "‑": "-",
        "‒": "-", "–": "-", "—": "-", "‘": "'", "’": "'",
        "“": '"', "”": '"', " ": " ",
    }
    for viejo, nuevo in reemplazos.items():
        texto = texto.replace(viejo, nuevo)

    # Quitar tildes.
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    # Un PDF corta palabras al final de línea: "genera-\ntive" -> "generative".
    texto = re.sub(r"-\s*\n\s*", "", texto)
    return re.sub(r"\s+", " ", texto).strip().lower()
