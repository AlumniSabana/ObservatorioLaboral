'use client';

import { Sidebar } from '@/lib/sidebar';

export default function ConditionsPage() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Condiciones Laborales Actuales
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
            Conoce las condiciones laborales prevalecientes en el mercado actual.
          </p>

          <div className="grid grid-cols-1 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-2xl font-semibold text-black dark:text-white mb-4">
                Modalidades de Trabajo
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-700">
                  <span className="text-zinc-700 dark:text-zinc-300">Presencial</span>
                  <span className="font-semibold text-black dark:text-white">25%</span>
                </div>
                <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-700">
                  <span className="text-zinc-700 dark:text-zinc-300">Híbrido</span>
                  <span className="font-semibold text-black dark:text-white">55%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-700 dark:text-zinc-300">Remoto</span>
                  <span className="font-semibold text-black dark:text-white">20%</span>
                </div>
              </div>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-2xl font-semibold text-black dark:text-white mb-4">
                Beneficios Comunes
              </h2>
              <ul className="space-y-2 text-zinc-600 dark:text-zinc-400">
                <li>✓ Seguro de salud</li>
                <li>✓ Plan de pensiones</li>
                <li>✓ Bonificación anual</li>
                <li>✓ Educación continua</li>
                <li>✓ Licencia pagada</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}