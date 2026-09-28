'use client';

/**
 * Ruta '/sobre': envuelve <SobreObservatorio /> en el layout estándar.
 *
 * Es su propio enlace en el menú lateral (decisión del usuario, 2026-09-28):
 * antes vivía al pie de Informes, pero mezclaba una sección informativa
 * (visible para ambos roles) con el flujo de curación de PDFs. El contenido
 * en sí no cambió: sigue en src/lib/sobre-observatorio.tsx, sin llamadas al
 * backend y visible tanto con sesión de Admin como sin ella.
 */

import { PageLayout } from '@/lib/sidebar';
import { SobreObservatorio } from '@/lib/sobre-observatorio';

export default function SobrePage() {
  return (
    <PageLayout title="Sobre el Observatorio">
      <SobreObservatorio />
    </PageLayout>
  );
}
