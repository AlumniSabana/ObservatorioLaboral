'use client';

/**
 * <InsightsConjuntos /> — panel de Admin para los "Insights Conjuntos".
 *
 * Dos pasos, espejo del backend (Informes/insights_conjuntos.py):
 *   1. POST /informes/insights-conjuntos/candidatos -> la IA propone GRUPOS de
 *      informes validados afines (sobre un solapamiento de skills calculado en
 *      Python) y explica en una frase por qué van juntos.
 *   2. "Generar Insight Conjunto" en un grupo -> POST /informes/insights-conjuntos
 *      sintetiza esos informes y lo persiste (tipo 'conjunto', migración 012).
 *
 * El componente queda MONTADO aunque se cierre (`abierto=false` -> no pinta
 * nada) para no perder los candidatos ya pedidos: cada propuesta cuesta una
 * llamada a Gemini, y se re-pide solo con el botón "Volver a proponer".
 *
 * Todo lo que hay aquí es exclusivo del Admin (el padre lo envuelve en
 * <SoloAdmin>) y manda `authHeaders()`.
 */

import { useEffect, useState } from 'react';
import { Layers, Sparkles, ChevronDown, ChevronUp, RefreshCw, Clock } from 'lucide-react';
import { AssistantContent } from '@/lib/markdown';
import { Spinner } from '@/lib/spinner';
import { authHeaders, useAuth } from '@/lib/auth';
import type {
  CandidatosResp,
  GrupoCandidato,
  InsightConjuntoResp,
  InsightGenerado,
  InsightsGeneradosResp,
} from './comun';
import { BACKEND_URL, errorDeRespuesta, etiquetaInforme, formatearFecha } from './comun';

const claveGrupo = (g: GrupoCandidato) => [...g.informe_ids].sort().join('|');

