'use client';

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function SkillsPage() {
  return (
    <>
      <PageLayout title="Competencias y Habilidades Apetecidas">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Descubre las competencias más apetecidas por los empleadores en el mercado laboral actual.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              💻 Competencias Técnicas
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2">
              <li>• Programación (Python, JavaScript, Java)</li>
              <li>• Cloud Computing (AWS, Azure, GCP)</li>
              <li>• Análisis de Datos</li>
              <li>• DevOps y CI/CD</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🤝 Competencias Blandas
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2">
              <li>• Liderazgo y gestión de equipos</li>
              <li>• Comunicación efectiva</li>
              <li>• Resolución de problemas</li>
              <li>• Trabajo en equipo</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🎯 Habilidades Emergentes
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2">
              <li>• Inteligencia Artificial</li>
              <li>• Ciberseguridad</li>
              <li>• Blockchain</li>
              <li>• Automatización robótica</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              📊 Competencias en Datos
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2">
              <li>• Business Intelligence</li>
              <li>• Machine Learning</li>
              <li>• Visualización de datos</li>
              <li>• Análisis predictivo</li>
            </ul>
          </div>
        </div>
      </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Competencias y Habilidades Apetecidas"
        pageContent="Página sobre competencias más apetecidas por empleadores. Incluye: Competencias Técnicas (Programación, Cloud Computing, Análisis de Datos, DevOps), Competencias Blandas (Liderazgo, Comunicación, Resolución de problemas), Habilidades Emergentes (IA, Ciberseguridad, Blockchain) y Competencias en Datos (Business Intelligence, Machine Learning)."
      />
    </>
  );
}