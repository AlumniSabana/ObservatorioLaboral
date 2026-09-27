'use client';

/**
 * Ruta '/sobre': envuelve <SobreObservatorio /> en el layout estándar.
 * El contenido vive en src/lib/sobre-observatorio.tsx porque también se
 * muestra al pie de Informes.
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
