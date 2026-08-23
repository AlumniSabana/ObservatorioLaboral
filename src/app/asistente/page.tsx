'use client';

/**
 * Página "Empresas" (ruta '/asistente') — chatbot de empresas y cultura.
 *
 * Explora estructura y cultura organizacional, clima laboral, tendencias de
 * ascensos y rankings de empleadores (Great Place to Work).
 *
 * Cómo se alimenta:
 *   1. Al cargar, pide a GET /asistente/contexto el resumen FACTUAL del
 *      Observatorio (empresas que contratan, sectores, cargos, salarios).
 *   2. Ese contexto viaja a /api/chat con modo='empresas', que instruye a Gemini
 *      para usar primero esos datos reales y, si la pregunta va más allá,
 *      responder con conocimiento general DECLARÁNDOLO y sin inventar cifras.
 *
 * Estado inicial: logo + preguntas sugeridas centrados. Al enviar el primer
 * mensaje se deslizan hacia arriba y desaparecen, dejando la conversación.
 */

import { PageLayout } from '@/lib/sidebar';
import { AssistantContent } from '@/lib/markdown';
import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { Send } from 'lucide-react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Mensaje {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

// Preguntas sugeridas del estado inicial (los "chips").
const SUGERENCIAS = [
  {
    etiqueta: 'Empresas colombianas',
    pregunta:
      '¿Qué empresas están contratando en Colombia y en qué sectores? Cuéntame también cómo suele ser su cultura organizacional.',
  },
  {
    etiqueta: 'Great Place to Work',
    pregunta:
      '¿Qué empresas destacan en el ranking Great Place to Work en Colombia y qué posiciones han ocupado? Explícame también cómo se mide y qué hace que una empresa como Globant figure ahí.',
  },
];

// "Empresas por sector" ya NO es un único chip quemado a Tecnología (TI): son
// los sectores REALES con más contratación en el Observatorio (verificado
// contra /asistente/contexto — Ingeniería y Tecnología encabezan, no solo TI),
// uno por botón, para que el usuario elija cuál explorar.
const SECTORES_SUGERIDOS = [
  'Ingeniería',
  'Tecnología (TI)',
  'Salud y enfermería',
  'Contabilidad y finanzas',
  'Educación',
  'Ventas',
];

const preguntaPorSector = (sector: string) =>
  `¿Qué empresas lideran la contratación en el sector de ${sector} y cómo es el clima laboral y las oportunidades de ascenso en ese sector?`;

