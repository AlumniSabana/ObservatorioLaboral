'use client';

/**
 * <VistaAdmin /> — la página de Informes tal como la ve el ADMINISTRADOR.
 *
 * Flujo en tres pasos deliberados (subir -> revisar -> validar): nada aparece
 * como fuente seleccionable hasta que un humano lo valida. Aquí viven además la
 * curación del catálogo (validar / retirar / eliminar), el "Informe de
 * insights" (Gemini) sobre los validados marcados, los "Insights Conjuntos" y
 * la comparativa entre informes.
 *
 * Los botones de curación e insights van dentro de <SoloAdmin> y mandan
 * `authHeaders()`: ocultarlos es cortesía de interfaz, la seguridad la pone el
 * backend en cada endpoint protegido. Subir y revisar (SubirInforme) NO se
 * protege: cualquier visitante puede aportar un PDF (queda en borrador).
 */

import { useEffect, useState } from 'react';
import { FileText, Check, Trash2, AlertTriangle, BarChart3, Sparkles, Layers } from 'lucide-react';
import { AssistantContent } from '@/lib/markdown';
import { Spinner } from '@/lib/spinner';
import { SoloAdmin, authHeaders, useAuth } from '@/lib/auth';
import type { Comparativa, Detalle, InformeGuardado, InsightsResp } from './comun';
import { BACKEND_URL, errorDeRespuesta } from './comun';
import { SubirInforme } from './subir-informe';
import { GraficasInforme } from './graficas-informe';
import { InsightsConjuntos } from './insights-conjuntos';

