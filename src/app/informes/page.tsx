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
 *   - Admin   -> vista-admin.tsx   : sube PDFs, valida / retira / elimina,
 *                informe de insights e Insights Conjuntos (Gemini).
 *   - Usuario -> vista-usuario.tsx : SOLO LECTURA. Catálogo de los informes
 *                YA VALIDADOS por el Admin; al abrir uno ve su análisis, los
 *                insights que el Admin generó, informes relacionados y (bajo
 *                demanda) los insights conjuntos que lo incluyen. No puede
 *                subir nada (decisión del usuario, 2026-09-27: antes cualquier
 *                visitante podía aportar un PDF; ahora `/informes/extraer` y
 *                `POST /informes` exigen sesión de Admin en el backend).
 * Lo compartido (subir/revisar, gráficas, tipos) vive en los demás archivos de
 * esta carpeta. Mientras useAuth aún no leyó localStorage se muestra un
 * spinner, para no pintar la vista de Usuario y luego saltar a la de Admin.
 *
 * "Sobre el observatorio" tiene su propio enlace en el menú (ruta /sobre,
 * decisión del usuario 2026-09-28): antes se montaba al pie de esta página,
 * pero es contenido informativo ajeno al flujo de informes, así que se sacó.
 */

import { PageLayout } from '@/lib/sidebar';
import { Spinner } from '@/lib/spinner';
import { useAuth } from '@/lib/auth';
import { VistaAdmin } from './vista-admin';
import { VistaUsuario } from './vista-usuario';

export default function InformesPage() {
  const { esAdmin, cargando } = useAuth();

  return (
    <PageLayout title="Informes">
      {cargando ? <Spinner label="Cargando…" /> : esAdmin ? <VistaAdmin /> : <VistaUsuario />}
    </PageLayout>
  );
}