export default function AsistentePage() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [entrada, setEntrada] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const finRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // Se guarda la PROMESA del contexto, no solo su valor: armarlo en el backend
  // puede tardar (lee toda la muestra histórica). Si el usuario pregunta antes de
  // que llegue, `enviar` la espera en vez de mandar la consulta sin los datos del
  // Observatorio, que son justo la fuente preferente del asistente.
  const contextoRef = useRef<Promise<string> | null>(null);

  // El "hero" (logo + sugerencias) solo se ve mientras no hay conversación.
  const heroVisible = mensajes.length === 0;

  // Contexto real del Observatorio (una sola vez, al montar).
  useEffect(() => {
    contextoRef.current = (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/asistente/contexto`);
        if (!r.ok) return '';
        const d = await r.json();
        return (d.contexto as string) ?? '';
      } catch {
        // Sin contexto el asistente sigue sirviendo, solo que sin datos del
        // Observatorio; el prompt ya contempla ese caso.
        return '';
      }
    })();
  }, []);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensajes]);

  const enviar = async (texto: string) => {
    const pregunta = texto.trim();
    if (!pregunta || cargando) return;

    setError(null);
    setEntrada('');
    setCargando(true);

    const historial = mensajes.map((m) => ({ role: m.role, content: m.content }));
    const idUsuario = `${Date.now()}`;
    const idAsistente = `${Date.now() + 1}`;

    setMensajes((prev) => [...prev, { id: idUsuario, role: 'user', content: pregunta }]);

    try {
      // Espera a que el contexto del Observatorio esté disponible (ver contextoRef).
      const contexto = (await contextoRef.current) ?? '';

      const respuesta = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: pregunta,
          modo: 'empresas',
          pageTitle: 'Empresas — cultura organizacional',
          pageContent: contexto,
          history: historial,
        }),
      });

      if (!respuesta.ok || !respuesta.body) {
        let detalle = `HTTP ${respuesta.status}`;
        try {
          const err = await respuesta.json();
          detalle = err.error || detalle;
        } catch {
          /* el cuerpo no era JSON */
        }
        throw new Error(detalle);
      }

      setMensajes((prev) => [...prev, { id: idAsistente, role: 'assistant', content: '' }]);

      const reader = respuesta.body.getReader();
      const decoder = new TextDecoder();
      let acumulado = '';
      let primero = true;

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        acumulado += decoder.decode(value, { stream: true });
        if (primero) {
          setCargando(false);
          primero = false;
        }
        setMensajes((prev) =>
          prev.map((m) => (m.id === idAsistente ? { ...m, content: acumulado } : m)),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo obtener respuesta');
    } finally {
      setCargando(false);
      inputRef.current?.focus();
    }
  };

  const alTeclear = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviar(entrada);
    }
  };

  return (
    <PageLayout title="Empresas">
      {/* `height` fijo (no `minHeight`): así el hijo "Conversación" puede tener
          `overflow-y-auto` y hacer scroll DENTRO de su propio recuadro en vez de
          estirar la página entera a medida que se generan mensajes. Con
          `minHeight` el contenedor crecería con el contenido y nunca daría pie
          a que el hijo necesitara su propio scroll. */}
      <div className="flex flex-col" style={{ height: 'calc(100vh - 12rem)' }}>
        {/* ---------- Hero: logo + sugerencias (se desliza al primer mensaje) ---------- */}
        <div
          className="overflow-hidden transition-all duration-700 ease-in-out"
          style={{
            maxHeight: heroVisible ? '640px' : '0px',
            opacity: heroVisible ? 1 : 0,
            transform: heroVisible ? 'translateY(0)' : 'translateY(-2.5rem)',
          }}
          aria-hidden={!heroVisible}
        >
          <div className="relative flex flex-col items-center text-center py-10 px-4 rounded-2xl overflow-hidden">
            {/* Fondo: logos de empresas que contratan a egresados de La Sabana.
                Encima va una capa clara (blanca en modo claro, oscura en modo
                oscuro) para que el texto siga siendo legible sobre tantos logos. */}
            <div
              className="absolute inset-0 bg-cover bg-center"
              style={{ backgroundImage: 'url(/empresas-logos-bg.jpg)' }}
              aria-hidden="true"
            />
            <div className="absolute inset-0 bg-white/85 dark:bg-zinc-900/85" aria-hidden="true" />

            <div className="relative z-10 flex flex-col items-center">
              <div
                className="rounded-2xl px-10 py-8 mb-6"
                style={{ backgroundColor: 'var(--sabana-dark-navy)' }}
              >
                <Image
                  src="/logo-alumni.png"
                  alt="Logo Alumni Sabana"
                  width={260}
                  height={100}
                  className="w-56 h-auto"
                  priority
                />
              </div>

              <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                ¿Qué quieres saber sobre las empresas?
              </h2>
              <p className="text-sm max-w-2xl mb-8" style={{ color: 'var(--sabana-black-50)' }}>
                Explora la estructura y cultura organizacional, el clima laboral, las
                tendencias de ascensos y los rankings de empleadores como Great Place to Work.
              </p>

              <div className="flex flex-wrap gap-3 justify-center">
                {SUGERENCIAS.map((s) => (
                  <button
                    key={s.etiqueta}
                    onClick={() => enviar(s.pregunta)}
                    disabled={cargando}
                    className="px-5 py-3 rounded-xl text-sm font-semibold border transition-colors cursor-pointer disabled:opacity-50"
                    style={{
                      borderColor: 'var(--sabana-light-blue)',
                      color: 'var(--sabana-dark-navy)',
                      backgroundColor: 'var(--sabana-sky-blue)',
                    }}
                  >
                    {s.etiqueta}
                  </button>
                ))}

                {/* `w-full` fuerza el salto de línea dentro del flex-wrap: separa
                    visualmente el grupo "por sector" de los chips generales de
                    arriba, sin montar una fila aparte. */}
                <span className="w-full text-xs font-semibold mt-1" style={{ color: 'var(--sabana-black-50)' }}>
                  Empresas por sector
                </span>
                {SECTORES_SUGERIDOS.map((sector) => (
                  <button
                    key={sector}
                    onClick={() => enviar(preguntaPorSector(sector))}
                    disabled={cargando}
                    className="px-4 py-2 rounded-xl text-sm font-semibold border transition-colors cursor-pointer disabled:opacity-50"
                    style={{
                      borderColor: 'var(--sabana-light-blue)',
                      color: 'var(--sabana-dark-navy)',
                      backgroundColor: 'var(--white-background)',
                    }}
                  >
                    {sector}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ---------- Conversación ---------- */}
        {/* `min-h-0` es necesario junto a `flex-1`: por defecto un hijo flex no
            se encoge más allá del alto de su contenido (min-height: auto), así
            que sin esto `overflow-y-auto` nunca llegaría a activarse y el
            contenedor seguiría empujando la página hacia abajo igual que antes. */}
        <div className="flex-1 min-h-0 overflow-y-auto space-y-4 mb-4 pr-1">
          {mensajes.map((m) => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className="max-w-[85%] rounded-2xl px-4 py-3 text-base"
                style={
                  m.role === 'user'
                    ? { backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }
                    : {
                        backgroundColor: 'var(--white-background)',
                        color: 'var(--sabana-dark-navy)',
                        border: '1px solid var(--sabana-sky-blue)',
                      }
                }
              >
                {m.role === 'assistant' ? (
                  <AssistantContent content={m.content} />
                ) : (
                  <span className="whitespace-pre-wrap">{m.content}</span>
                )}
              </div>
            </div>
          ))}

          {cargando && (
            <div className="flex justify-start">
              <div
                className="rounded-2xl px-4 py-3 text-base"
                style={{
                  backgroundColor: 'var(--white-background)',
                  border: '1px solid var(--sabana-sky-blue)',
                  color: 'var(--sabana-black-50)',
                }}
              >
                Pensando…
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">{error}</div>
          )}

          <div ref={finRef} />
        </div>

        {/* ---------- Entrada ---------- */}
        <div
          className="sticky bottom-0 pt-2 pb-4"
          style={{ backgroundColor: 'var(--white-background)' }}
        >
          <div
            className="flex items-end gap-2 rounded-2xl border p-2"
            style={{ borderColor: 'var(--sabana-light-blue)' }}
          >
            <textarea
              ref={inputRef}
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
              onKeyDown={alTeclear}
              rows={1}
              placeholder="Pregunta por una empresa, un sector o su cultura…"
              className="flex-1 resize-none bg-transparent px-2 py-2 text-base outline-none"
              style={{ color: 'var(--sabana-dark-navy)', maxHeight: '8rem' }}
            />
            <button
              onClick={() => enviar(entrada)}
              disabled={cargando || !entrada.trim()}
              aria-label="Enviar mensaje"
              className="rounded-xl p-3 text-white transition-opacity disabled:opacity-40"
              style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: 'pointer' }}
            >
              <Send size={16} />
            </button>
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--sabana-black-50)' }}>
            Usa los datos del Observatorio cuando existen; si responde con información
            general lo indica. Verifica los rankings en su fuente oficial.
          </p>
        </div>
      </div>
    </PageLayout>
  );
}
