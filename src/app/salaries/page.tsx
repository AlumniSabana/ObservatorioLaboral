'use client';

import { PageLayout } from '@/lib/sidebar';

export default function SalariesPage() {
  return (
    <PageLayout title="Análisis Salarial">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Explora información sobre salarios en diferentes sectores, roles y niveles de experiencia.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              💰 Salarios por Sector
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 mb-3">
              Conoce los rangos salariales promedio en diferentes industrias.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Tecnología e Informática</li>
              <li>• Finanzas y Banca</li>
              <li>• Manufacturero</li>
              <li>• Servicios y Consultoría</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              📈 Salarios por Experiencia
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 mb-3">
              Descubre cómo evolucionan los salarios con la experiencia profesional.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Junior (0-2 años)</li>
              <li>• Mid-level (2-5 años)</li>
              <li>• Senior (5+ años)</li>
              <li>• Liderazgo</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🎓 Salarios por Rol
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 mb-3">
              Análisis salarial según el puesto de trabajo.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Desarrollador de Software</li>
              <li>• Analista de Datos</li>
              <li>• Gerente de Proyectos</li>
              <li>• Especialista en Ciberseguridad</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold text-black dark:text-white mb-3">
              🌍 Tendencias Salariales
            </h3>
            <p className="text-zinc-600 dark:text-zinc-400 mb-3">
              Observa las variaciones y tendencias en el mercado salarial.
            </p>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Crecimiento salarial anual</li>
              <li>• Comparativa regional</li>
              <li>• Beneficios adicionales</li>
              <li>• Proyecciones futuras</li>
            </ul>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
