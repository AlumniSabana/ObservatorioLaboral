'use client';

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function DemandPage() {
  return (
    <>
      <PageLayout title="Mayor Demanda Actual">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Descubre los roles y competencias con mayor demanda en el mercado laboral actual.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              👨‍💻 Roles en Tecnología
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Desarrollador Full Stack</li>
              <li>• Ingeniero de Datos</li>
              <li>• Especialista en Cloud</li>
              <li>• Ingeniero de Machine Learning</li>
              <li>• Especialista en Ciberseguridad</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              💼 Roles en Negocios
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Gerente de Proyectos</li>
              <li>• Analista de Negocios</li>
              <li>• Especialista en Marketing Digital</li>
              <li>• Consultor de Transformación Digital</li>
              <li>• Product Manager</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              📊 Roles en Datos y Análisis
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Científico de Datos</li>
              <li>• Analista de Business Intelligence</li>
              <li>• Especialista en Analytics</li>
              <li>• Ingeniero de Datos</li>
              <li>• Data Architect</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🔒 Roles en Seguridad
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Analista de Ciberseguridad</li>
              <li>• Ingeniero de Seguridad</li>
              <li>• Especialista en Compliance</li>
              <li>• Auditor de Seguridad IT</li>
              <li>• Especialista en Riesgos</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🌐 Tendencias de Demanda
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>↑ Roles remotos en aumento</li>
              <li>↑ Demanda de especialistas en IA</li>
              <li>↑ Profesionales con múltiples skills</li>
              <li>↑ Experiencia en transformación digital</li>
              <li>↑ Habilidades en sostenibilidad</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-dark-navy)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🎯 Competencias Prioritarias
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-1 text-sm">
              <li>• Adaptabilidad y flexibilidad</li>
              <li>• Habilidades digitales avanzadas</li>
              <li>• Pensamiento crítico</li>
              <li>• Inteligencia emocional</li>
              <li>• Capacidad de aprendizaje continuo</li>
            </ul>
          </div>
        </div>
      </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Mayor Demanda Actual"
        pageContent="Página sobre roles y competencias con mayor demanda incluyendo: Roles en Tecnología (Full Stack, Datos, Cloud, ML, Ciberseguridad), Roles en Negocios (PM, Analista, Marketing), Roles en Datos (Científico, BI, Analytics), Roles en Seguridad, Tendencias de Demanda (remotos, IA, transformación digital) y Competencias Prioritarias (adaptabilidad, habilidades digitales, pensamiento crítico)."
      />
    </>
  );
}