export function VistaAdmin() {
  // `logout` se usa cuando un endpoint protegido responde 401: el token dejó de
  // valer (p. ej. el backend se reinició) y hay que dejar de creerse Admin.
  const { logout } = useAuth();
  const [informes, setInformes] = useState<InformeGuardado[]>([]);
  // Distingue "todavía no hay informes" (catálogo vacío de verdad) de "no se
  // pudo cargar el catálogo" (fetch falló): si la carga inicial fallaba, la
  // página parecía vacía para siempre aunque el catálogo sí tuviera informes.
  const [catalogoError, setCatalogoError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Informe cuyas gráficas propias se están viendo, y la comparativa entre todos.
  const [abierto, setAbierto] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [comparativa, setComparativa] = useState<Comparativa | null>(null);

  // Informe de insights (Gemini): selección de 1+ informes validados.
  const [seleccionados, setSeleccionados] = useState<string[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insights, setInsights] = useState<InsightsResp | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [conjuntosAbierto, setConjuntosAbierto] = useState(false);

  const cargarInformes = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/informes`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setInformes(d.informes ?? []);
      setCatalogoError(false);
    } catch {
      setCatalogoError(true);
    }
  };

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargarInformes();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  // Gráficas propias de un informe. Se piden al abrirlo (no al listar) para no
  // traer datos de todos los informes de golpe.
  const abrirGraficas = async (id: string) => {
    if (abierto === id) {
      setAbierto(null);
      return;
    }
    setAbierto(id);
    setDetalle(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/${encodeURIComponent(id)}/detalle`);
      setDetalle(r.ok ? await r.json() : null);
    } catch {
      setDetalle(null);
    }
  };

  // Comparativa entre informes: solo tiene sentido con dos o más validados.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (informes.filter((i) => i.estado === 'validado').length < 2) {
      setComparativa(null);
      return;
    }
    fetch(`${BACKEND_URL}/informes/comparativa`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setComparativa)
      .catch(() => setComparativa(null));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [informes]);

  const toggleSeleccion = (id: string) => {
    setSeleccionados((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  };

  // Informe de insights (Gemini) sobre los informes validados marcados. Lee los
  // datos YA extraídos y verificados (no vuelve a leer el PDF) y queda guardado
  // (tipo 'individual') para que el Usuario que subió el PDF pueda leerlo.
  const generarInsights = async () => {
    if (seleccionados.length === 0) return;
    setInsightsLoading(true);
    setInsightsError(null);
    setInsights(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/insights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ informe_ids: seleccionados }),
      });
      if (!r.ok) throw new Error(await errorDeRespuesta(r, logout));
      setInsights(await r.json());
    } catch (e) {
      setInsightsError(e instanceof Error ? e.message : 'No se pudo generar el informe de insights');
    } finally {
      setInsightsLoading(false);
    }
  };

  const accion = async (id: string, ruta: string, metodo = 'POST') => {
    setError(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/${encodeURIComponent(id)}${ruta}`, {
        method: metodo,
        headers: authHeaders(),
      });
      if (!r.ok) throw new Error(await errorDeRespuesta(r, logout));
      await cargarInformes();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La acción falló');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
          Sube informes de terceros (por ejemplo, un <i>Job Skills Report</i>) para usarlos como
          fuente de skills junto a las vacantes y O*NET.
        </p>
        <p className="text-sm mt-1" style={{ color: 'var(--sabana-black-50)' }}>
          Las cifras de un informe son <b>declaradas por su editor</b>, no medidas por el
          Observatorio: se muestran como contraste, nunca promediadas con las vacantes.
        </p>
      </div>

      {error && <div className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">{error}</div>}

      {/* ---------- Pasos 1 y 2: subir y revisar ---------- */}
      <SubirInforme modo="admin" onGuardado={cargarInformes} onDuplicado={cargarInformes} />

      {/* ---------- Paso 3: catálogo y validación ---------- */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
          3. Informes ingeridos
        </h3>
        <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
          Un informe solo aparece como fuente seleccionable cuando está <b>validado</b>. Un informe
          <b> retirado</b> se puede volver a subir: el mismo PDF lo reactiva.
        </p>

        {catalogoError ? (
          <div className="text-sm text-center py-6" style={{ color: 'var(--sabana-black-50)' }}>
            <p className="mb-2">No se pudo cargar el catálogo de informes (¿el backend está caído o se reinició?).</p>
            <button onClick={cargarInformes}
              className="text-xs font-semibold underline"
              style={{ color: 'var(--sabana-navy)', cursor: 'pointer' }}>
              Reintentar
            </button>
          </div>
        ) : informes.length === 0 ? (
          <p className="text-sm text-center py-6" style={{ color: 'var(--sabana-black-50)' }}>
            Todavía no hay informes. Sube un PDF para empezar.
          </p>
        ) : (
          <div className="space-y-2">
            {informes.map((inf) => (
              <div key={inf.id}>
                <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3"
                  style={{ borderColor: 'var(--sabana-sky-blue)' }}>
                  <FileText size={18} style={{ color: 'var(--sabana-navy)' }} />
                  <div className="flex-1 min-w-[14rem]">
                    <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {inf.editor} — {inf.titulo} ({inf.anio_referencia})
                    </p>
                    <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                      {inf.n_observaciones} skills · {inf.anio_referencia}
                    </p>
                  </div>
                  <span className="text-xs font-semibold px-2 py-1 rounded"
                    style={{
                      backgroundColor: inf.estado === 'validado' ? 'var(--trend-up)' : 'var(--sabana-cream)',
                      color: inf.estado === 'validado' ? 'white' : 'var(--sabana-dark-navy)',
                    }}>
                    {inf.estado}
                  </span>

                  <SoloAdmin>
                    {inf.estado === 'borrador' && (
                      <>
                        <button onClick={() => accion(inf.id, '/validar')}
                          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded text-white"
                          style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
                          <Check size={13} /> Validar
                        </button>
                        <button onClick={() => accion(inf.id, '', 'DELETE')}
                          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
                          style={{ borderColor: 'var(--trend-down)', color: 'var(--trend-down)', cursor: 'pointer' }}>
                          <Trash2 size={13} /> Eliminar
                        </button>
                      </>
                    )}
                    {inf.estado === 'validado' && (
                      <>
                        <label className="flex items-center gap-1.5 text-xs font-semibold px-2 cursor-pointer"
                          style={{ color: 'var(--sabana-dark-navy)' }}>
                          <input type="checkbox" checked={seleccionados.includes(inf.id)}
                            onChange={() => toggleSeleccion(inf.id)} className="cursor-pointer" />
                          Para insights
                        </label>
                        <button onClick={() => accion(inf.id, '/retirar')}
                          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
                          style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
                          <AlertTriangle size={13} /> Retirar
                        </button>
                      </>
                    )}
                  </SoloAdmin>

                  <button onClick={() => abrirGraficas(inf.id)}
                    className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
                    style={{ borderColor: 'var(--sabana-navy)', color: 'var(--sabana-navy)', cursor: 'pointer' }}>
                    <BarChart3 size={13} /> {abierto === inf.id ? 'Ocultar' : 'Ver gráficas'}
                  </button>
                </div>

                {abierto === inf.id && (
                  <div className="mt-2 rounded-lg border p-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                    <GraficasInforme detalle={detalle} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---------- Informe de insights (Gemini) + Insights Conjuntos ---------- */}
      {informes.some((i) => i.estado === 'validado') && (
        <SoloAdmin>
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold mb-1 flex items-center gap-2" style={{ color: 'var(--sabana-dark-navy)' }}>
              <Sparkles size={18} /> Informe de insights (Gemini)
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
              Marca «Para insights» en uno o más informes validados y genera un análisis narrativo
              a partir de sus skills ya extraídas y verificadas (no vuelve a leer el PDF). Con
              «Insights Conjuntos» la IA propone qué informes conviene analizar juntos.
            </p>

            <div className="flex flex-wrap gap-3">
              <button onClick={generarInsights} disabled={seleccionados.length === 0 || insightsLoading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
                style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: seleccionados.length === 0 ? 'not-allowed' : 'pointer' }}>
                <Sparkles size={16} />
                {insightsLoading
                  ? 'Generando…'
                  : `Generar informe de insights${seleccionados.length ? ` (${seleccionados.length})` : ''}`}
              </button>
              <button onClick={() => setConjuntosAbierto((v) => !v)}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold border"
                style={{ borderColor: 'var(--sabana-navy)', color: 'var(--sabana-navy)', cursor: 'pointer' }}>
                <Layers size={16} /> Insights Conjuntos {conjuntosAbierto ? '▲' : '▼'}
              </button>
            </div>

            {insightsLoading && <div className="mt-4"><Spinner label="Gemini está analizando los informes seleccionados..." /></div>}

            {insightsError && (
              <div className="mt-4 rounded-lg p-3 bg-red-50 text-red-700 text-sm">{insightsError}</div>
            )}

            {insights && !insightsLoading && (
              <div className="mt-4 rounded-lg border p-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                <p className="text-xs mb-3" style={{ color: 'var(--sabana-black-50)' }}>
                  Basado en: {insights.informes.map((i) => `${i.editor} — ${i.titulo} (${i.anio_referencia})${i.antiguo ? ' ⚠ hace más de 2 años' : ''}`).join(' · ')}
                  {insights.omitidos.length > 0 && ` — se omitieron ${insights.omitidos.length} id(s) por no existir o no estar validados.`}
                </p>
                {!insights.persistido && (
                  <div className="rounded-lg p-2 mb-3 text-xs" style={{ background: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}>
                    {insights.aviso ?? 'El insight no quedó guardado (pendiente de aplicar migración 012).'}
                  </div>
                )}
                <AssistantContent content={insights.texto} />
              </div>
            )}

            <InsightsConjuntos abierto={conjuntosAbierto} />
          </div>
        </SoloAdmin>
      )}

      {/* ---------- Comparativa entre informes (desde 2 validados) ---------- */}
      {comparativa && comparativa.terminos.length > 0 && (
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
          <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
            Comparativa entre informes
          </h3>
          <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
            Qué posición ocupa cada skill en cada informe. Se comparan <b>posiciones</b>, no
            menciones: el conteo depende de la extensión de cada documento.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                  <th className="text-left px-3 py-2 font-semibold">Skill</th>
                  {comparativa.informes.map((i) => (
                    <th key={i.id} className="text-right px-3 py-2 font-semibold">{i.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparativa.terminos.map((t, idx) => (
                  <tr key={t.termino} style={{ backgroundColor: idx % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                    <td className="px-3 py-2" style={{ color: 'var(--sabana-dark-navy)' }}>{t.termino}</td>
                    {comparativa.informes.map((i) => (
                      <td key={i.id} className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>
                        {t.posiciones[i.id] != null ? `#${t.posiciones[i.id]}` : '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
