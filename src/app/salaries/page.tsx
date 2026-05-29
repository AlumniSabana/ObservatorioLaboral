'use client';

import { Sidebar } from '@/lib/sidebar';

export default function SalariesPage() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Análisis Salarial
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
            Analiza los salarios promedio en diferentes sectores y roles.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-4">
                Salarios por Sector
              </h2>
              <ul className="space-y-2 text-zinc-600 dark:text-zinc-400">
                <li>• Tecnología: $80,000 - $120,000</li>
                <li>• Finanzas: $75,000 - $110,000</li>
                <li>• Manufactura: $50,000 - $80,000</li>
                <li>• Educación: $45,000 - $70,000</li>
              </ul>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-black dark:text-white mb-4">
                Salarios por Experiencia
              </h2>
              <ul className="space-y-2 text-zinc-600 dark:text-zinc-400">
                <li>• Junior (0-2 años): $35,000 - $50,000</li>
                <li>• Semi-Senior (2-5 años): $50,000 - $75,000</li>
                <li>• Senior (5-10 años): $75,000 - $120,000</li>
                <li>• Manager: $100,000 - $180,000</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}