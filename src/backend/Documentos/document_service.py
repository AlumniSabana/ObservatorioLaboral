"""
Servicio de lectura de documentos con Claude.

Permite que el usuario suba un archivo (PDF) y obtenga insights + respuestas a
preguntas sobre él, SIN guardar nada en la base de datos. Flujo:

  1. El PDF se sube a la Files API de Claude (almacenamiento temporal de Anthropic)
     y se obtiene un `file_id`.
  2. Ese `file_id` se referencia tanto para el resumen inicial de insights como
     para cada pregunta de seguimiento del chat (así no se reenvía el archivo
     completo en cada mensaje).

Es efímero: el frontend conserva el `file_id` solo durante la sesión del navegador.
No hay tabla ni persistencia en Supabase.

Requiere la dependencia `anthropic` y la variable de entorno ANTHROPIC_API_KEY.
"""

import io
from typing import Iterator
import anthropic

from config import ANTHROPIC_API_KEY

# Beta header de la Files API de Claude (necesario para subir y referenciar archivos).
FILES_BETA = "files-api-2025-04-14"
# Modelo con contexto de 1M de tokens: necesario para PDFs largos (ej. reportes).
MODELO = "claude-sonnet-4-6"

# Reglas de comportamiento del asistente al leer el documento.
SYSTEM_PROMPT = """
Eres un analista experto del Observatorio Laboral de Alumni Sabana. El usuario te
ha proporcionado un DOCUMENTO (adjunto a este mensaje) y quiere entenderlo.

Normas obligatorias:
- Básate ÚNICAMENTE en el contenido del documento adjunto. No uses conocimiento
  externo ni inventes datos. Si algo no está en el documento, indícalo con claridad.
- Responde siempre en español, claro y profesional, fácil de entender a la primera.
- Cita cifras y datos concretos del documento cuando existan; puedes hacer cálculos
  (porcentajes, comparaciones, totales) a partir de esas cifras.
- Usa formato Markdown: encabezados (##), negritas y listas para que sea legible.
  Si usas una tabla, escribe CADA FILA EN SU PROPIA LÍNEA (incluida la separadora
  | --- | --- |) y prefiere tablas de pocas columnas.
""".strip()


def _client():
    """Crea el cliente de Anthropic.

    El import de `anthropic` es perezoso (dentro de la función) para que el resto
    del backend siga funcionando aunque la librería todavía no esté instalada.
    """


    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY no está configurada en el backend (src/backend/.env)."
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def subir_documento(file_bytes: bytes, filename: str, content_type: str = "application/pdf") -> str:
    """Sube el archivo a la Files API de Claude y devuelve su file_id."""
    client = _client()
    uploaded = client.beta.files.upload(
        file=(filename, io.BytesIO(file_bytes), content_type),
        betas=[FILES_BETA],
    )
    return uploaded.id


def stream_respuesta(file_id: str, mensaje: str) -> Iterator[str]:
    """Genera, en streaming, la respuesta de Claude sobre el documento indicado.

    Devuelve fragmentos de texto a medida que el modelo los produce.
    """
    client = _client()
    with client.beta.messages.stream(
        betas=[FILES_BETA],
        model=MODELO,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    # Referencia al PDF previamente subido (no se reenvía el archivo).
                    {"type": "document", "source": {"type": "file", "file_id": file_id}},
                    {"type": "text", "text": mensaje},
                ],
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            yield text
