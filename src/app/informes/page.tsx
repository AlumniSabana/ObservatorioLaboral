'use client';

/**
 * Página "Informes" (ruta '/informes').
 *
 * Permite subir un informe PDF de un tercero (ej. "Coursera Job Skills Report
 * 2024") y convertirlo en una FUENTE de skills del Observatorio, en tres pasos
 * deliberados: subir -> revisar -> validar. Ese paso humano es intencional: un
 * informe mal leído contaminaría el dashboard.
 *
 * La página es solo el CONMUTADOR POR ROL (useAuth, contrato de src/lib/auth):
 *   - Admin   -> vista-admin.tsx   : catálogo completo, validar / retirar /
 *                eliminar, informe de insights e Insights Conjuntos (Gemini).
 *   - Usuario -> vista-usuario.tsx : sube PDFs, ve SUS informes (los de este
 *                navegador), su análisis, los insights que el Admin generó y
 *                reportes similares. Solo lectura.
 * Lo compartido (subir/revisar, gráficas, tipos) vive en los demás archivos de
 * esta carpeta. Mientras useAuth aún no leyó localStorage se muestra un
 * spinner, para no pintar la vista de Usuario y luego saltar a la de Admin.
 *
 * Al pie va siempre "Sobre el observatorio", en ambas vistas.
 */

import { PageLayout } from '@/lib/sidebar';
import { Spinner } from '@/lib/spinner';
import { SobreObservatorio } from '@/lib/sobre-observatorio';
import { useAuth } from '@/lib/auth';
import { VistaAdmin } from './vista-admin';
import { VistaUsuario } from './vista-usuario';

export default function InformesPage() {
  const { esAdmin, cargando } = useAuth();

  return (
    <PageLayout title="Informes">
      {cargando ? <Spinner label="Cargando…" /> : esAdmin ? <VistaAdmin /> : <VistaUsuario />}

      {/* ---------------- Sobre el observatorio ----------------
          Texto institucional al pie de Informes (antes tenía página propia).
          Lo estila el Equipo 1 dentro de su componente; esta página solo lo
          monta y debe seguir montándolo en la vista Admin y en la de Usuario. */}
      <section className="mt-12 pt-8 border-t" style={{ borderColor: 'var(--sabana-light-blue)' }}>
        <h2 className="text-2xl font-bold mb-6" style={{ color: 'var(--sabana-dark-navy)' }}>
          Sobre el observatorio
        </h2>
        <SobreObservatorio />
      </section>
    </PageLayout>
  );
}
