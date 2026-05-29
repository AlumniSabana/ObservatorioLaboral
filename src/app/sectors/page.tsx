'use client';

import { Sidebar } from '@/lib/sidebar';

export default function SectorsPage() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Sectores y Empresas
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
            Explora los sectores más dinámicos y principales empresas empleadoras.
          </p>

          <div className="space-y-6">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-2xl font-semibold text-black dark:text-white mb-3">
                Sectores en Crecimiento
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-blue-100 dark:bg-blue-900 rounded">Tecnología</div>
                <div className="p-3 bg-green-100 dark:bg-green-900 rounded">Energías Renovables</div>
                <div className="p-3 bg-purple-100 dark:bg-purple-900 rounded">Salud Digital</div>
                <div className="p-3 bg-orange-100 dark:bg-orange-900 rounded">E-commerce</div>
              </div>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <h2 className="text-2xl font-semibold text-black dark:text-white mb-3">
                Principales Empleadores
              </h2>
              <ul className="space-y-2 text-zinc-600 dark:text-zinc-400">
                <li>✓ Amazon Web Services</li>
                <li>✓ Microsoft</li>
                <li>✓ Google</li>
                <li>✓ Meta</li>
                <li>✓ Apple</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}