'use client';

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';

export default function ConditionsPage() {
  return (
    <>
      <PageLayout title="Condiciones laborales actuales">
      <div className="space-y-6">
        <p className="text-lg text-zinc-600 dark:text-zinc-400" style={{color: 'var(--sabana-dark-navy)'}}>
          Analiza las condiciones laborales actuales, beneficios y modalidades de trabajo en el mercado.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              📍 Modalidades de trabajo
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• <strong>Presencial:</strong> Trabajo en oficina tradicional</li>
              <li>• <strong>Remoto:</strong> Trabajo desde casa o cualquier ubicación</li>
              <li>• <strong>Híbrido:</strong> Combinación de presencial y remoto</li>
              <li>• <strong>Flexible:</strong> Horarios y locaciones adaptables</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              🎁 Beneficios y prestaciones
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Seguro de salud completo</li>
              <li>• Bonificación anual</li>
              <li>• Planes de pensión</li>
              <li>• Beneficios adicionales (transporte, comida)</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              ⏰ Horarios de trabajo
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Jornada de 40 horas semanales</li>
              <li>• Horarios flexibles</li>
              <li>• Tiempo flexible (flexitime)</li>
              <li>• Opciones de medio tiempo</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              📚 Desarrollo profesional
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Programas de capacitación</li>
              <li>• Becas para educación continua</li>
              <li>• Mentoría profesional</li>
              <li>• Planes de carrera</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              👥 Cultura empresarial
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Ambiente colaborativo</li>
              <li>• Programas de bienestar</li>
              <li>• Inclusión y diversidad</li>
              <li>• Eventos y actividades de equipo</li>
            </ul>
          </div>

          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4" style={{borderColor: 'var(--sabana-light-blue)'}}>
            <h3 className="text-lg font-semibold mb-3" style={{color: 'var(--sabana-light-blue)'}}>
              ⚖️ Estabilidad laboral
            </h3>
            <ul className="text-zinc-600 dark:text-zinc-400 space-y-2 text-sm">
              <li>• Contratos indefinidos</li>
              <li>• Seguridad en el empleo</li>
              <li>• Protección legal</li>
              <li>• Beneficios de jubilación</li>
            </ul>
          </div>
        </div>
      </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Condiciones Laborales Actuales"
        pageContent="Página sobre condiciones laborales actuales incluyendo: Modalidades de Trabajo (Presencial, Remoto, Híbrido), Beneficios y Prestaciones, Horarios de Trabajo, Desarrollo Profesional, Cultura Empresarial y Estabilidad Laboral."
      />
    </>
  );
}