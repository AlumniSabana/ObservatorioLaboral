'use client';

/**
 * Página "Análisis salarial" (ruta '/salaries').
 *
 * Muestra salarios REALES en COP pivotados por PROGRAMA académico. Los datos
 * salen del backend (GET /analytics/salarios), que a su vez lee la GEIH del DANE
 * agregada por ocupación CNO y los rangos de vacantes del SPE Colombia.
 *
 * Flujo:
 *   - Al montar -> GET /analytics/salarios  (resumen: meta + lista de programas).
 *   - Al elegir programa -> GET /analytics/salarios?programa=... (KPIs +
 *     comparativa por subgrupo ocupacional + rango SPE de la mediana).
 *
 * Nota de granularidad: la GEIH da salario por OCUPACIÓN, no por programa. Cada
 * programa se asocia al gran grupo ocupacional (CNO 2 dígitos) de sus egresados,
 * así que programas afines (p. ej. las ingenierías) comparten referencia. Es la
 * resolución honesta de la fuente; se comunica como tal en la página.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { useState, useEffect, useMemo } from 'react';
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Estilos comunes de tooltip/ejes, iguales a los de /analytics.
const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};

// ---------------------------------------------------------------------------
// Tipos que devuelve el backend
// ---------------------------------------------------------------------------
interface Kpis {
  mediana: number;
  media: number;
  p25: number;
  p75: number;
  p10: number;
  p90: number;
  n: number;
}

interface ItemComparativa {
  codigo: string;
  nombre: string;
  mediana: number;
  n: number;
  es_actual: boolean;
}

interface RangoSpe {
  rango: string;
  min_cop: number | null;
  max_cop: number | null;
  participacion: number;
  variacion: number;
}

interface Meta {
  periodo?: string;
  fuente?: string;
  mediana_nacional?: number | null;
  nota?: string;
}

interface NivelEducativo {
  codigo: string;
  nombre: string;
  orden: number;
  mediana: number;
  p25: number;
  p75: number;
  n: number;
}

interface Resumen {
  meta: Meta;
  programas: string[];
  spe_rangos: RangoSpe[];
  nivel_educativo: NivelEducativo[];
  tiene_geih: boolean;
}

// ── OLE (MinEducación) ─────────────────────────────────────────────────────
// Mide algo DISTINTO de la GEIH y por eso va en su propia sección, sin
// promediarse: la GEIH mide a quien ejerce la ocupación (venga de la formación
// que venga) y el OLE a quien se graduó de este programa. Además el OLE publica
// BANDAS de SMMLV, no pesos: la mediana es estimada por interpolación.
interface BandaOle {
  rango: string;
  graduados: number;
  pct: number;
}

interface ResumenOle {
  graduados: number;
  mediana_smmlv: number | null;
  mediana_cop: number | null;
  /** La mediana cayó en 'Más de 9 SMMLV', que no tiene techo con el que interpolar. */
  mediana_abierta: boolean;
  pct_sobre_4smmlv: number;
  muestra_corta: boolean;
  distribucion: BandaOle[];
  anios_grado?: [number, number] | null;
  n_ies?: number | null;
}

interface Ole {
  programa: string;
  sin_datos: boolean;
  sabana: ResumenOle | null;
  /** null cuando La Sabana es la única que ofrece el programa: no hay con qué comparar. */
  nacional: ResumenOle | null;
  unico_oferente?: boolean;
  brecha_vs_nacional_pct?: number | null;
  anio_corte?: number;
}

interface PosgradoOle extends ResumenOle {
  programa: string;
  nivel: string;
}

interface AnalisisPrograma {
  programa: string;
  encontrado: boolean;
  cno: { codigo: string; nombre: string } | null;
  kpis: Kpis | null;
  comparativa: ItemComparativa[];
  rango_spe: RangoSpe | null;
  spe_rangos: RangoSpe[];
  nivel_educativo: NivelEducativo[];
  nivel_educativo_nacional: boolean;
  meta: Meta;
  tiene_geih: boolean;
}

// ---------------------------------------------------------------------------
// Helpers de formato COP
// ---------------------------------------------------------------------------
const fmtCOP = (v: number) =>
  '$' + v.toLocaleString('es-CO', { maximumFractionDigits: 0 });

