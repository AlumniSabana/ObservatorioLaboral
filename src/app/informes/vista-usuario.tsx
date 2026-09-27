'use client';

/**
 * <VistaUsuario /> — la página de Informes para un visitante SIN sesión.
 *
 * Solo lectura salvo subir PDFs. Muestra:
 *   1. SUS informes: los que se registraron desde ESTE navegador (ids en
 *      localStorage, ver comun.ts). No hay login de Usuario, así que no existe
 *      otra forma de saber "cuáles son míos". Puede subir nuevos con el mismo
 *      flujo del Admin (extraer -> revisar -> guardar) y los ve en estado
 *      "pendiente de validación por el Administrador" hasta que uno los valide.
 *   2. Por cada informe suyo: su ANÁLISIS (GET /informes/{id}/detalle), los
 *      INSIGHTS INDIVIDUALES que el Admin ya generó sobre él (solo lectura,
 *      GET /informes/insights-generados?informe_id=…&tipo=individual) y los
 *      REPORTES SIMILARES (GET /informes/{id}/similares, por solapamiento de
 *      skills, sin IA: se consulta cada vez y debe ser barato).
 *   3. Los INSIGHTS CONJUNTOS ya generados por el Admin (solo lectura).
 *
 * Aquí NO hay validar / retirar / eliminar / generar: esas acciones son del
 * Admin (vista-admin.tsx) y el backend las protege con `requiere_admin`.
 */

import { useEffect, useState } from 'react';
import { FileText, Clock, Layers, Link2, ChevronDown, ChevronUp, X, Info } from 'lucide-react';
import { AssistantContent } from '@/lib/markdown';
import { Spinner } from '@/lib/spinner';
import type {
  Detalle,
  InformeGuardado,
  InsightGenerado,
  InsightsGeneradosResp,
  SimilaresResp,
} from './comun';
import {
  BACKEND_URL,
  ETIQUETA_ESTADO,
  etiquetaInforme,
  formatearFecha,
  leerMisInformes,
  olvidarMiInforme,
  recordarMiInforme,
} from './comun';
import { SubirInforme } from './subir-informe';
import { GraficasInforme } from './graficas-informe';

// ── Piezas ─────────────────────────────────────────────────────────────────

/** Un insight guardado, plegado por defecto (pueden ser largos). */
function TarjetaInsight({ insight }: { insight: InsightGenerado }) {
  const [abierto, setAbierto] = useState(false);
  const basadoEn = (insight.informes ?? []).map(etiquetaInforme).join(' · ');
  return (
    <div className="rounded-lg border" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
      <button onClick={() => setAbierto((v) => !v)}
        className="w-full flex items-center justify-between gap-2 p-3 text-left" style={{ cursor: 'pointer' }}>
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>{insight.titulo}</p>
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
            {formatearFecha(insight.creado_en)}
            {basadoEn && ` · Basado en: ${basadoEn}`}
            {insight.motivo_grupo && ` · ${insight.motivo_grupo}`}
          </p>
        </div>
        {abierto ? <ChevronUp size={16} style={{ color: 'var(--sabana-navy)' }} /> : <ChevronDown size={16} style={{ color: 'var(--sabana-navy)' }} />}
      </button>
      {abierto && <div className="px-3 pb-3"><AssistantContent content={insight.contenido} /></div>}
    </div>
  );
}

function Subtitulo({ icono: Icono, children }: { icono: React.ElementType; children: React.ReactNode }) {
  return (
    <h4 className="text-sm font-bold flex items-center gap-2 mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
      <Icono size={15} /> {children}
    </h4>
  );
}

/**
 * Un informe del Usuario con sus tres bloques (análisis, insights, similares).
 * Los tres se piden juntos al desplegar la tarjeta, no al listar: un Usuario
 * con varios PDFs no debería disparar 3×N fetches al entrar a la página.
 */
