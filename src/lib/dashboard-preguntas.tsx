'use client';

/**
 * <DashboardPreguntas /> — panel de Administrador de la página Empresas.
 *
 * Muestra dos cosas que son información OPERATIVA (decisión del Tech Lead:
 * solo el Admin las ve, el usuario final no necesita saber cuánto cuesta su
 * pregunta):
 *
 *   1. COSTO DE LA SESIÓN ACTUAL: preguntas, tokens y USD estimados de la
 *      conversación abierta en esta pestaña. Se calcula en el navegador con
 *      el tráiler de uso que devuelve /api/chat (ver src/lib/chat-sesion.ts).
 *   2. PREGUNTAS MÁS REALIZADAS por categoría (Perfil ocupacional, Análisis
 *      salarial, Cursos, Competencias, Empresas) con totales, desde
 *      GET /asistente/preguntas/resumen. Si la tabla no existe todavía, el
 *      backend responde `disponible=false` y aquí se dice "pendiente de
 *      aplicar migración 011" en lugar de fallar.
 *
 * Todo lo que dice "estimado" lo es: precios configurados por variable de
 * entorno, no la factura del proveedor.
 */

import { useCallback, useEffect, useState } from 'react';
import { authHeaders, useAuth } from '@/lib/auth';
import { Spinner } from '@/lib/spinner';
import { formatearTokens, formatearUsd } from '@/lib/chat-sesion';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export const MENSAJE_SESION_EXPIRADA =
  'La sesión de Administrador expiró, vuelve a iniciar sesión.';

export interface CostoSesion {
  preguntas: number;
  conTokens: number;
  tokensEntrada: number;
  tokensSalida: number;
  costoUsd: number;
}

interface Categoria {
  categoria: string;
  etiqueta: string;
  total: number;
  distintas: number;
  sesiones: number;
  tokens_entrada: number;
  tokens_salida: number;
  costo_usd_estimado: number;
  top: { pregunta: string; veces: number; ultima_vez: string }[];
}

interface Resumen {
  disponible: boolean;
  motivo?: string;
  categorias: Categoria[];
  totales: {
    preguntas: number;
    sesiones: number;
    tokens_entrada: number;
    tokens_salida: number;
    costo_usd_estimado: number;
    costo_usd_por_sesion: number | null;
    costo_usd_por_pregunta: number | null;
    con_tokens: number;
    modelos: Record<string, number>;
  } | null;
  nota?: string;
}