export function InsightsConjuntos({ abierto }: { abierto: boolean }) {
  // Con 401 (token caducado tras reiniciar el backend) se cierra la sesión local.
  const { logout } = useAuth();
  const [candidatos, setCandidatos] = useState<CandidatosResp | null>(null);
  const [cargandoCand, setCargandoCand] = useState(false);
  const [errorCand, setErrorCand] = useState<string | null>(null);

  // Grupo que se está generando (por clave), y el último resultado.
  const [generando, setGenerando] = useState<string | null>(null);
  const [resultado, setResultado] = useState<InsightConjuntoResp | null>(null);
  const [errorGen, setErrorGen] = useState<string | null>(null);

  // Conjuntos ya guardados (para no volver a pagar por lo que ya existe).
  const [historico, setHistorico] = useState<InsightsGeneradosResp | null>(null);
  const [historicoAbierto, setHistoricoAbierto] = useState<number | null>(null);

  const cargarHistorico = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/informes/insights-generados?tipo=conjunto`);
      setHistorico(r.ok ? await r.json() : null);
    } catch {
      setHistorico(null);
    }
  };

  const pedirCandidatos = async () => {
    setCargandoCand(true);
    setErrorCand(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/insights-conjuntos/candidatos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
      });
      if (!r.ok) throw new Error(await errorDeRespuesta(r, logout));
      setCandidatos(await r.json());
    } catch (e) {
      setErrorCand(e instanceof Error ? e.message : 'No se pudieron proponer grupos');
    } finally {
      setCargandoCand(false);
    }
  };

  // La primera vez que se abre el panel se piden candidatos e histórico; las
  // siguientes solo se muestra lo que ya hay (evita gastar en Gemini al alternar).
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!abierto || candidatos || cargandoCand) return;
    pedirCandidatos();
    cargarHistorico();
    /* eslint-enable react-hooks/set-state-in-effect */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto]);

  const generar = async (g: GrupoCandidato) => {
    setGenerando(claveGrupo(g));
    setErrorGen(null);
    setResultado(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/insights-conjuntos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ informe_ids: g.informe_ids, motivo_grupo: g.motivo }),
      });
      if (!r.ok) throw new Error(await errorDeRespuesta(r, logout));
      setResultado(await r.json());
      await cargarHistorico();
    } catch (e) {
      setErrorGen(e instanceof Error ? e.message : 'No se pudo generar el insight conjunto');
    } finally {
      setGenerando(null);
    }
  };

  if (!abierto) return null;

  const nombre = (id: string) => {
    const inf = candidatos?.informes.find((i) => i.id === id);
    return inf ? etiquetaInforme(inf) : id;
  };

  return (
    <div className="mt-4 rounded-lg border p-4 space-y-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--sabana-dark-navy)' }}>
          <Layers size={16} /> Grupos de informes afines propuestos por la IA
        </h4>
        <button onClick={pedirCandidatos} disabled={cargandoCand}
          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border disabled:opacity-50"
          style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
          <RefreshCw size={12} /> Volver a proponer
        </button>
      </div>
      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
        Primero se calcula qué skills comparten los informes validados (sin IA); con ese resumen,
        Gemini agrupa y explica el motivo. Generar un insight conjunto cuesta una llamada al modelo.
      </p>

      {cargandoCand && <Spinner compact label="Buscando informes afines…" />}
      {errorCand && <div className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">{errorCand}</div>}

      {candidatos && !cargandoCand && (
        <>
          {candidatos.aviso && (
            <div className="rounded-lg p-3 text-xs" style={{ background: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}>
              {candidatos.aviso}
            </div>
          )}
          {candidatos.grupos.length === 0 ? (
            <p className="text-sm text-center py-3" style={{ color: 'var(--sabana-black-50)' }}>
              No se encontraron grupos con afinidad suficiente entre los informes validados.
            </p>
          ) : (
            <div className="space-y-2">
              {candidatos.grupos.map((g) => {
                const clave = claveGrupo(g);
                return (
                  <div key={clave} className="rounded-lg border p-3" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
                    <div className="flex flex-wrap items-start gap-3">
                      <div className="flex-1 min-w-[16rem]">
                        <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
                          {g.titulo_grupo}
                          <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded"
                            style={{ background: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}>
                            afinidad {Math.round(g.afinidad * 100)} %
                          </span>
                        </p>
                        <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-70)' }}>{g.motivo}</p>
                        <ul className="text-xs mt-1 list-disc pl-5" style={{ color: 'var(--sabana-black-50)' }}>
                          {g.informe_ids.map((id) => <li key={id}>{nombre(id)}</li>)}
                        </ul>
                      </div>
                      <button onClick={() => generar(g)} disabled={generando !== null}
                        className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded text-white disabled:opacity-50"
                        style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: generando ? 'wait' : 'pointer' }}>
                        <Sparkles size={13} />
                        {generando === clave ? 'Generando…' : 'Generar Insight Conjunto'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {generando && <Spinner label="Gemini está sintetizando el grupo de informes..." />}
      {errorGen && <div className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">{errorGen}</div>}

      {resultado && !generando && (
        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm font-bold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>{resultado.titulo}</p>
          <p className="text-xs mb-3" style={{ color: 'var(--sabana-black-50)' }}>
            Basado en: {resultado.informes.map((i) => `${etiquetaInforme(i)}${i.antiguo ? ' ⚠ hace más de 2 años' : ''}`).join(' · ')}
            {resultado.omitidos.length > 0 && ` — se omitieron ${resultado.omitidos.length} id(s) por no estar validados.`}
          </p>
          {!resultado.persistido && (
            <div className="rounded-lg p-2 mb-3 text-xs" style={{ background: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}>
              {resultado.aviso ?? 'El insight no quedó guardado (pendiente de aplicar migración 012).'}
            </div>
          )}
          <AssistantContent content={resultado.texto} />
        </div>
      )}

      {/* Conjuntos ya generados: se listan para no volver a pagar por lo mismo. */}
      <div>
        <h4 className="text-sm font-bold flex items-center gap-2 mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
          <Clock size={14} /> Insights conjuntos guardados
        </h4>
        {historico === null ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
        ) : !historico.disponible ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
            {historico.aviso ?? 'Pendiente de aplicar la migración 012.'}
          </p>
        ) : historico.insights.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Todavía no hay insights conjuntos guardados.</p>
        ) : (
          <div className="space-y-2">
            {historico.insights.map((ins: InsightGenerado) => (
              <div key={ins.id} className="rounded-lg border" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
                <button onClick={() => setHistoricoAbierto(historicoAbierto === ins.id ? null : ins.id)}
                  className="w-full flex items-center justify-between gap-2 p-3 text-left" style={{ cursor: 'pointer' }}>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>{ins.titulo}</p>
                    <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                      {formatearFecha(ins.creado_en)}{ins.motivo_grupo ? ` · ${ins.motivo_grupo}` : ''}
                    </p>
                  </div>
                  {historicoAbierto === ins.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
                {historicoAbierto === ins.id && (
                  <div className="px-3 pb-3"><AssistantContent content={ins.contenido} /></div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
