'use client';

import { PageLayout } from '@/lib/sidebar';

export default function SectorsPage() {
  return (
    <PageLayout title="Sectores y Empresas">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Conoce los principales sectores económicos y empresas empleadoras del mercado laboral.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🏭 Sector Manufacturero
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

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              💻 Sector Tecnológico
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

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🏦 Sector Financiero
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

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🏥 Sector Salud
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

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🎓 Sector Educación
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

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              ⚡ Otros Sectores
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
  );
}
