'use client';

import { Sidebar } from '@/lib/sidebar';

export default function SkillsPage() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Competencias y Habilidades Apetecidas
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
            Descubre las competencias y habilidades más demandadas por los empleadores.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-4">
                Competencias Técnicas
              </h2>
              <ul className="space-y-2 text-zinc-600 dark:text-zinc-400">
                <li>✓ Python y programación</li>
                <li>✓ Cloud Computing (AWS, Azure)</li>
                <li>✓ Machine Learning</li>
                <li>✓ Análisis de datos</li>
                <li>✓ DevOps</li>
              </ul>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-4">
                Competencias Blandas
              </h2>
              <ul className="space-y-2 text-zinc-600 dark:text-zinc-400">
                <li>✓ Comunicación efectiva</li>
                <li>✓ Pensamiento crítico</li>
                <li>✓ Liderazgo</li>
                <li>✓ Trabajo en equipo</li>
                <li>✓ Adaptabilidad</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}