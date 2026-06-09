'use client';

/**
 * Página "Tendencias en formación" (ruta '/trends').
 *
 * ⚠️ Contenido ESTÁTICO de ejemplo: las tarjetas están escritas a mano y NO
 * consumen el backend. Es una página informativa/placeholder. Si en el futuro
 * se quiere mostrar datos reales, este es uno de los lugares a conectar con la
 * API (ver cómo lo hace src/app/analytics/page.tsx).
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function TrendsPage() {
  return (
    <>
      <PageLayout title="Tendencias en formación">
      <div className="space-y-6" >
        <p className="text-lg text-zinc-600 dark:text-zinc-400" style={{color: 'var(--sabana-dark-navy)'}}>
          Explora las tendencias actuales en los modelos de formación y educación continua demandadas por el mercado laboral.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              📚 Formación digital
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              La demanda de competencias digitales continúa creciendo exponencialmente en todos los sectores.
            </p>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🎓 Educación continua
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              El aprendizaje permanente se ha convertido en una necesidad para mantenerse competitivo.
            </p>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🤖 Inteligencia artificial
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400">
              Las habilidades en IA y machine learning se posicionan como prioritarias para el futuro.
            </p>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              💡 Soft skills
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
