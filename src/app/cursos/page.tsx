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
//  - Google Skills:    ?keywords=...&locale=es  (espacios como '+', en español)
//  - IBM Training:     ?query=...
//  - Coursera:         ?query=...
//  - LinkedIn Learning:?keywords=...
const urlGoogleSkills = (q: string) =>
  `https://www.skills.google/catalog?keywords=${encodeURIComponent(q).replace(/%20/g, '+')}&locale=es`;
const urlIbmTraining = (q: string) =>
  `https://www.ibm.com/training/search?query=${encodeURIComponent(q)}`;
const urlCoursera = (q: string) =>
  `https://www.coursera.org/search?query=${encodeURIComponent(q)}`;
const urlLinkedInLearning = (q: string) =>
  `https://www.linkedin.com/learning/search?keywords=${encodeURIComponent(q)}`;

// Plataformas que ofrece el buscador. Para añadir otra, basta con sumarla aquí.
// `soloTecnicas`: el catálogo de esa plataforma es SOLO competencias técnicas (sin
// power skills) — se marca con un color distinto (ver leyenda bajo los botones) para
// que quede claro antes de hacer clic, no después de aterrizar en un catálogo que no
// tiene lo que se buscaba.
const PLATAFORMAS = [
  { nombre: 'Coursera', url: urlCoursera, color: 'var(--sabana-dark-navy)', soloTecnicas: false },
  { nombre: 'LinkedIn Learning', url: urlLinkedInLearning, color: 'var(--sabana-navy)', soloTecnicas: false },
  { nombre: 'Google Skills', url: urlGoogleSkills, color: 'var(--cat-5)', soloTecnicas: true },
  { nombre: 'IBM Training', url: urlIbmTraining, color: 'var(--sabana-dark-navy)', soloTecnicas: false },
];

// Traducción ES->EN antes de mandar la búsqueda a IBM Training: su catálogo no
// tiene cursos en español, así que buscar en español ahí devuelve poco o nada.
// MyMemory es gratis, sin API key y admite llamadas desde el navegador (CORS
// abierto) — verificado. Si falla (red, cuota), se usa el término tal cual: es
// mejor una búsqueda en español que ninguna búsqueda.
async function traducirParaIbm(q: string): Promise<string> {
  try {
    const r = await fetch(
      `https://api.mymemory.translated.net/get?q=${encodeURIComponent(q)}&langpair=es|en`,
    );
    if (!r.ok) return q;
    const d = await r.json();
    const traducido = d?.responseData?.translatedText;
    return typeof traducido === 'string' && traducido.trim() ? traducido : q;
  } catch {
    return q;
  }
}

