'use client';

import { Sidebar } from '@/lib/sidebar';

export default function DemandPage() {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            Mayor Demanda Actual
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>

          <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
            Los roles con mayor demanda en el mercado laboral actual.
          </p>

          <div className="space-y-4">
            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-semibold text-black dark:text-white">Software Engineers</h3>
                <span className="text-2xl font-bold text-blue-600">🔥</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div className="bg-blue-600 h-2 rounded-full" style={{width: '95%'}}></div>
              </div>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">Demanda muy alta</p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-semibold text-black dark:text-white">Data Scientists</h3>
                <span className="text-2xl font-bold text-blue-600">🔥</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div className="bg-blue-600 h-2 rounded-full" style={{width: '90%'}}></div>
              </div>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">Demanda muy alta</p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-semibold text-black dark:text-white">Product Managers</h3>
                <span className="text-2xl font-bold text-orange-600">⚡</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div className="bg-orange-600 h-2 rounded-full" style={{width: '75%'}}></div>
              </div>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">Demanda alta</p>
            </div>

            <div className="bg-white dark:bg-zinc-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-semibold text-black dark:text-white">DevOps Engineers</h3>
                <span className="text-2xl font-bold text-orange-600">⚡</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div className="bg-orange-600 h-2 rounded-full" style={{width: '80%'}}></div>
              </div>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">Demanda alta</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}