export function DashboardPreguntas({ sesion }: { sesion: CostoSesion }) {
  const { logout } = useAuth();
  const [datos, setDatos] = useState<Resumen | null>(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setAviso(null);
    try {
      const r = await fetch(`${BACKEND_URL}/asistente/preguntas/resumen?top=8`, { headers: authHeaders() });
      if (r.status === 401) {
        logout();
        setAviso(MENSAJE_SESION_EXPIRADA);
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setDatos(await r.json());
    } catch (e) {
      setAviso(`No se pudo leer el resumen de preguntas (${e instanceof Error ? e.message : 'error'}).`);
    } finally {
      setCargando(false);
    }
  }, [logout]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargar();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [cargar]);

  return (
    <section
      className="rounded-lg border p-4 mb-4 text-sm"
      style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--white-background)' }}
      aria-label="Panel de administración del asistente"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h3 className="font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
          Uso del asistente (Administrador)
        </h3>
        <button
          onClick={cargar}
          className="text-xs font-semibold underline cursor-pointer"
          style={{ color: 'var(--sabana-navy)' }}
        >
          Actualizar
        </button>
      </div>

      {/* ---------------- Sesión actual ---------------- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          { t: 'Preguntas en esta sesión', v: String(sesion.preguntas) },
          { t: 'Tokens de entrada', v: formatearTokens(sesion.tokensEntrada) },
          { t: 'Tokens de salida', v: formatearTokens(sesion.tokensSalida) },
          { t: 'Costo estimado de la sesión', v: formatearUsd(sesion.costoUsd) },
        ].map((k) => (
          <div key={k.t} className="rounded-lg p-3" style={{ backgroundColor: 'var(--sabana-sky-blue)' }}>
            <p className="text-[11px] font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>{k.t}</p>
            <p className="text-xl font-bold mt-0.5" style={{ color: 'var(--sabana-dark-navy)' }}>{k.v}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-zinc-500 mb-4">
        Estimado con los precios configurados en el servidor (GEMINI_USD_POR_1M_ENTRADA / _SALIDA); no es la
        factura. {sesion.conTokens < sesion.preguntas && sesion.preguntas > 0
          ? `${sesion.preguntas - sesion.conTokens} pregunta(s) sin conteo de tokens del modelo.`
          : ''}
      </p>

      {/* ---------------- Histórico por categoría ---------------- */}
      {aviso && <div className="rounded-lg p-3 mb-3 bg-amber-50 text-amber-900" role="status">{aviso}</div>}

      {cargando && !datos ? (
        <Spinner size="sm" compact label="Cargando preguntas..." />
      ) : datos && !datos.disponible ? (
        <div className="rounded-lg p-3 bg-amber-50 text-amber-900" role="status">
          Dashboard de preguntas <b>pendiente de aplicar migración 011</b> (<code>preguntas_asistente</code>) en
          Supabase. Hasta entonces las preguntas no se registran.
          {datos.motivo && <span className="block text-xs mt-1 opacity-80">{datos.motivo}</span>}
        </div>
      ) : datos && datos.totales ? (
        <>
          <p className="text-xs text-zinc-600 mb-3">
            Histórico registrado: <b>{datos.totales.preguntas.toLocaleString('es-CO')}</b> preguntas en{' '}
            <b>{datos.totales.sesiones.toLocaleString('es-CO')}</b> sesiones · costo estimado total{' '}
            <b>{formatearUsd(datos.totales.costo_usd_estimado)}</b>
            {datos.totales.costo_usd_por_sesion !== null && ` · ${formatearUsd(datos.totales.costo_usd_por_sesion)} por sesión`}
            {datos.totales.costo_usd_por_pregunta !== null && ` · ${formatearUsd(datos.totales.costo_usd_por_pregunta)} por pregunta`}
            {' '}· modelos: {Object.entries(datos.totales.modelos).map(([m, n]) => `${m} (${n})`).join(', ') || '—'}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {datos.categorias
              .filter((c) => c.total > 0 || ['perfil_ocupacional', 'analisis_salarial', 'cursos', 'competencias'].includes(c.categoria))
              .map((c) => (
                <div key={c.categoria} className="rounded-lg border p-3" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
                  <p className="font-semibold flex items-baseline justify-between" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {c.etiqueta}
                    <span className="text-xs font-normal text-zinc-500">
                      {c.total} preguntas · {c.sesiones} sesiones · {formatearUsd(c.costo_usd_estimado)}
                    </span>
                  </p>
                  {c.top.length === 0 ? (
                    <p className="text-xs text-zinc-400 mt-1">Todavía sin preguntas registradas.</p>
                  ) : (
                    <ol className="mt-2 space-y-1 text-xs">
                      {c.top.map((p, i) => (
                        <li key={`${c.categoria}-${i}`} className="flex gap-2">
                          <span className="font-semibold w-5 text-right" style={{ color: 'var(--sabana-navy)' }}>{i + 1}.</span>
                          <span className="flex-1 min-w-0" style={{ color: 'var(--sabana-dark-navy)' }}>{p.pregunta}</span>
                          <span className="text-zinc-500 whitespace-nowrap">×{p.veces}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              ))}
          </div>
          {datos.nota && <p className="text-[11px] text-zinc-400 mt-3">{datos.nota}</p>}
        </>
      ) : null}
    </section>
  );
}
