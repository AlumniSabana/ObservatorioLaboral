'use client';

/**
 * Página "Sectores y empresas" (ruta '/sectors').
 *
 * ⚠️ Contenido ESTÁTICO de ejemplo (sectores económicos escritos a mano). NO
 * consume el backend; es informativa/placeholder. El dashboard de /analytics sí
 * muestra sectores y empresas reales a partir de las vacantes recolectadas.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function SectorsPage() {
  return (
    <>
      <PageLayout title="Sectores y empresas">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400" style={{color: 'var(--sabana-dark-navy)'}}>
          Conoce los principales sectores económicos y empresas empleadoras del mercado laboral.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🏭 Sector manufacturero
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">
              Producción industrial y manufactura de bienes.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Automotriz</li>
              <li>• Alimentos y bebidas</li>
              <li>• Textil y confecciones</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              💻 Sector tecnológico
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">
              Tecnología, software y servicios digitales.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Desarrollo de software</li>
              <li>• Telecomunicaciones</li>
              <li>• Infraestructura IT</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🏦 Sector financiero
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">
              Banca, seguros y servicios financieros.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Banca comercial</li>
              <li>• Seguros</li>
              <li>• Fintech</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🏥 Sector salud
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">
              Salud, farmacéutica y servicios médicos.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Hospitales y clínicas</li>
              <li>• Farmacéutica</li>
              <li>• Seguros de salud</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🎓 Sector educación
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">
              Educación e instituciones académicas.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Universidades</li>
              <li>• Institutos de formación</li>
              <li>• Plataformas e-learning</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              ⚡ Otros sectores
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">
              Energía, infraestructura y servicios.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Energía renovable</li>
              <li>• Infraestructura</li>
              <li>• Consultoría</li>
            </ul>
          </div>
        </div>
      </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Sectores y Empresas"
        pageContent="Página sobre principales sectores económicos incluyendo: Sector Manufacturero (Automotriz, Alimentos, Textil), Sector Tecnológico (Software, Telecomunicaciones), Sector Financiero (Banca, Seguros, Fintech), Sector Salud (Hospitales, Farmacéutica), Sector Educación (Universidades, E-learning) y otros sectores como Energía y Consultoría."
      />
    </>
  );
}