export default function CursosPage() {
  const [campo, setCampo] = useState('');
  const [traduciendo, setTraduciendo] = useState(false);

  // Abre la plataforma (construyendo su URL con el término) en una pestaña NUEVA.
  const abrir = (construirUrl: (q: string) => string) => {
    const q = campo.trim();
    if (!q) return;
    window.open(construirUrl(q), '_blank', 'noopener,noreferrer');
  };

  // IBM necesita el término en inglés. La traducción es async, y abrir la
  // pestaña DESPUÉS de un await hace que varios navegadores lo bloqueen por
  // "no viene de un gesto directo del usuario" — por eso se abre una pestaña
  // en blanco de inmediato (todavía dentro del clic) y se le asigna la URL
  // real cuando la traducción vuelve, en vez de abrir la pestaña al final.
  const abrirIbm = async () => {
    const q = campo.trim();
    if (!q) return;
    // Sin 'noopener'/'noreferrer' aquí A PROPÓSITO: con cualquiera de los dos,
    // window.open() devuelve null en la mayoría de navegadores (es como el
    // navegador implementa "sin opener": si no hay forma de tocar la ventana
    // nueva, tampoco te da la referencia) — sin la referencia no hay forma de
    // redirigirla después. El destino es siempre ibm.com/training/search
    // (fijo, construido acá mismo, nunca viene del usuario), así que el riesgo
    // de "reverse tabnabbing" que noopener evita no aplica: no es un link
    // externo arbitrario.
    const ventana = window.open('', '_blank');
    setTraduciendo(true);
    const traducido = await traducirParaIbm(q);
    setTraduciendo(false);
    if (ventana) ventana.location.href = urlIbmTraining(traducido);
  };

  const deshabilitado = campo.trim().length === 0;

  return (
    <>
      <PageLayout title="Cursos y formación: competencias técnicas y power skills">
        <div className="space-y-8">
          <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
            Escribe un <strong>campo de estudio o rama de interés</strong> y explóralo en Coursera,
            LinkedIn Learning, Google Skills o IBM Training. La plataforma se abrirá en una pestaña nueva.
          </p>

          {/* Buscador */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
            <label htmlFor="campo-input" className="block text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
              Campo de estudio o rama de interés
            </label>

            <div className="flex items-center gap-2 rounded-lg px-3 py-2 border" style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--sabana-sky-blue)' }}>
              <Search size={18} style={{ color: 'var(--sabana-navy)' }} />
              <input
                id="campo-input"
                type="text"
                value={campo}
                onChange={(e) => setCampo(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && abrir(PLATAFORMAS[0].url)}
                placeholder="Ej. inteligencia artificial, enfermería, finanzas, ciberseguridad…"
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: 'var(--sabana-dark-navy)' }}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
              {PLATAFORMAS.map((p) => {
                const esIbm = p.nombre === 'IBM Training';
                const ocupado = esIbm && traduciendo;
                return (
                  <button
                    key={p.nombre}
                    onClick={() => (esIbm ? abrirIbm() : abrir(p.url))}
                    disabled={deshabilitado || ocupado}
                    className="flex items-center justify-center gap-2 px-5 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
                    style={{
                      backgroundColor: p.color,
                      color: 'white',
                      cursor: deshabilitado || ocupado ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {ocupado ? 'Traduciendo…' : `Buscar en ${p.nombre}`} <ExternalLink size={16} />
                  </button>
                );
              })}
            </div>

            {/* Convención de color: qué plataformas cubren solo competencias
                técnicas frente a las que también tienen power skills. */}
            <div className="flex items-center gap-2 mt-3 text-xs" style={{ color: 'var(--sabana-black-50)' }}>
              <span className="inline-block w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: 'var(--cat-5)' }} />
              <span>Solo competencias técnicas (sin power skills) — hoy: Google Skills.</span>
            </div>
            <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
              IBM Training no tiene catálogo en español: el término se traduce automáticamente al inglés
              antes de buscar.
            </p>

            {deshabilitado && (
              <p className="text-xs text-zinc-500 mt-3">Escribe un campo para habilitar la búsqueda.</p>
            )}
          </div>

          {/* Descripción de cada plataforma */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--sabana-light-blue)' }}>
                Coursera
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Cursos, certificados profesionales y títulos de universidades y empresas
                (Google, IBM, Meta, Stanford). Muchos con subtítulos en español y opción
                de auditar el contenido de forma gratuita.
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--sabana-light-blue)' }}>
                LinkedIn Learning
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Formación corta y orientada al trabajo en tecnología, negocios y habilidades
                blandas. Los certificados se pueden añadir directamente al perfil de LinkedIn.
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--sabana-light-blue)' }}>
                Google Skills
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Plataforma de formación de Google con miles de cursos, laboratorios y credenciales
                (Google Cloud, IA, Grow with Google, Google for Education).
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--sabana-light-blue)' }}>
                IBM Training
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
        pageContent="Página con un buscador que abre Coursera (coursera.org), LinkedIn Learning (linkedin.com/learning), Google Skills (skills.google) e IBM Training (ibm.com/training) filtrados por el campo de estudio que el usuario escriba, para encontrar cursos. Las plataformas se abren en una pestaña nueva. Google Skills solo tiene competencias técnicas (sin power skills), marcado con un color distinto. IBM Training no tiene catálogo en español: el término se traduce automáticamente al inglés antes de buscar."
      />
    </>
  );
}
