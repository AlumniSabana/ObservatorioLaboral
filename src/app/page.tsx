'use client';

import { Sidebar } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function Home() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-87 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Bienvenido al Observatorio Laboral
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
            Explora el mercado laboral, tendencias de empleo y competencias demandadas por las empresas.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
                📊 Tendencias en Formación
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400">
                Analiza las tendencias actuales en los modelos de formación y educación continua
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
                💼 Competencias y Habilidades
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400">
                Descubre las competencias más apetecidas por los empleadores
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
                💰 Análisis Salarial
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400">
                Explora información sobre salarios en diferentes sectores
              </p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
                🏢 Sectores y Empresas
              </h2>
              <p className="text-zinc-600 dark:text-zinc-400">
                Conoce los principales sectores y empresas empleadoras
              </p>
            </div>
          </div>

          <p className="mt-8 text-sm text-zinc-500 dark:text-zinc-400">
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