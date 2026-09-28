'use client';

/**
 * <VistaUsuario /> — la página de Informes para un visitante SIN sesión.
 *
 * Es un CATÁLOGO DE SOLO LECTURA de los informes que el Administrador ya
 * validó (decisión del usuario, 2026-09-27: el Usuario ya no puede subir
 * nada — ni el frontend lo ofrece ni el backend lo permite, `/informes/extraer`
 * y `POST /informes` ahora exigen `requiere_admin`). Antes esta vista dejaba
 * subir un PDF y mostraba "mis informes" (los de ese navegador, vía
 * localStorage); ese flujo entero se quitó.
 *
 * Interacción tipo catálogo → detalle:
 *   - Catálogo: una tarjeta por informe validado (título, editor, año, nº de
 *     skills). Clic → abre su detalle.
 *   - Detalle de un informe:
 *       1. ANÁLISIS   (GET /informes/{id}/detalle)
 *       2. INSIGHTS   individuales que el Admin generó sobre él (solo lectura,
 *          GET /informes/insights-generados?informe_id=…&tipo=individual)
 *       3. INFORMES RELACIONADOS, debajo de los dos anteriores (GET
 *          /informes/{id}/similares, por solapamiento de skills, sin IA).
 *          Clic en uno de ellos NAVEGA el detalle a ese otro informe (mismo
 *          patrón catálogo→detalle, no una nueva pestaña).
 *       4. Un botón "Ver insights en conjunto" que trae —bajo demanda, no de
 *          entrada— los insights CONJUNTOS ya generados que incluyen a este
 *          informe (mismo endpoint de arriba, tipo=conjunto): la síntesis del
 *          Admin sobre este informe Y sus relacionados. Antes esto vivía en
 *          una sección aparte al fondo de la página con TODOS los conjuntos
 *          del Observatorio; se reemplaza por este botón contextual porque el
 *          usuario lo pidió puntual a lo que se está viendo.
 *
 * No hay validar / retirar / eliminar / generar / subir aquí: esas acciones
 * son del Admin (vista-admin.tsx) y el backend las protege con `requiere_admin`.
 */

import { useEffect, useState } from 'react';
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  FileText,
  Layers,
  Link2,
  Sparkles,
} from 'lucide-react';
import { AssistantContent } from '@/lib/markdown';
import { Spinner } from '@/lib/spinner';
import type {
  Detalle,
  InformeGuardado,
  InsightGenerado,
  InsightsGeneradosResp,
  SimilaresResp,
} from './comun';
import { BACKEND_URL, etiquetaInforme } from './comun';
import { GraficasInforme } from './graficas-informe';

// ── Piezas compartidas ───────────────────────────────────────────────────────

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
            {basadoEn && `Basado en: ${basadoEn}`}
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

/** Lista de insights, con los tres estados (cargando / no habilitado / vacío). */
function ListaInsights({ resp, vacio }: { resp: InsightsGeneradosResp | null; vacio: string }) {
  if (resp === null) return <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>;
  if (!resp.disponible) {
    return (
      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
        Los insights aún no están habilitados en esta instalación (pendiente de aplicar la migración 012).
      </p>
    );
  }
  if (resp.insights.length === 0) {
    return <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>{vacio}</p>;
  }
  return <div className="space-y-2">{resp.insights.map((ins) => <TarjetaInsight key={ins.id} insight={ins} />)}</div>;
}

// ── Tarjeta del catálogo ─────────────────────────────────────────────────────

function TarjetaCatalogo({ informe, onAbrir }: { informe: InformeGuardado; onAbrir: () => void }) {
  return (
    <button
      onClick={onAbrir}
      className="text-left rounded-lg border p-4 h-full flex flex-col gap-2 transition-shadow hover:shadow-md"
      style={{ borderColor: 'var(--sabana-sky-blue)', cursor: 'pointer' }}
    >
      <FileText size={20} style={{ color: 'var(--sabana-navy)' }} />
      <p className="text-sm font-semibold flex-1" style={{ color: 'var(--sabana-dark-navy)' }}>
        {informe.editor} — {informe.titulo}
      </p>
      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
        {informe.anio_referencia} · {informe.n_observaciones} skills detectadas
      </p>
    </button>
  );
}

