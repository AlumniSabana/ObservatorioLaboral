'use client';

/**
 * Lector de documentos ("Leer un documento").
 *
 * Se muestra en la página de análisis cuando el usuario elige esa opción en el
 * combo box. Flujo:
 *   1. El usuario sube un PDF (que descargó por fuera).
 *   2. Se envía al backend FastAPI (POST /documento/subir), que lo sube a la
 *      Files API de Claude y devuelve un file_id.
 *   3. Se pide un resumen de insights y se muestra en streaming.
 *   4. El usuario puede hacer preguntas de seguimiento sobre el documento.
 *
 * NO se guarda nada en base de datos: el file_id vive solo en esta sesión del
 * navegador; al recargar o cambiar de fuente, se pierde.
 */

import { useRef, useState } from 'react';
import { Send, FileUp, FileText } from 'lucide-react';
import { AssistantContent } from './markdown';

interface DocMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

// Prompt inicial: pide un resumen estructurado de los insights del documento.
const PROMPT_INSIGHTS =
  'Extrae y resume los insights más importantes de este documento: hallazgos clave, ' +
  'tendencias, cifras relevantes y conclusiones. Estructúralo con encabezados y listas, en español.';

export function DocumentReader({ backendUrl }: { backendUrl: string }) {
  const [fileId, setFileId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  // "preparing": el archivo ya se subió y estamos esperando que Claude empiece a
  // responder. Mantiene el indicador de carga hasta que llega el primer fragmento
  // (con PDFs grandes esto puede tardar) para que no parezca que la app falló.
  const [preparing, setPreparing] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<DocMessage[]>([]);
  const [input, setInput] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pide una respuesta al backend sobre el documento y la muestra en streaming.
  // showUser=false para el resumen inicial (no pintamos una burbuja de usuario).
  // isInitial=true para el resumen tras subir: limpia el indicador de carga en
  // cuanto empieza a llegar la respuesta.
  const ask = async (docId: string, message: string, showUser: boolean, isInitial = false) => {
    setError(null);
    setStreaming(true);
    const assistantId = `${Date.now()}-a`;

    if (showUser) {
      setMessages((prev) => [...prev, { id: `${Date.now()}-u`, role: 'user', content: message }]);
    }
    setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }]);

    try {
      const res = await fetch(`${backendUrl}/documento/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: docId, message }),
      });

      if (!res.ok || !res.body) {
        let detalle = `HTTP ${res.status}`;
        try {
          const data = await res.json();
          detalle = data.error || detalle;
        } catch {
          /* el cuerpo no era JSON */
        }
        throw new Error(detalle);
      }

      // Leemos el stream de texto y vamos rellenando la burbuja del asistente.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acumulado = '';
      let primerFragmento = true;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        acumulado += decoder.decode(value, { stream: true });
        if (primerFragmento) {
          primerFragmento = false;
          // Empezó el streaming: ya podemos quitar el indicador de carga.
          if (isInitial) setPreparing(false);
        }
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: acumulado } : m)),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error desconocido';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `⚠️ Ocurrió un error al leer el documento: ${msg}` }
            : m,
        ),
      );
    } finally {
      setStreaming(false);
      // Por si falló antes del primer fragmento, garantizamos que el indicador
      // de carga se quite (para mostrar el mensaje de error).
      if (isInitial) setPreparing(false);
    }
  };

  // Sube el archivo al backend y dispara el resumen inicial de insights.
  const handleFile = async (file: File) => {
    setError(null);
    setMessages([]);
    setFileId(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${backendUrl}/documento/subir`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      setFileId(data.file_id);
      setFilename(data.filename || file.name);
      // Pasamos de "subiendo" a "preparando": el indicador de carga se mantiene
      // hasta que Claude empiece a responder (lo limpia ask() en isInitial).
      setUploading(false);
      setPreparing(true);

      // Resumen inicial automático (sin burbuja de usuario).
      await ask(data.file_id, PROMPT_INSIGHTS, false, true);
    } catch (err) {
      setUploading(false);
      setPreparing(false);
      setError(err instanceof Error ? err.message : 'Error al subir el documento');
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !fileId || streaming) return;
    const pregunta = input;
    setInput('');
    ask(fileId, pregunta, true);
  };

  // ----- Estado inicial: zona de carga -----
  if (!fileId && !uploading && !preparing) {
    return (
      <div className="space-y-4">
        <div
          className="rounded-lg p-10 text-center border-2 border-dashed cursor-pointer transition-colors"
          style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--sabana-sky-blue)' }}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
        >
          <FileUp size={40} className="mx-auto mb-3" style={{ color: 'var(--sabana-navy)' }} />
          <p className="font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
            Sube un PDF para analizarlo con Claude
          </p>
          <p className="text-sm mt-1" style={{ color: 'var(--sabana-navy)' }}>
            Arrastra el archivo aquí o haz clic para seleccionarlo
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
        </div>
        {error && (
          <div className="bg-red-100 rounded-lg p-4 text-red-700 text-sm">❌ {error}</div>
        )}
      </div>
    );
  }

  // ----- Subiendo / preparando: el indicador se mantiene hasta que Claude
  // empieza a responder (clave para PDFs grandes, que tardan en procesarse). -----
  if (uploading || preparing) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2 text-center">
        <p className="text-lg font-bold text-zinc-600">
          {uploading ? '⏳ Subiendo el documento...' : '⏳ Leyendo el documento con Claude...'}
        </p>
        {preparing && (
          <p className="text-sm text-zinc-500">
            Esto puede tardar varios segundos con archivos grandes. No cierres la página.
          </p>
        )}
      </div>
    );
  }

  // ----- Documento cargado: insights + chat de seguimiento -----
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--sabana-dark-navy)' }}>
        <FileText size={18} />
        <span className="font-bold truncate">{filename}</span>
        <button
          onClick={() => {
            setFileId(null);
            setFilename(null);
            setMessages([]);
          }}
          className="ml-auto text-xs px-3 py-1 rounded-lg font-semibold"
          style={{ backgroundColor: 'var(--sabana-navy)', color: 'white' }}
        >
          Cambiar documento
        </button>
      </div>

      <div className="space-y-4">
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`px-4 py-3 rounded-lg ${
                m.role === 'user'
                  ? 'text-white rounded-br-none max-w-[80%]'
                  : 'bg-white dark:bg-zinc-800 shadow text-black dark:text-white rounded-bl-none max-w-full w-full'
              }`}
              style={m.role === 'user' ? { backgroundColor: 'var(--sabana-navy)' } : {}}
            >
              {m.role === 'assistant' ? (
                m.content ? (
                  <AssistantContent content={m.content} />
                ) : (
                  <span className="inline-block w-2 h-4 bg-zinc-500 animate-pulse align-middle" />
                )
              ) : (
                <p className="text-sm">{m.content}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Pregunta de seguimiento sobre el documento */}
      <form onSubmit={onSubmit} className="flex gap-2 pt-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregunta algo sobre el documento..."
          disabled={streaming}
          className="flex-1 px-3 py-2 rounded border border-zinc-300 dark:border-zinc-600 dark:bg-zinc-700 dark:text-white text-sm focus:outline-none focus:ring-2 disabled:opacity-50"
          style={{ '--tw-ring-color': 'var(--sabana-navy)' } as React.CSSProperties}
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="text-white rounded p-2 transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{ backgroundColor: 'var(--sabana-navy)' }}
          aria-label="Enviar pregunta"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