function TarjetaMiInforme({
  id,
  informe,
  onOlvidar,
}: {
  id: string;
  informe: InformeGuardado | null;   // null = ya no está en el catálogo
  onOlvidar: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [insights, setInsights] = useState<InsightsGeneradosResp | null>(null);
  const [similares, setSimilares] = useState<SimilaresResp | null>(null);
  const [cargado, setCargado] = useState(false);

  const desplegar = async () => {
    setAbierto((v) => !v);
    if (cargado || !informe) return;
    setCargado(true);
    const idUrl = encodeURIComponent(id);
    const [d, i, s] = await Promise.all([
      fetch(`${BACKEND_URL}/informes/${idUrl}/detalle`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      fetch(`${BACKEND_URL}/informes/insights-generados?informe_id=${idUrl}&tipo=individual`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      fetch(`${BACKEND_URL}/informes/${idUrl}/similares`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ]);
    setDetalle(d);
    setInsights(i);
    setSimilares(s);
  };

  if (!informe) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
        <FileText size={18} style={{ color: 'var(--sabana-black-30)' }} />
        <p className="flex-1 min-w-[14rem] text-sm" style={{ color: 'var(--sabana-black-50)' }}>
          Este informe ya no está en el catálogo (id <code className="text-xs">{id}</code>); el
          Administrador pudo eliminarlo.
        </p>
        <button onClick={onOlvidar}
          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
          style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
          <X size={12} /> Quitar de mi lista
        </button>
      </div>
    );
  }

  const pendiente = informe.estado === 'borrador';

  return (
    <div className="rounded-lg border" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
      <div className="flex flex-wrap items-center gap-3 p-3">
        <FileText size={18} style={{ color: 'var(--sabana-navy)' }} />
        <div className="flex-1 min-w-[14rem]">
          <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>{etiquetaInforme(informe)}</p>
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>{informe.n_observaciones} skills detectadas</p>
        </div>
        <span className="flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded"
          style={{
            backgroundColor: informe.estado === 'validado' ? 'var(--trend-up)' : 'var(--sabana-cream)',
            color: informe.estado === 'validado' ? 'white' : 'var(--sabana-dark-navy)',
          }}>
          {pendiente && <Clock size={12} />}
          {ETIQUETA_ESTADO[informe.estado] ?? informe.estado}
        </span>
        <button onClick={desplegar}
          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
          style={{ borderColor: 'var(--sabana-navy)', color: 'var(--sabana-navy)', cursor: 'pointer' }}>
          {abierto ? <ChevronUp size={13} /> : <ChevronDown size={13} />} {abierto ? 'Ocultar' : 'Ver análisis'}
        </button>
      </div>

      {abierto && (
        <div className="border-t p-4 space-y-6" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
          {pendiente && (
            <div className="flex items-start gap-2 rounded-lg p-3 text-xs"
              style={{ background: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}>
              <Info size={14} className="mt-0.5 shrink-0" />
              <p>
                Este informe está pendiente de validación. Cuando el Administrador lo valide pasará a ser
                una fuente del Observatorio y podrá generar insights sobre él.
              </p>
            </div>
          )}

          {/* 1. Análisis propio del informe */}
          <div>
            <Subtitulo icono={FileText}>Análisis del informe</Subtitulo>
            <GraficasInforme detalle={detalle} />
          </div>

          {/* 2. Insights individuales generados por el Admin */}
          <div>
            <Subtitulo icono={Clock}>Insights del Administrador sobre este informe</Subtitulo>
            {insights === null ? (
              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
            ) : !insights.disponible ? (
              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                Los insights aún no están habilitados en esta instalación (pendiente de aplicar la migración 012).
              </p>
            ) : insights.insights.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                El Administrador aún no ha generado insights para este informe.
              </p>
            ) : (
              <div className="space-y-2">
                {insights.insights.map((ins) => <TarjetaInsight key={ins.id} insight={ins} />)}
              </div>
            )}
          </div>

          {/* 3. Reportes similares (solapamiento de skills, sin IA) */}
          <div>
            <Subtitulo icono={Link2}>Reportes similares</Subtitulo>
            {similares === null ? (
              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
            ) : similares.similares.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                {similares.n_candidatos === 0
                  ? 'Todavía no hay otros informes validados con los que comparar.'
                  : 'Ningún informe validado comparte skills con este.'}
              </p>
            ) : (
              <div className="space-y-2">
                {similares.similares.map((s) => (
                  <div key={s.id} className="rounded-lg border p-3" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="flex-1 min-w-[12rem] text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
                        {etiquetaInforme(s)}
                      </p>
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}>
                        {s.n_compartidas} skills en común · afinidad {Math.round(s.afinidad * 100)} %
                      </span>
                    </div>
                    {s.compartidas.length > 0 && (
                      <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
                        Comparten: {s.compartidas.join(', ')}
                      </p>
                    )}
                  </div>
                ))}
                <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                  La afinidad es la proporción de skills que ambos informes tienen en común (Jaccard);
                  se calcula sobre las skills ya extraídas, sin usar IA.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Vista ──────────────────────────────────────────────────────────────────

export function VistaUsuario() {
  const [misIds, setMisIds] = useState<string[]>([]);
  // null = cargando; [] = catálogo vacío de verdad.
  const [catalogo, setCatalogo] = useState<InformeGuardado[] | null>(null);
  const [catalogoError, setCatalogoError] = useState(false);
  const [conjuntos, setConjuntos] = useState<InsightsGeneradosResp | null>(null);

  const cargarCatalogo = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/informes`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setCatalogo(d.informes ?? []);
      setCatalogoError(false);
    } catch {
      setCatalogo([]);
      setCatalogoError(true);
    }
  };

  const cargarConjuntos = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/informes/insights-generados?tipo=conjunto`);
      setConjuntos(r.ok ? await r.json() : null);
    } catch {
      setConjuntos(null);
    }
  };

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setMisIds(leerMisInformes());
    cargarCatalogo();
    cargarConjuntos();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const olvidar = (id: string) => {
    olvidarMiInforme(id);
    setMisIds(leerMisInformes());
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
          Sube un informe de mercado laboral en PDF (por ejemplo, un <i>Job Skills Report</i>) y
          consulta su análisis, los insights que el Administrador genere sobre él y qué otros
          informes del Observatorio se le parecen.
        </p>
        <p className="text-sm mt-1" style={{ color: 'var(--sabana-black-50)' }}>
          Un informe pasa a ser fuente del Observatorio solo cuando el Administrador lo valida. Las
          cifras de un informe son <b>declaradas por su editor</b>, no medidas por el Observatorio.
        </p>
      </div>

      {/* Subir + revisar (mismo flujo que el Admin; queda en borrador) */}
      <SubirInforme
        modo="usuario"
        numerar={false}
        onGuardado={async (r) => {
          recordarMiInforme(r.id);
          setMisIds(leerMisInformes());
          await cargarCatalogo();
        }}
        onDuplicado={cargarCatalogo}
      />

      {/* Mis informes */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
          Mis informes
        </h3>
        <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
          Los informes que has subido desde este navegador. Si cambias de equipo o borras los datos
          del sitio, dejarán de aparecer aquí (siguen en el catálogo del Observatorio).
        </p>

        {catalogo === null ? (
          <Spinner compact label="Cargando tus informes…" />
        ) : misIds.length === 0 ? (
          <div className="text-sm text-center py-6 space-y-1" style={{ color: 'var(--sabana-black-50)' }}>
            <p>Todavía no has subido ningún informe desde este navegador.</p>
            <p>
              Pulsa <b>Seleccionar PDF</b> arriba, revisa las skills detectadas y guárdalo: aparecerá aquí
              como pendiente de validación.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {catalogoError && (
              <div className="text-xs rounded-lg p-2 bg-red-50 text-red-700">
                No se pudo cargar el catálogo (¿el backend está caído?). Tus informes siguen guardados;{' '}
                <button onClick={cargarCatalogo} className="underline font-semibold" style={{ cursor: 'pointer' }}>reintentar</button>.
              </div>
            )}
            {misIds.map((id) => (
              <TarjetaMiInforme
                key={id}
                id={id}
                informe={catalogoError ? null : (catalogo.find((i) => i.id === id) ?? null)}
                onOlvidar={() => olvidar(id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Insights conjuntos ya generados (solo lectura) */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-lg font-semibold mb-1 flex items-center gap-2" style={{ color: 'var(--sabana-dark-navy)' }}>
          <Layers size={18} /> Insights conjuntos del Observatorio
        </h3>
        <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
          Síntesis que el Administrador ha generado sobre grupos de informes afines (por ejemplo, varios
          reportes sobre IA y empleo). Se leen aquí, no se generan.
        </p>
        {conjuntos === null ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
        ) : !conjuntos.disponible ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
            Los insights conjuntos aún no están habilitados en esta instalación (pendiente de aplicar la migración 012).
          </p>
        ) : conjuntos.insights.length === 0 ? (
          <p className="text-sm text-center py-4" style={{ color: 'var(--sabana-black-50)' }}>
            El Administrador aún no ha generado insights conjuntos.
          </p>
        ) : (
          <div className="space-y-2">
            {conjuntos.insights.map((ins) => <TarjetaInsight key={ins.id} insight={ins} />)}
          </div>
        )}
      </div>
    </div>
  );
}
