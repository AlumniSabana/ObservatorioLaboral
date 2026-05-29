'use client';

import { Sidebar } from '@/lib/sidebar';

export default function TrendsPage() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Tendencias en
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-8 shadow">
            <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-6">
              Descubre las tendencias más importantes en el mercado laboral actual.
            </p>

            <div className="space-y-6">
              <div className="border-l-4 border-blue-600 pl-4">
                <h2 className="text-2xl font-semibold text-black dark:text-white mb-2">
                  Transformación Digital
                </h2>
                <p className="text-zinc-600 dark:text-zinc-400">
                  La automatización y la adopción de tecnologías digitales continúan siendo
                  las tendencias dominantes en el mercado laboral.
                </p>
              </div>

              <div className="border-l-4 border-green-600 pl-4">
                <h2 className="text-2xl font-semibold text-black dark:text-white mb-2">
                  Trabajo Flexible
                </h2>
                <p className="text-zinc-600 dark:text-zinc-400">
                  El trabajo remoto e híbrido se ha consolidado como una tendencia permanente
                  en muchas organizaciones.
                </p>
              </div>

              <div className="border-l-4 border-purple-600 pl-4">
                <h2 className="text-2xl font-semibold text-black dark:text-white mb-2">
                  Sostenibilidad
                </h2>
                <p className="text-zinc-600 dark:text-zinc-400">
                  Las prácticas sostenibles y responsabilidad social se vuelven cada vez
                  más importantes para los empleadores.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}