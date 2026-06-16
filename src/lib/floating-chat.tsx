'use client';

/**
 * Widget de chat flotante ("Preguntar a Claude").
 *
 * Aparece como un botón en la esquina inferior derecha de cada página. Al abrirlo,
 * el usuario puede preguntar sobre lo que está viendo. Cada página le pasa dos
 * props que sirven de CONTEXTO para la IA:
 *   - pageTitle:   el título de la sección actual.
 *   - pageContent: una descripción + los datos reales visibles en esa página.
 *
 * El componente envía la pregunta + ese contexto a la ruta /api/chat (ver
 * src/app/api/chat/route.ts), que responde en STREAMING: el texto llega por
 * fragmentos y se va mostrando en pantalla a medida que Claude lo genera
 * (efecto "máquina de escribir"), en lugar de esperar la respuesta completa.
 *
 * Las respuestas vienen en Markdown y se renderizan con <AssistantContent />
 * (definido en src/lib/markdown.tsx, compartido con el lector de documentos).
 *
 * El historial de mensajes es local y efímero: se borra al cerrar el chat.
 */

import { useState, useRef, useEffect } from 'react';
import { X, Send, MessageCircle } from 'lucide-react';
import { AssistantContent } from './markdown';

// Props: el contexto de la página donde se monta el chat.
interface FloatingChatProps {
  pageTitle: string;
  pageContent: string;
}

// Un mensaje del chat (del usuario o de la IA).
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function FloatingChat({ pageTitle, pageContent }: FloatingChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  // Referencia al final de la lista de mensajes, para auto-scrollear hacia abajo.
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Cada vez que cambia el contenido (nuevo mensaje o un fragmento del stream),
  // baja la vista al último.
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Envía la pregunta del usuario y muestra la respuesta de Claude en streaming.
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!inputValue.trim() || isLoading) return;

    const pregunta = inputValue;
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: pregunta,
    };

    // Pintamos de inmediato el mensaje del usuario y mostramos el indicador "..."
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    // Id del mensaje del asistente que iremos rellenando con el stream.
    const assistantId = `${Date.now() + 1}`;

    try {
      // El '/ObservatorioLaboral' es el basePath configurado en next.config.ts.
      // En producción (GitHub Pages) el sitio vive bajo esa subruta, por eso la
      // URL de la ruta API se prefija manualmente aquí.
      const response = await fetch('/ObservatorioLaboral/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: pregunta,
          pageTitle,
          pageContent,
        }),
      });

      if (!response.ok || !response.body) {
        // En error, la ruta devuelve JSON con { error }.
        let detalle = `HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          detalle = errorData.error || detalle;
        } catch {
          /* el cuerpo no era JSON */
        }
        throw new Error(detalle);
      }

      // Creamos la burbuja del asistente vacía y la vamos rellenando.
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let acumulado = '';
      let primerFragmento = true;

      // Leemos el stream fragmento a fragmento y actualizamos el mensaje.
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        acumulado += decoder.decode(value, { stream: true });

        if (primerFragmento) {
          // Al llegar el primer texto, ocultamos el indicador "..."
          setIsLoading(false);
          primerFragmento = false;
        }

        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: acumulado } : m)),
        );
      }
    } catch (error) {
      console.error('Error:', error);
      const mensajeError =
        'Lo siento, ocurrió un error al procesar tu pregunta. Por favor intenta de nuevo.';
      setMessages((prev) => {
        // Si ya existe la burbuja del asistente, le ponemos el error; si no, la creamos.
        if (prev.some((m) => m.id === assistantId)) {
          return prev.map((m) => (m.id === assistantId ? { ...m, content: mensajeError } : m));
        }
        return [...prev, { id: assistantId, role: 'assistant', content: mensajeError }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Botón flotante */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-40 text-white rounded-full p-4 shadow-lg transition-all duration-200 flex items-center gap-2 hover:shadow-xl"
          style={{backgroundColor: 'var(--sabana-navy)'}}
          aria-label="Abrir chat"
        >
          <MessageCircle size={24} />
          <span className="text-sm font-semibold" style={{cursor: 'pointer'}}>Preguntar a Claude</span>
        </button>
      )}

      {/* Ventana del chat */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-[92vw] sm:w-[30rem] h-[75vh] md:h-[34rem] bg-white dark:bg-zinc-800 rounded-lg shadow-2xl flex flex-col border border-zinc-200 dark:border-zinc-700">
          {/* Header */}
          <div className="flex items-center justify-between p-4 text-white rounded-t-lg" style={{backgroundColor: 'var(--sabana-dark-navy)', borderBottomColor: 'var(--sabana-navy)'}}>
            <div>
              <h3 className="font-semibold">
                Asistente Claude
              </h3>
              <p className="text-xs" style={{color: 'var(--sabana-sky-blue)'}}>
                {pageTitle}
              </p>
            </div>
            <button
              onClick={() => {
                setIsOpen(false);
                setMessages([]);
              }}
              className="text-white hover:opacity-80 transition-opacity"
              aria-label="Cerrar chat"
            >
              <X size={20} />
            </button>
          </div>

          {/* Mensajes */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-zinc-500 dark:text-zinc-400 py-8">
                <p className="text-sm">
                  Haz una pregunta sobre lo que estás viendo en esta página
                </p>
              </div>
            )}

            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`px-4 py-2 rounded-lg ${
                    message.role === 'user'
                      ? 'text-white rounded-br-none max-w-[80%]'
                      : 'bg-zinc-200 dark:bg-zinc-700 text-black dark:text-white rounded-bl-none max-w-[90%]'
                  }`}
                  style={message.role === 'user' ? {backgroundColor: 'var(--sabana-navy)'} : {}}
                >
                  {message.role === 'assistant' ? (
                    message.content ? (
                      <AssistantContent content={message.content} />
                    ) : (
                      // Cursor parpadeante mientras llega el primer fragmento del stream.
                      <span className="inline-block w-2 h-4 bg-zinc-500 animate-pulse align-middle" />
                    )
                  ) : (
                    <p className="text-sm">{message.content}</p>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-zinc-200 dark:bg-zinc-700 px-4 py-2 rounded-lg rounded-bl-none">
                  <div className="flex gap-2">
                    <div className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce delay-100" />
                    <div className="w-2 h-2 bg-zinc-500 rounded-full animate-bounce delay-200" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={handleSendMessage}
            className="p-4 border-t border-zinc-200 dark:border-zinc-700 flex gap-2"
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Escribe tu pregunta..."
              disabled={isLoading}
              className="flex-1 px-3 py-2 rounded border border-zinc-300 dark:border-zinc-600 dark:bg-zinc-700 dark:text-white text-sm focus:outline-none focus:ring-2 disabled:opacity-50"
              style={{
                '--tw-ring-color': 'var(--sabana-navy)',
              } as React.CSSProperties}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="text-white rounded p-2 transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{backgroundColor: 'var(--sabana-navy)'}}
              aria-label="Enviar mensaje"
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
