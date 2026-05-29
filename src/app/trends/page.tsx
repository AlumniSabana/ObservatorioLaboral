'use client';

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function TrendsPage() {
  return (
    <>
      <PageLayout title="Tendencias en Formación">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Explora las tendencias actuales en los modelos de formación y educación continua demandadas por el mercado laboral.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              📚 Formación Digital
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              La demanda de competencias digitales continúa creciendo exponencialmente en todos los sectores.
            </p>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🎓 Educación Continua
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              El aprendizaje permanente se ha convertido en una necesidad para mantenerse competitivo.
            </p>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🤖 Inteligencia Artificial
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              Las habilidades en IA y machine learning se posicionan como prioritarias para el futuro.
            </p>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              💡 Soft Skills
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              Las habilidades blandas como comunicación y liderazgo son cada vez más valoradas.
            </p>
          </div>
        </div>
      </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Tendencias en Formación"
        pageContent="Página sobre tendencias actuales en modelos de formación y educación continua. Contiene información sobre: Formación Digital, Educación Continua, Inteligencia Artificial y Soft Skills."
      />
    </>
  );
}
