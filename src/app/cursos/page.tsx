'use client';

/**
 * Página "Cursos y formación" (ruta '/cursos').
 *
 * Buscador que toma un campo de estudio / rama de interés y abre, en una PESTAÑA
 * NUEVA, el catálogo de Google Skills o de IBM Training filtrado por ese término,
 * para que el usuario vea qué cursos ofrecen en ese campo.
 *
 * (Antes esta ruta era '/trends' con contenido estático; se repurposeó.)
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { useState } from 'react';
import { Search, ExternalLink } from 'lucide-react';

// Construye la URL de búsqueda de cada plataforma a partir del término.
//  - Google Skills: ?keywords=...&locale=es  (espacios como '+', en español)
//  - IBM Training:  ?query=...
const urlGoogleSkills = (q: string) =>
  `https://www.skills.google/catalog?keywords=${encodeURIComponent(q).replace(/%20/g, '+')}&locale=es`;
const urlIbmTraining = (q: string) =>
  `https://www.ibm.com/training/search?query=${encodeURIComponent(q)}`;

export default function CursosPage() {
  const [campo, setCampo] = useState('');

  // Abre la plataforma (construyendo su URL con el término) en una pestaña NUEVA.
  const abrir = (construirUrl: (q: string) => string) => {
    const q = campo.trim();
    if (!q) return;
    window.open(construirUrl(q), '_blank', 'noopener,noreferrer');
  };

  const deshabilitado = campo.trim().length === 0;

  return (
    <>
      <PageLayout title="Cursos y formación">
        <div className="space-y-8">
          <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
            Escribe un <strong>campo de estudio o rama de interés</strong> y explóralo en las
            plataformas de formación de Google e IBM. La página se abrirá en una pestaña nueva.
          </p>

          {/* Buscador */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
            <label htmlFor="campo-input" className="block text-sm font-bold mb-2" style={{ color: 'var(--white)' }}>
              Campo de estudio o rama de interés
            </label>

            <div className="flex items-center gap-2 rounded-lg px-3 py-2 border" style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--sabana-sky-blue)' }}>
              <Search size={18} style={{ color: 'var(--sabana-navy)' }} />
              <input
                id="campo-input"
                type="text"
                value={campo}
                onChange={(e) => setCampo(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && abrir(urlGoogleSkills)}
                placeholder="Ej. inteligencia artificial, enfermería, finanzas, ciberseguridad…"
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: 'var(--sabana-dark-navy)' }}
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-3 mt-4">
              <button
                onClick={() => abrir(urlGoogleSkills)}
                disabled={deshabilitado}
                className="flex items-center justify-center gap-2 px-5 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ backgroundColor: 'var(--sabana-navy)', color: 'white', cursor: deshabilitado ? 'not-allowed' : 'pointer' }}
              >
                Buscar en Google Skills <ExternalLink size={16} />
              </button>
              <button
                onClick={() => abrir(urlIbmTraining)}
                disabled={deshabilitado}
                className="flex items-center justify-center gap-2 px-5 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white', cursor: deshabilitado ? 'not-allowed' : 'pointer' }}
              >
                Buscar en IBM Training <ExternalLink size={16} />
              </button>
            </div>

            {deshabilitado && (
              <p className="text-xs text-zinc-500 mt-3">Escribe un campo para habilitar la búsqueda.</p>
            )}
          </div>

          {/* Descripción de cada plataforma */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--sabana-light-blue)' }}>
                🎓 Google Skills
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Plataforma de formación de Google con miles de cursos, laboratorios y credenciales
                (Google Cloud, IA, Grow with Google, Google for Education).
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--sabana-light-blue)' }}>
                💼 IBM Training
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Catálogo de IBM con más de 1.500 cursos, certificaciones, insignias digitales y rutas
                de aprendizaje en tecnologías de IBM (datos, IA, nube, seguridad).
              </p>
            </div>
          </div>
        </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Cursos y formación"
        pageContent="Página con un buscador que abre Google Skills (skills.google) e IBM Training (ibm.com/training) filtrados por el campo de estudio que el usuario escriba, para encontrar cursos. Las plataformas se abren en una pestaña nueva."
      />
    </>
  );
}
