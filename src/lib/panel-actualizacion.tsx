'use client';

/**
 * <PanelActualizacion /> — bloque de Administrador que acompaña al botón
 * "Actualizar histórico" en la página de Tendencias.
 *
 * Tres cosas, en este orden, porque son las que el Admin necesita ANTES de
 * pulsar el botón:
 *
 *   1. FUENTES CONSULTADAS: cada fuente/zona del catálogo con la fecha de su
 *      última búsqueda (GET /tendencias/fuentes/estado, calculada desde los
 *      datos) y cuáles NUNCA se han consultado.
 *   2. SEMÁFORO DE SERPAPI: cuántas búsquedas quedan del cupo mensual de
 *      Google Jobs (GET /tendencias/serpapi/estado; leer la cuenta NO consume
 *      búsquedas) y una recomendación. Regla del Tech Lead: verde si quedan
 *      al menos `presupuesto` búsquedas; amarillo si quedan menos (corrida
 *      parcial; si el cupo se renueva en <= 2 días, esperar); rojo si quedan
 *      0 o la cuenta no responde y no hay estimación. El cupo se renueva el
 *      día 19. Ver src/backend/GoogleJobs/serpapi_cuota.py.
 *   3. El BOTÓN y, tras pulsarlo, el resumen por fuente/zona que devuelve
 *      POST /tendencias/recolectar (estado, filas, llamadas, error, duración).
 *
 * Solo lo ve el Admin: quien lo monta lo envuelve en <SoloAdmin>. Los fetch
 * llevan `authHeaders()`; un 401 significa que el token dejó de valer (p. ej.
 * el backend se reinició sin AUTH_SECRET fijo) y entonces se cierra la sesión
 * local con `logout()` y se avisa, en vez de mostrar un error genérico.
 */

import { useCallback, useEffect, useState } from 'react';
import { authHeaders, useAuth } from '@/lib/auth';
import { Spinner } from '@/lib/spinner';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export const MENSAJE_SESION_EXPIRADA =
  'La sesión de Administrador expiró, vuelve a iniciar sesión.';

// ---------------------------------------------------------------------------
// Tipos de los tres endpoints
// ---------------------------------------------------------------------------

export interface FilaFuenteActualizada {
  fuente: string;
  pais: string;
  label: string;
  estado: 'ok' | 'sin_cambios' | 'parcial' | 'omitida' | 'desactivada' | 'error';
  filas: number | null;
  llamadas: number | null;
  error: string | null;
  duracion_seg: number | null;
}

export interface ResumenActualizacion {
  status: 'completed' | 'parcial' | 'error';
  inicio: string;
  fin?: string;
  duracion_seg?: number;
  fuentes: FilaFuenteActualizada[];
  recalculo: { observaciones: number; mercados: string[] } | null;
  vacantes_historicas_totales: number | null;
  error: string | null;
}

interface FuenteEstado {
  id: string;
  fuente: string;
  pais: string;
  label: string;
  filas_historico: number | null;
  ultima_busqueda: string | null;
  origen_fecha: string | null;
  consultada: boolean;
  ultima_actualizacion: { estado: string; filas: number | null; error: string | null; fin: string } | null;
}

interface EstadoFuentes {
  fuentes: FuenteEstado[];
  nunca_consultadas: string[];
  actualizacion: { en_curso: boolean; inicio: string | null; ultima_fin: string | null; ultimo_status: string | null };
}