// ── Detalle de un informe ────────────────────────────────────────────────────

function DetalleInforme({
  informe,
  onVolver,
  onIrA,
}: {
  informe: InformeGuardado;
  onVolver: () => void;
  /** Ir al detalle de OTRO informe (clic en un relacionado): mismo patrón catálogo→detalle. */
  onIrA: (id: string) => void;
}) {
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [insights, setInsights] = useState<InsightsGeneradosResp | null>(null);
  const [similares, setSimilares] = useState<SimilaresResp | null>(null);
  const [conjuntos, setConjuntos] = useState<InsightsGeneradosResp | null>(null);
  const [conjuntosAbierto, setConjuntosAbierto] = useState(false);

  // Se piden los tres bloques de arriba al ENTRAR a este informe (y de nuevo
  // si se navega a otro vía "relacionados"); los conjuntos son bajo demanda
  // (botón), no se piden aquí.
  useEffect(() => {
    let vivo = true;
    setDetalle(null);
    setInsights(null);
    setSimilares(null);
    setConjuntos(null);
    setConjuntosAbierto(false);

    const idUrl = encodeURIComponent(informe.id);
    fetch(`${BACKEND_URL}/informes/${idUrl}/detalle`).then((r) => (r.ok ? r.json() : null)).catch(() => null)
      .then((d) => vivo && setDetalle(d));
    fetch(`${BACKEND_URL}/informes/insights-generados?informe_id=${idUrl}&tipo=individual`).then((r) => (r.ok ? r.json() : null)).catch(() => null)
      .then((d) => vivo && setInsights(d));
    fetch(`${BACKEND_URL}/informes/${idUrl}/similares`).then((r) => (r.ok ? r.json() : null)).catch(() => null)
      .then((d) => vivo && setSimilares(d));

    return () => { vivo = false; };
  }, [informe.id]);

  const verConjuntos = async () => {
    setConjuntosAbierto((v) => !v);
    if (conjuntos !== null) return; // ya se pidió para este informe
    const idUrl = encodeURIComponent(informe.id);
    const d = await fetch(`${BACKEND_URL}/informes/insights-generados?informe_id=${idUrl}&tipo=conjunto`)
      .then((r) => (r.ok ? r.json() : null)).catch(() => null);
    setConjuntos(d);
  };

  return (
    <div className="space-y-6">
      <button onClick={onVolver}
        className="flex items-center gap-1.5 text-sm font-semibold"
        style={{ color: 'var(--sabana-navy)', cursor: 'pointer' }}>
        <ArrowLeft size={16} /> Volver al catálogo
      </button>

      <div>
        <h3 className="text-xl font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
          {etiquetaInforme(informe)}
        </h3>
        <p className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>
          {informe.n_observaciones} skills detectadas
        </p>
      </div>

      {/* 1. Análisis propio del informe */}
      <div>
        <Subtitulo icono={FileText}>Análisis del informe</Subtitulo>
        <GraficasInforme detalle={detalle} />
      </div>

      {/* 2. Insights individuales generados por el Admin */}
      <div>
        <Subtitulo icono={Sparkles}>Insights del Administrador sobre este informe</Subtitulo>
        <ListaInsights resp={insights} vacio="El Administrador aún no ha generado insights para este informe." />
      </div>

      {/* 3. Informes relacionados (debajo de los dos anteriores) + botón de
          insights conjuntos de este informe y sus relacionados. */}
      <div>
        <Subtitulo icono={Link2}>Informes relacionados</Subtitulo>
        {similares === null ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
        ) : similares.similares.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
            {similares.n_candidatos === 0
              ? 'Todavía no hay otros informes validados con los que comparar.'
              : 'Ningún otro informe validado comparte skills con este.'}
          </p>
        ) : (
          <div className="space-y-2">
            {similares.similares.map((s) => (
              <button
                key={s.id}
                onClick={() => onIrA(s.id)}
                className="w-full text-left rounded-lg border p-3 transition-shadow hover:shadow-sm"
                style={{ borderColor: 'var(--sabana-sky-blue)', cursor: 'pointer' }}
              >
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
              </button>
            ))}
            <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
              La afinidad es la proporción de skills que ambos informes tienen en común (Jaccard);
              se calcula sobre las skills ya extraídas, sin usar IA.
            </p>
          </div>
        )}

        {/* Insights conjuntos que incluyen a ESTE informe (con sus relacionados
            u otros grupos): bajo demanda, para no pedirlos si nadie los mira. */}
        <div className="mt-4">
          <button onClick={verConjuntos}
            className="flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-lg border"
            style={{ borderColor: 'var(--sabana-navy)', color: 'var(--sabana-navy)', cursor: 'pointer' }}>
            <Layers size={15} />
            Ver insights en conjunto {conjuntosAbierto ? '▲' : '▼'}
          </button>
          <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
            Síntesis que el Administrador generó comparando este informe con otros afines.
          </p>
          {conjuntosAbierto && (
            <div className="mt-3">
              <ListaInsights
                resp={conjuntos}
                vacio="El Administrador aún no ha generado un insight conjunto que incluya este informe."
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Vista ────────────────────────────────────────────────────────────────────

export function VistaUsuario() {
  // null = cargando; [] = catálogo vacío de verdad.
  const [catalogo, setCatalogo] = useState<InformeGuardado[] | null>(null);
  const [catalogoError, setCatalogoError] = useState(false);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);

  const cargarCatalogo = async () => {
    try {
      // Solo VALIDADOS: es el catálogo público del Observatorio, lo que el
      // Administrador ya revisó y aprobó como fuente. Un borrador (recién
      // subido, sin revisar) o un retirado no se muestran aquí.
      const r = await fetch(`${BACKEND_URL}/informes?estado=validado`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setCatalogo(d.informes ?? []);
      setCatalogoError(false);
    } catch {
      setCatalogo([]);
      setCatalogoError(true);
    }
  };

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargarCatalogo();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const informeSeleccionado = catalogo?.find((i) => i.id === seleccionado) ?? null;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
          Catálogo de informes de mercado laboral que el Administrador ha validado (por ejemplo,
          un <i>Job Skills Report</i>). Abre uno para ver su análisis, los insights que el
          Administrador generó sobre él y qué otros informes se le parecen.
        </p>
        <p className="text-sm mt-1" style={{ color: 'var(--sabana-black-50)' }}>
          Las cifras de un informe son <b>declaradas por su editor</b>, no medidas por el
          Observatorio.
        </p>
      </div>

      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        {informeSeleccionado ? (
          <DetalleInforme
            informe={informeSeleccionado}
            onVolver={() => setSeleccionado(null)}
            onIrA={setSeleccionado}
          />
        ) : (
          <>
            <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              Informes del Observatorio
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
              Solo se listan los informes ya validados por el Administrador.
            </p>

            {catalogo === null ? (
              <Spinner compact label="Cargando catálogo…" />
            ) : catalogoError ? (
              <div className="text-sm text-center py-6" style={{ color: 'var(--sabana-black-50)' }}>
                <p className="mb-2">No se pudo cargar el catálogo (¿el backend está caído?).</p>
                <button onClick={cargarCatalogo} className="text-xs font-semibold underline"
                  style={{ color: 'var(--sabana-navy)', cursor: 'pointer' }}>
                  Reintentar
                </button>
              </div>
            ) : catalogo.length === 0 ? (
              <p className="text-sm text-center py-6" style={{ color: 'var(--sabana-black-50)' }}>
                Todavía no hay informes validados en el Observatorio.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {catalogo.map((inf) => (
                  <TarjetaCatalogo key={inf.id} informe={inf} onAbrir={() => setSeleccionado(inf.id)} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
