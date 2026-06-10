'use client';

/**
 * Página de inicio (ruta '/').
 *
 * Es la portada del Observatorio: muestra un mensaje de bienvenida y unas tarjetas
 * que describen las secciones disponibles. El contenido es estático (no consume
 * el backend); la navegación real se hace desde la barra lateral.
 */

import { Sidebar } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function Home() {
  return (
    <div className="flex min-h-screen" style={{backgroundColor: 'var(--white-background)'}}>
      <Sidebar />
      <main className="ml-80 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold mb-2" style={{color: 'var(--sabana-dark-navy)'}}>
            Bienvenido al Observatorio Laboral
          </h1>
          <div className="h-1 w-20 rounded mb-8" style={{backgroundColor: 'var(--sabana-navy)'}}></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8" style ={{color: 'var(--sabana-dark-navy)'}}  >
            Explora el mercado laboral, tendencias de empleo y competencias demandadas por las empresas.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
              <h2 className="text-xl font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
                📊 Tendencias en formación
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400" style={{color: 'var(--white-background)'}}>
                Analiza las tendencias actuales en los modelos de formación y educación continua
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
              <h2 className="text-xl font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
                💼 Competencias y habilidades
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400" style={{color: 'var(--white-background)'}}>
                Descubre las competencias más apetecidas por los empleadores
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
              <h2 className="text-xl font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
                💰 Análisis salarial
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400" style={{color: 'var(--white-background)'}}>
                Explora información sobre salarios en diferentes sectores
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
              <h2 className="text-xl font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
                🏢 Sectores y empresas
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400" style={{color: 'var(--white-background)'}}>
                Conoce los principales sectores y empresas empleadoras
              </p>
            </div>
          </div>

          <p className="mt-8 text-sm text-zinc-500 dark:text-zinc-400" style={{color: 'var(--sabana-dark-navy)'}}>
            Usa la barra lateral para navegar entre las diferentes secciones del observatorio.
          </p>
        </div>
      </main>

      <FloatingChat
        pageTitle="Bienvenido al Observatorio Laboral"
        pageContent="Página principal del Observatorio Laboral con acceso a: Tendencias en Formación, Competencias y Habilidades Apetecidas, Análisis Salarial, Sectores y Empresas, Condiciones Laborales Actuales, y Mayor Demanda Actual."
      />
    </div>
  );
}