interface EstadoSerpapi {
  semaforo: 'verde' | 'amarillo' | 'rojo';
  recomendacion: string;
  restantes: number | null;
  total: number | null;
  uso_mes: number | null;
  extra_credits: number | null;
  presupuesto: number;
  dias_para_reset: number;
  fecha_reset: string;
  estimado: boolean;
  fuente_dato: string | null;
  plan: string | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Presentación
// ---------------------------------------------------------------------------

// El color va SIEMPRE acompañado del nombre y del símbolo: la identidad no
// depende solo del color.
const SEMAFORO: Record<EstadoSerpapi['semaforo'], { color: string; texto: string; simbolo: string }> = {
  verde: { color: '#15803d', texto: 'Verde', simbolo: '●' },
  amarillo: { color: '#b45309', texto: 'Amarillo', simbolo: '●' },
  rojo: { color: '#b91c1c', texto: 'Rojo', simbolo: '●' },
};

const ESTADO_FILA: Record<FilaFuenteActualizada['estado'], { texto: string; color: string }> = {
  ok: { texto: 'OK', color: '#15803d' },
  sin_cambios: { texto: 'Sin cambios', color: 'var(--sabana-black-70)' },
  parcial: { texto: 'Parcial', color: '#b45309' },
  omitida: { texto: 'Omitida', color: '#b45309' },
  desactivada: { texto: 'Desactivada', color: 'var(--sabana-black-50)' },
  error: { texto: 'Error', color: '#b91c1c' },
};

function fmtFecha(iso: string | null | undefined): string {
  if (!iso) return 'Nunca';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
}

function fmtDuracion(seg: number | null | undefined): string {
  if (seg === null || seg === undefined) return '—';
  if (seg < 60) return `${seg.toFixed(0)} s`;
  const m = Math.floor(seg / 60);
  return `${m} min ${Math.round(seg - m * 60)} s`;
}

interface Props {
  onActualizar: () => void;
  actualizando: boolean;
  resultado: ResumenActualizacion | null;
  errorActualizacion: string | null;
  /** Cambia tras cada actualización para recargar el estado de las fuentes. */
  version: number;
}

export function PanelActualizacion({ onActualizar, actualizando, resultado, errorActualizacion, version }: Props) {
  const { logout } = useAuth();
  const [fuentes, setFuentes] = useState<EstadoFuentes | null>(null);
  const [serpapi, setSerpapi] = useState<EstadoSerpapi | null>(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setAviso(null);
    try {
      const [rf, rs] = await Promise.all([
        fetch(`${BACKEND_URL}/tendencias/fuentes/estado`, { headers: authHeaders() }),
        fetch(`${BACKEND_URL}/tendencias/serpapi/estado`, { headers: authHeaders() }),
      ]);
      if (rf.status === 401 || rs.status === 401) {
        logout();
        setAviso(MENSAJE_SESION_EXPIRADA);
        return;
      }
      setFuentes(rf.ok ? await rf.json() : null);
      setSerpapi(rs.ok ? await rs.json() : null);
      if (!rf.ok || !rs.ok) setAviso('No se pudo leer el estado de alguna fuente; revisa el backend.');
    } catch {
      setAviso('No se pudo contactar al backend para leer el estado de las fuentes.');
    } finally {
      setCargando(false);
    }
  }, [logout]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargar();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [cargar, version]);

  const sem = serpapi ? SEMAFORO[serpapi.semaforo] : null;
  const enCurso = actualizando || !!fuentes?.actualizacion.en_curso;

  return (
    <section
      className="rounded-lg border p-5 mb-10"
      style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--white-background)' }}
      aria-label="Panel de administración: actualización del histórico"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
        <h3 className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
          Fuentes consultadas
        </h3>
        <span className="text-xs text-zinc-500">Solo Administrador</span>
      </div>
      <p className="text-sm text-zinc-500 mb-4">
        Última búsqueda registrada en cada fuente y zona (se calcula desde las tablas: la fecha en que entró la
        última vacante). &ldquo;Nunca&rdquo; significa que esa zona del catálogo todavía no se ha recolectado.
      </p>

      {aviso && (
        <div className="rounded-lg p-3 mb-4 text-sm bg-amber-50 text-amber-900" role="status">
          {aviso}
        </div>
      )}