const fmtM = (v: number) => `$${(v / 1e6).toFixed(1)}M`;

// Etiqueta corta de cada banda del OLE: el nombre completo ('Entre 1,5 y 2,5
// SMMLV') no cabe en el eje y repetir "SMMLV" siete veces es ruido.
const BANDA_CORTA: Record<string, string> = {
  '1 SMMLV': 'Hasta 1',
  'Entre 1 y 1,5 SMMLV': '1 – 1,5',
  'Entre 1,5 y 2,5 SMMLV': '1,5 – 2,5',
  'Entre 2,5 y 4 SMMLV': '2,5 – 4',
  'Entre 4 y 6 SMMLV': '4 – 6',
  'Entre 6 y 9 SMMLV': '6 – 9',
  'Más de 9 SMMLV': 'Más de 9',
};

/** Mediana del OLE en texto. Devuelve '> 9 SMMLV' cuando cayó en la banda abierta. */
const medianaOle = (r: ResumenOle | null): string => {
  if (!r) return '—';
  if (r.mediana_abierta) return '> 9 SMMLV';
  if (r.mediana_smmlv == null) return '—';
  return `${r.mediana_smmlv.toFixed(2)} SMMLV`;
};

export default function SalariesPage() {
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [programa, setPrograma] = useState<string>('');
  const [analisis, setAnalisis] = useState<AnalisisPrograma | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // OLE: va aparte del análisis GEIH a propósito. Si la migración 010 no ha
  // corrido, el backend responde `sin_datos` y la sección no se pinta.
  const [ole, setOle] = useState<Ole | null>(null);
  // Sección "Posgrados de La Sabana con mayores ingresos": retirada del
  // frontend a pedido de Alumni (en discusión), el backend (/ole/posgrados)
  // sigue intacto por si se retoma.
  // const [posgrados, setPosgrados] = useState<PosgradoOle[]>([]);

  // Carga inicial: resumen con la lista de programas disponibles.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/analytics/salarios`);
        if (!res.ok) throw new Error('No se pudo cargar el análisis salarial');
        const data: Resumen = await res.json();
        setResumen(data);
        // Programa por defecto: Ing. Informática si está, si no el primero.
        const inicial = data.programas.includes('Ingeniería Informática')
          ? 'Ingeniería Informática'
          : data.programas[0] ?? '';
        setPrograma(inicial);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido');
        setLoading(false);
      }
    })();
  }, []);

  // Cada cambio de programa recarga su análisis.
  useEffect(() => {
    if (!programa) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const url = new URL(`${BACKEND_URL}/analytics/salarios`);
        url.searchParams.append('programa', programa);
        const res = await fetch(url);
        if (!res.ok) throw new Error('No se pudo cargar el programa');
        setAnalisis(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido');
      } finally {
        setLoading(false);
      }
    })();
  }, [programa]);

  // OLE en petición aparte: es otra fuente y no debe retrasar ni tumbar el
  // análisis GEIH, que es la espina de la página.
  useEffect(() => {
    if (!programa) return;
    (async () => {
      try {
        const r = await fetch(
          `${BACKEND_URL}/ole/ingreso?programa=${encodeURIComponent(programa)}`,
        );
        const d: Ole | null = r.ok ? await r.json() : null;
        setOle(d && !d.sin_datos ? d : null);
      } catch {
        setOle(null);
      }
    })();
  }, [programa]);

  // Distribución comparada: una fila por banda, con el % de La Sabana y el del
  // país. Se compara en PORCENTAJE y no en conteo porque el país tiene tres
  // órdenes de magnitud más graduados y aplastaría la serie propia.
  const distribucionOle = useMemo(() => {
    if (!ole?.sabana) return [];
    return ole.sabana.distribucion.map((b, i) => ({
      banda: BANDA_CORTA[b.rango] ?? b.rango,
      sabana: b.pct,
      pais: ole.nacional?.distribucion[i]?.pct ?? null,
      graduados: b.graduados,
    }));
  }, [ole]);

  const meta = resumen?.meta ?? analisis?.meta;
  const kpis = analisis?.kpis;
  const comparativa = analisis?.comparativa ?? [];

  return (
    <>
      <PageLayout title="Análisis salarial">
        <div className="space-y-6">
          {/* Intro + fuentes */}
          <div>
            <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
              Salarios de referencia en pesos colombianos (COP) por programa académico,
              a partir de datos oficiales del mercado laboral.
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--sabana-black-50)' }}>
              Fuentes: <b>GEIH — DANE</b> (ingreso laboral real por ocupación) ·{' '}
              <b>SPE Colombia</b> (rangos de vacantes)
              {ole?.sabana && <> · <b>OLE — MinEducación</b> (egresados por programa)</>}
              {meta?.periodo ? ` · ${meta.periodo}` : ''}.
            </p>
          </div>

          {/* Selector de programa */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 shadow">
            <label
              className="block text-sm font-semibold mb-2"
              style={{ color: 'var(--sabana-dark-navy)' }}
            >
              Programa académico
            </label>
            <select
              value={programa}
              onChange={(e) => setPrograma(e.target.value)}
              className="w-full md:w-96 rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' }}
            >
              {resumen?.programas.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <div className="rounded-lg p-4 bg-red-50 text-red-700 text-sm">{error}</div>
          )}

          {loading && !analisis && (
            <div className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>
              Cargando…
            </div>
          )}

          {analisis && kpis && analisis.cno && (
            <>
              {/* Ocupación de referencia */}
              <div>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
                  {analisis.cno.nombre}
                </h3>
                <p className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>
                  Gran grupo ocupacional (CNO {analisis.cno.codigo}) al que se asocian
                  los egresados de <b>{analisis.programa}</b> · {kpis.n.toLocaleString('es-CO')} trabajadores en la GEIH.
                </p>
              </div>

              {/* KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Mediana mensual', value: fmtCOP(kpis.mediana), destacado: true },
                  { label: 'Percentil 25', value: fmtCOP(kpis.p25) },
                  { label: 'Percentil 75', value: fmtCOP(kpis.p75) },
                  { label: 'Rango típico (p10–p90)', value: `${fmtM(kpis.p10)} – ${fmtM(kpis.p90)}` },
                ].map((k) => (
                  <div
                    key={k.label}
                    className="rounded-lg p-4 border-l-4 bg-white dark:bg-zinc-800 shadow"
                    style={{ borderColor: k.destacado ? 'var(--sabana-dark-navy)' : 'var(--sabana-light-blue)' }}
                  >
                    <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>{k.label}</p>
                    <p className="text-xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {k.value}
                    </p>
                  </div>
                ))}
              </div>

              {/* ── Egresados de La Sabana (OLE, MinEducación) ─────────────
                  Va antes de la comparativa GEIH porque responde la pregunta
                  más directa de Alumni: qué ganan LOS NUESTROS. No se mezcla
                  con los KPIs de arriba: aquellos miden la ocupación, este el
                  programa, y promediarlos sería juntar dos universos. */}
              {ole?.sabana && (
                <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                  <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    Egresados de La Sabana — OLE, MinEducación {ole.anio_corte}
                  </h3>
                  <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                    Ingreso de los <b>{ole.sabana.graduados.toLocaleString('es-CO')}</b> graduados de{' '}
                    <b>{analisis.programa}</b>
                    {ole.sabana.anios_grado && ` (promociones ${ole.sabana.anios_grado[0]}–${ole.sabana.anios_grado[1]})`}
                    {' '}que cotizan a seguridad social. A diferencia de los KPIs de arriba, que miden{' '}
                    <b>la ocupación</b>, esto mide <b>el programa</b>: son nuestros egresados, no
                    quien ejerce el oficio.
                  </p>

                  {/* Cifras principales */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
                    <div
                      className="rounded-lg p-4 border-l-4"
                      style={{ borderColor: 'var(--sabana-dark-navy)', backgroundColor: 'var(--sabana-sky-blue)' }}
                    >
                      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Mediana — La Sabana</p>
                      <p className="text-2xl font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
                        {ole.sabana.mediana_cop ? fmtCOP(ole.sabana.mediana_cop) : medianaOle(ole.sabana)}
                      </p>
                      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                        {medianaOle(ole.sabana)} · estimada
                      </p>
                    </div>

                    <div className="rounded-lg p-4 border" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                        Mismo programa en el país
                      </p>
                      {ole.unico_oferente ? (
                        <p className="text-sm mt-2" style={{ color: 'var(--sabana-black-50)' }}>
                          La Sabana es la <b>única</b> institución que lo ofrece: no hay referencia
                          externa con la que compararse.
                        </p>
                      ) : (
                        <>
                          <p className="text-2xl font-bold" style={{ color: 'var(--sabana-navy)' }}>
                            {ole.nacional?.mediana_cop ? fmtCOP(ole.nacional.mediana_cop) : medianaOle(ole.nacional)}
                          </p>
                          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                            {medianaOle(ole.nacional)}
                            {ole.nacional?.n_ies ? ` · ${ole.nacional.n_ies} sedes lo ofrecen` : ''}
                          </p>
                        </>
                      )}
                    </div>

                    <div className="rounded-lg p-4 border" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                      <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Diferencia</p>
                      {ole.brecha_vs_nacional_pct != null ? (
                        <>
                          <p
                            className="text-2xl font-bold"
                            style={{ color: ole.brecha_vs_nacional_pct >= 0 ? 'var(--trend-up)' : 'var(--trend-down)' }}
                          >
                            {ole.brecha_vs_nacional_pct >= 0 ? '+' : ''}{ole.brecha_vs_nacional_pct}%
                          </p>
                          <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                            frente a la mediana nacional del programa
                          </p>
                        </>
                      ) : (
                        <p className="text-sm mt-2" style={{ color: 'var(--sabana-black-50)' }}>
                          Sin comparación disponible.
                        </p>
                      )}
                      <p className="text-xs mt-2" style={{ color: 'var(--sabana-black-50)' }}>
                        <b style={{ color: 'var(--sabana-dark-navy)' }}>{ole.sabana.pct_sobre_4smmlv}%</b>{' '}
                        gana más de 4 SMMLV
                      </p>
                    </div>
                  </div>

                  {ole.sabana.muestra_corta && (
                    <p
                      className="text-xs rounded px-3 py-2 mb-4"
                      style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}
                    >
                      Solo {ole.sabana.graduados} graduados cotizantes. Con una muestra tan
                      pequeña la mediana se mueve con unas pocas personas: tómese como indicio.
                    </p>
                  )}

                  {/* Distribución por banda */}
                  <p className="text-sm mb-2" style={{ color: 'var(--sabana-black-50)' }}>
                    Cómo se reparten por rango de ingreso (en SMMLV). El OLE no publica el salario
                    exacto, solo <b>en qué banda cae cada graduado</b>, así que esta distribución es
                    el dato real y la mediana de arriba se estima a partir de ella.
                  </p>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={distribucionOle} margin={{ left: 8, right: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="banda" tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                      <YAxis
                        tickFormatter={(v) => `${v}%`}
                        tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        itemStyle={{ color: 'var(--white-background)' }}
                        labelStyle={{ color: 'var(--white-background)' }}
                        formatter={(v, name) => [`${(v as number).toFixed(1)}%`, name as string]}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="sabana" name="La Sabana" fill="var(--sabana-dark-navy)" radius={[4, 4, 0, 0]} />
                      {!ole.unico_oferente && (
                        <Bar dataKey="pais" name="El país" fill="var(--sabana-light-blue)" radius={[4, 4, 0, 0]} />
                      )}
                    </BarChart>
                  </ResponsiveContainer>

                  <p className="text-xs mt-4 leading-relaxed" style={{ color: 'var(--sabana-black-50)' }}>
                    <b>Cómo leerlo:</b> el OLE mide el <b>Ingreso Base de Cotización</b> a seguridad
                    social, no el salario declarado. Los independientes cotizan sobre el 40% de sus
                    honorarios, así que en programas con mucho ejercicio independiente la cifra
                    <b> queda por debajo</b> del ingreso real. La mediana se estima por interpolación
                    dentro de la banda que la contiene, porque la fuente publica rangos y no pesos.
                    Corte {ole.anio_corte}, convertido a pesos con el SMMLV de ese año.
                  </p>
                </div>
              )}

              {/* Comparativa por subgrupo CNO */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                  Comparativa salarial entre grupos ocupacionales
                </h3>
                <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                  Mediana mensual (COP) por gran grupo profesional. En{' '}
                  <span style={{ color: 'var(--sabana-dark-navy)', fontWeight: 600 }}>azul oscuro</span>,
                  el del programa seleccionado.
                </p>
                <ResponsiveContainer width="100%" height={Math.max(260, comparativa.length * 46)}>
                  <BarChart data={comparativa} layout="vertical" margin={{ left: 8, right: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      type="number"
                      tickFormatter={(v) => fmtM(v as number)}
                      tick={{ fontSize: 12, fill: 'var(--sabana-dark-navy)' }}
                    />
                    <YAxis
                      dataKey="nombre"
                      type="category"
                      width={260}
                      tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      itemStyle={{ color: 'var(--white-background)' }}
                      labelStyle={{ color: 'var(--white-background)' }}
                      formatter={(value) => [fmtCOP(value as number), 'Mediana']}
                    />
                    <Bar dataKey="mediana" radius={[0, 4, 4, 0]}>
                      {comparativa.map((it) => (
                        <Cell
                          key={it.codigo}
                          fill={it.es_actual ? 'var(--sabana-dark-navy)' : 'var(--sabana-light-blue)'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Rangos SPE */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                  Rangos salariales en vacantes activas — SPE Colombia
                </h3>
                <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                  Participación de vacantes por rango y su variación anual. Resaltado con borde, el
                  rango donde cae la mediana de <b>{analisis.programa}</b>.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {analisis.spe_rangos
                    .filter((r) => r.min_cop !== null)
                    .map((r) => {
                      const enRango =
                        analisis.rango_spe != null && r.rango === analisis.rango_spe.rango;
                      const sube = r.variacion >= 0;
                      return (
                        <div
                          key={r.rango}
                          className="rounded-lg px-3 py-2 border"
                          style={{
                            borderColor: enRango ? 'var(--sabana-dark-navy)' : 'var(--sabana-sky-blue)',
                            borderWidth: enRango ? 2 : 1,
                            background: enRango ? 'var(--sabana-sky-blue)' : 'transparent',
                          }}
                        >
                          <div className="flex justify-between items-baseline">
                            <span className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
                              {r.rango}
                            </span>
                            <span
                              className="text-xs font-semibold"
                              style={{ color: sube ? 'var(--trend-up)' : 'var(--trend-down)' }}
                            >
                              {sube ? '↑' : '↓'} {Math.abs(r.variacion).toFixed(1)}% a/a
                            </span>
                          </div>
                          <span className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                            {r.participacion.toFixed(1)}% de las vacantes
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* Salario por nivel educativo — dentro del grupo ocupacional del programa */}
              {analisis.nivel_educativo.length > 0 && (
                <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                  <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    Salario según nivel educativo
                  </h3>
                  <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                    {analisis.nivel_educativo_nacional ? (
                      <>
                        Mediana mensual (COP) por máximo nivel alcanzado. Para{' '}
                        <b>{analisis.programa}</b> no hay muestra suficiente dentro de su
                        ocupación, así que se muestra la <b>escalera nacional</b>.
                      </>
                    ) : (
                      <>
                        Mediana mensual (COP) por máximo nivel alcanzado, <b>dentro de{' '}
                        {analisis.cno?.nombre}</b> — así el efecto del posgrado se lee ya
                        controlando por la ocupación de {analisis.programa}.
                      </>
                    )}{' '}
                    En <span style={{ color: 'var(--sabana-dark-navy)', fontWeight: 600 }}>azul oscuro</span>,
                    los niveles universitario y de posgrado.
                  </p>
                  <ResponsiveContainer width="100%" height={Math.max(220, analisis.nivel_educativo.length * 44)}>
                    <BarChart data={analisis.nivel_educativo} layout="vertical" margin={{ left: 8, right: 40 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        type="number"
                        tickFormatter={(v) => fmtM(v as number)}
                        tick={{ fontSize: 12, fill: 'var(--sabana-dark-navy)' }}
                      />
                      <YAxis
                        dataKey="nombre"
                        type="category"
                        width={170}
                        tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        itemStyle={{ color: 'var(--white-background)' }}
                        labelStyle={{ color: 'var(--white-background)' }}
                        formatter={(value, _name, item) => [
                          `${fmtCOP(value as number)}  (n=${item?.payload?.n ?? '—'})`,
                          'Mediana',
                        ]}
                      />
                      <Bar dataKey="mediana" radius={[0, 4, 4, 0]}>
                        {analisis.nivel_educativo.map((nv) => (
                          <Cell
                            key={nv.codigo}
                            fill={nv.orden >= 10 ? 'var(--sabana-dark-navy)' : 'var(--sabana-light-blue)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Sección "Posgrados de La Sabana con mayores ingresos" retirada
                  del frontend a pedido de Alumni (en discusión interna). El
                  backend (GET /ole/posgrados) sigue intacto por si se retoma. */}

              {/* Nota metodológica */}
              <p className="text-xs leading-relaxed" style={{ color: 'var(--sabana-black-50)' }}>
                <b>Metodología:</b> la GEIH del DANE registra el ingreso laboral por
                ocupación (código CNO-2020), no por programa. Cada programa se asocia al
                gran grupo ocupacional de 2 dígitos que agrupa a sus egresados
                profesionales, por lo que programas afines comparten referencia salarial.
                Los rangos SPE reflejan lo ofertado en vacantes activas y no dependen del
                programa. El salario por nivel educativo (variable P3042 de la GEIH) se
                calcula dentro del grupo ocupacional del programa; si su muestra es
                insuficiente, cae a la escalera nacional. Solo se muestran niveles con al
                menos 30 casos.{' '}
                {ole?.sabana && (
                  <>
                    El bloque del <b>OLE</b> no se promedia con lo anterior: mide a los graduados
                    del programa (Ingreso Base de Cotización, rangos de SMMLV, corte{' '}
                    {ole.anio_corte}) mientras que la GEIH mide a quien ejerce la ocupación. Son
                    universos distintos y se leen por separado.{' '}
                  </>
                )}
                {meta?.mediana_nacional
                  ? `Mediana laboral nacional de referencia: ${fmtCOP(meta.mediana_nacional)}.`
                  : ''}
              </p>
            </>
          )}
        </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Análisis Salarial"
        pageContent={
          analisis && analisis.kpis && analisis.cno
            ? `Salarios por programa (COP), fuente GEIH DANE + SPE. Programa: ${analisis.programa}. ` +
              `Ocupación de referencia CNO ${analisis.cno.codigo} (${analisis.cno.nombre}). ` +
              `Mediana mensual ${fmtCOP(analisis.kpis.mediana)}, P25 ${fmtCOP(analisis.kpis.p25)}, ` +
              `P75 ${fmtCOP(analisis.kpis.p75)}, N=${analisis.kpis.n}. ` +
              `Rango SPE de la mediana: ${analisis.rango_spe?.rango ?? 'N/A'}.` +
              (ole?.sabana
                ? ` OLE MinEducación ${ole.anio_corte}: ${ole.sabana.graduados} egresados de La Sabana ` +
                  `cotizantes, mediana estimada ${medianaOle(ole.sabana)}` +
                  (ole.sabana.mediana_cop ? ` (${fmtCOP(ole.sabana.mediana_cop)})` : '') +
                  `, ${ole.sabana.pct_sobre_4smmlv}% sobre 4 SMMLV` +
                  (ole.brecha_vs_nacional_pct != null
                    ? `, ${ole.brecha_vs_nacional_pct > 0 ? '+' : ''}${ole.brecha_vs_nacional_pct}% frente al mismo programa en el país.`
                    : ole.unico_oferente
                      ? '. La Sabana es la única institución que ofrece este programa.'
                      : '.')
                : '')
            : 'Página de análisis salarial por programa académico (GEIH DANE + SPE Colombia).'
        }
      />
    </>
  );
}
