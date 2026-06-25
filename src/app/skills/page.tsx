'use client';

/**
 * Página "Competencias y habilidades apetecidas" (ruta '/skills').
 *
 * Datos REALES desde O*NET (vía el backend): el usuario elige un programa y se
 * muestran las competencias clave y las tecnologías de la ocupación O*NET
 * asociada (`GET /competencias?programa=...`). El backend cachea las respuestas.
 *
 * Nota: O*NET describe el mercado de EE.UU. y es una referencia normativa de
 * competencias por ocupación (no demanda colombiana de vacantes). Se etiqueta así.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Una competencia o una tecnología: nombre + su explicación en español.
interface Item {
  nombre: string;
  descripcion: string;
}

interface Competencias {
  programa: string;
  habilidades: Item[];
  tecnologias: Item[];
}

export default function SkillsPage() {
  const [programas, setProgramas] = useState<string[]>([]);
  const [programa, setPrograma] = useState<string>('');
  const [data, setData] = useState<Competencias | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Ítem seleccionado (habilidad o tecnología) para mostrar su explicación debajo.
  const [seleccion, setSeleccion] = useState<Item | null>(null);

  // Carga la lista de programas y selecciona el primero.
  const cargarProgramas = async () => {
    setError(null);
    try {
      const r = await fetch(`${BACKEND_URL}/competencias/programas`);
      if (!r.ok) throw new Error('No se pudo cargar la lista de programas');
      const d = await r.json();
      const lista: string[] = d.programas || [];
      setProgramas(lista);
      if (lista.length) {
        setPrograma(lista[0]); // dispara la carga de competencias vía el efecto
      } else {
        setLoading(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido');
      setLoading(false);
    }
  };

  // Carga las competencias del programa seleccionado.
  const cargarCompetencias = async (prog: string) => {
    setLoading(true);
    setError(null);
    setSeleccion(null); // al cambiar de programa, cerramos la explicación anterior
    try {
      const r = await fetch(`${BACKEND_URL}/competencias?programa=${encodeURIComponent(prog)}`);
      if (!r.ok) throw new Error('No se pudieron cargar las competencias');
      const d = await r.json();
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    cargarProgramas();
  }, []);

  useEffect(() => {
    if (!programa) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    cargarCompetencias(programa);
  }, [programa]);

  // Selector de programa (siempre visible).
  const selector = (
    <div className="mb-6 flex flex-col sm:flex-row sm:items-center gap-2">
      <label htmlFor="programa-select" className="text-sm font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
        Programa académico:
      </label>
      <select
        id="programa-select"
        value={programa}
        onChange={(e) => setPrograma(e.target.value)}
        disabled={programas.length === 0}
        className="rounded-lg px-4 py-2 font-semibold border cursor-pointer"
        style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)', borderColor: 'var(--sabana-light-blue)' }}
      >
        {programas.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
    </div>
  );

  const sinDatos = data && data.habilidades.length === 0 && data.tecnologias.length === 0;

  return (
    <>
      <PageLayout title="Competencias y habilidades apetecidas">
        {selector}

        <p className="text-sm mb-6" style={{ color: 'var(--sabana-navy)', fontWeight: 'bold' }}>
          Competencias y tecnologías de referencia según <strong>O*NET</strong> (base de
          ocupaciones del Depto. de Trabajo de EE.UU.). Es una referencia normativa por
          ocupación, no demanda colombiana de vacantes.
        </p>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <p className="text-lg text-zinc-600 font-bold">⏳ Cargando competencias...</p>
          </div>
        )}

        {!loading && error && (
          <div className="bg-red-100 rounded-lg p-6">
            <p className="text-red-700">❌ {error}</p>
            <button
              onClick={() => (programa ? cargarCompetencias(programa) : cargarProgramas())}
              className="mt-4 px-4 py-2 rounded-lg font-semibold transition-colors"
              style={{ backgroundColor: 'var(--sabana-light-blue)', color: 'white' }}
            >
              Reintentar
            </button>
          </div>
        )}

        {!loading && !error && sinDatos && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-8 shadow text-center">
            <p className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
              Sin datos de O*NET para este programa.
            </p>
            <p className="text-sm text-zinc-500 mt-2">
              Verifica que la variable <code>ONET_API_KEY</code> esté configurada en el backend
              (regístrate en services.onetcenter.org/developer/signup).
            </p>
          </div>
        )}

        {!loading && !error && data && !sinDatos && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Competencias / habilidades clave */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--sabana-light-blue)' }}>
                  🧠 Competencias y habilidades clave
                </h3>
                {data.habilidades.length > 0 ? (
                  <>
                    <p className="text-xs text-zinc-500 mb-3">Haz clic en una competencia para ver su explicación.</p>
                    <ul className="space-y-1">
                      {data.habilidades.map((h, i) => {
                        const activa = seleccion?.nombre === h.nombre;
                        return (
                          <li key={i}>
                            <button
                              onClick={() => setSeleccion(activa ? null : h)}
                              className="w-full text-left flex items-start gap-2 text-sm px-2 py-1 rounded cursor-pointer transition-colors"
                              style={{
                                backgroundColor: activa ? 'var(--sabana-dark-navy)' : 'transparent',
                                color: 'var(--white)',
                              }}
                            >
                              <span style={{ color: 'var(--sabana-light-blue)' }}>•</span> {h.nombre}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </>
                ) : (
                  <p className="text-sm text-zinc-500">Sin datos.</p>
                )}
              </div>

              {/* Tecnologías y herramientas (clickables) */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--sabana-light-blue)' }}>
                  💻 Tecnologías y herramientas
                </h3>
                {data.tecnologias.length > 0 ? (
                  <>
                    <p className="text-xs text-zinc-500 mb-3">Haz clic en una herramienta para ver qué es.</p>
                    <div className="flex flex-wrap gap-2">
                      {data.tecnologias.map((t, i) => {
                        const activa = seleccion?.nombre === t.nombre;
                        return (
                          <button
                            key={i}
                            onClick={() => setSeleccion(activa ? null : t)}
                            className="px-3 py-1 rounded-full text-xs font-semibold cursor-pointer transition-colors"
                            style={{
                              backgroundColor: activa ? 'var(--sabana-navy)' : 'var(--sabana-sky-blue)',
                              color: activa ? 'white' : 'var(--sabana-dark-navy)',
                            }}
                          >
                            {t.nombre}
                          </button>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-zinc-500">Sin datos de tecnologías para esta ocupación.</p>
                )}
              </div>
            </div>

            {/* Explicación del ítem seleccionado (competencia o tecnología), debajo de los dos DIVs */}
            {seleccion && (
              <div
                className="mt-6 rounded-lg p-5 shadow border-l-4 flex items-start gap-3"
                style={{ borderColor: 'var(--sabana-navy)', backgroundColor: 'var(--sabana-sky-blue)' }}
              >
                <div className="flex-1">
                  <p className="font-bold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    ¿Qué es {seleccion.nombre}?
                  </p>
                  <p className="text-sm" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {seleccion.descripcion}
                  </p>
                </div>
                <button
                  onClick={() => setSeleccion(null)}
                  className="text-sm font-bold px-2"
                  style={{ color: 'var(--sabana-navy)' }}
                  aria-label="Cerrar explicación"
                >
                  ✕
                </button>
              </div>
            )}
          </>
        )}
      </PageLayout>

      <FloatingChat
        pageTitle="Competencias y Habilidades Apetecidas"
        pageContent={
          data && !sinDatos
            ? `Competencias y tecnologías (fuente: O*NET, EE.UU.) para el programa "${data.programa}". ` +
              `Habilidades clave: ${data.habilidades.map((h) => h.nombre).join(', ') || 'sin datos'}. ` +
              `Tecnologías y herramientas: ${data.tecnologias.map((t) => t.nombre).join(', ') || 'sin datos'}. ` +
              `O*NET es una referencia normativa por ocupación, no demanda colombiana de vacantes.`
            : 'Página de competencias y habilidades apetecidas, con datos de referencia de O*NET (EE.UU.) por programa académico.'
        }
      />
    </>
  );
}