      {cargando && !fuentes ? (
        <Spinner size="sm" compact label="Leyendo el estado de las fuentes..." />
      ) : fuentes ? (
        <div className="overflow-x-auto mb-5">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                <th className="text-left px-3 py-2 font-semibold">Fuente — zona</th>
                <th className="text-left px-3 py-2 font-semibold">Última búsqueda</th>
                <th className="text-right px-3 py-2 font-semibold">Vacantes en histórico</th>
                <th className="text-left px-3 py-2 font-semibold">Última actualización</th>
              </tr>
            </thead>
            <tbody>
              {fuentes.fuentes.map((f, i) => (
                <tr key={f.id} style={{ backgroundColor: i % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                  <td className="px-3 py-1.5" style={{ color: 'var(--sabana-dark-navy)' }}>{f.label}</td>
                  <td className="px-3 py-1.5" style={{ color: f.consultada ? 'var(--sabana-dark-navy)' : '#b91c1c' }}>
                    {fmtFecha(f.ultima_busqueda)}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {f.filas_historico === null ? '—' : f.filas_historico.toLocaleString('es-CO')}
                  </td>
                  <td className="px-3 py-1.5 text-xs text-zinc-500">
                    {f.ultima_actualizacion
                      ? `${ESTADO_FILA[f.ultima_actualizacion.estado as FilaFuenteActualizada['estado']]?.texto ?? f.ultima_actualizacion.estado}${
                          f.ultima_actualizacion.error ? ` · ${f.ultima_actualizacion.error}` : ''
                        }`
                      : 'Sin corrida en esta sesión del backend'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {fuentes.nunca_consultadas.length > 0 && (
            <p className="text-xs mt-2" style={{ color: '#b91c1c' }}>
              Nunca consultadas: {fuentes.nunca_consultadas.join(', ')}.
            </p>
          )}
        </div>
      ) : null}

      {/* ---------------- Semáforo SerpApi ---------------- */}
      <div
        className="rounded-lg p-4 mb-5 border-l-4"
        style={{ borderColor: sem?.color ?? 'var(--sabana-light-blue)', backgroundColor: 'var(--sabana-sky-blue)' }}
        role="status"
        aria-label={sem ? `Semáforo SerpApi: ${sem.texto}` : 'Semáforo SerpApi'}
      >
        <p className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: 'var(--sabana-navy)' }}>
          Cuota de SerpApi (Google Jobs)
        </p>
        {serpapi && sem ? (
          <>
            <p className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--sabana-dark-navy)' }}>
              <span style={{ color: sem.color, fontSize: '1.2rem' }} aria-hidden="true">{sem.simbolo}</span>
              {sem.texto}
              {serpapi.estimado && <span className="text-xs font-normal text-zinc-500">(estimado con el uso local)</span>}
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              Restantes: <b>{serpapi.restantes ?? '—'}</b> / {serpapi.total ?? '—'} búsquedas ·
              Uso del mes: <b>{serpapi.uso_mes ?? '—'}</b> ·
              Presupuesto por corrida: <b>{serpapi.presupuesto}</b> ·
              Reset en <b>{serpapi.dias_para_reset}</b> día(s) ({serpapi.fecha_reset})
              {serpapi.extra_credits ? ` · Créditos extra: ${serpapi.extra_credits}` : ''}
            </p>
            <p className="text-xs mt-1 text-zinc-600">{serpapi.recomendacion}</p>
            {serpapi.error && <p className="text-xs mt-1 text-zinc-500">{serpapi.error}</p>}
          </>
        ) : cargando ? (
          <Spinner size="sm" compact label="Consultando la cuenta de SerpApi..." />
        ) : (
          <p className="text-sm text-zinc-500">Sin datos de la cuenta de SerpApi.</p>
        )}
      </div>

      {/* ---------------- Botón ---------------- */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={onActualizar}
          disabled={enCurso}
          className="px-6 py-2 rounded-lg font-semibold disabled:opacity-60"
          style={{ backgroundColor: 'var(--sabana-navy)', color: 'white', cursor: enCurso ? 'wait' : 'pointer' }}
        >
          {enCurso ? 'Actualizando histórico (todas las fuentes)...' : 'Actualizar histórico (todas las fuentes)'}
        </button>
        <span className="text-xs text-zinc-500 max-w-md">
          Adzuna (5 mercados), Google Jobs (Colombia) y LinkedIn (co, mx, ar, cl, pe), luego recálculo. Si una
          fuente falla, continúa con la siguiente. Puede tardar varios minutos.
        </span>
      </div>

      {errorActualizacion && (
        <div className="rounded-lg p-3 mt-4 text-sm bg-red-50 text-red-700" role="alert">
          {errorActualizacion}
        </div>
      )}

      {/* ---------------- Resultado de la última corrida ---------------- */}
      {resultado && (
        <div className="mt-5">
          <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
            Resultado de la actualización:{' '}
            <span style={{ color: resultado.status === 'completed' ? '#15803d' : resultado.status === 'parcial' ? '#b45309' : '#b91c1c' }}>
              {resultado.status === 'completed' ? 'completa' : resultado.status === 'parcial' ? 'parcial' : 'con error'}
            </span>
            {resultado.duracion_seg !== undefined && ` · ${fmtDuracion(resultado.duracion_seg)}`}
            {resultado.vacantes_historicas_totales !== null &&
              ` · ${resultado.vacantes_historicas_totales.toLocaleString('es-CO')} vacantes en el histórico`}
            {resultado.recalculo && ` · ${resultado.recalculo.observaciones.toLocaleString('es-CO')} observaciones recalculadas`}
          </p>
          {resultado.error && <p className="text-xs mt-1 text-red-700">{resultado.error}</p>}
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                  <th className="text-left px-3 py-2 font-semibold">Fuente — zona</th>
                  <th className="text-left px-3 py-2 font-semibold">Estado</th>
                  <th className="text-right px-3 py-2 font-semibold">Filas</th>
                  <th className="text-right px-3 py-2 font-semibold">Llamadas</th>
                  <th className="text-right px-3 py-2 font-semibold">Duración</th>
                  <th className="text-left px-3 py-2 font-semibold">Detalle</th>
                </tr>
              </thead>
              <tbody>
                {resultado.fuentes.map((f, i) => (
                  <tr key={`${f.fuente}:${f.pais}`} style={{ backgroundColor: i % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                    <td className="px-3 py-1.5" style={{ color: 'var(--sabana-dark-navy)' }}>{f.label}</td>
                    <td className="px-3 py-1.5 font-semibold" style={{ color: ESTADO_FILA[f.estado]?.color }}>
                      {ESTADO_FILA[f.estado]?.texto ?? f.estado}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {f.filas === null ? '—' : f.filas.toLocaleString('es-CO')}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {f.llamadas === null ? '—' : f.llamadas}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-zinc-500">{fmtDuracion(f.duracion_seg)}</td>
                    <td className="px-3 py-1.5 text-xs text-zinc-500">{f.error ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
