'use client';

/**
 * Página "Perfil ocupacional" (ruta '/perfil-ocupacional').
 *
 * Reúne en una sola vista el perfil de un PROGRAMA académico: salario, skills,
 * seniority que más conviene, tendencia de demanda y perfil O*NET (RIASEC / job
 * zone). Consume UN endpoint agregador: GET /perfil-ocupacional?programa=...
 * Además ofrece descargar un reporte PDF con lo más importante.
 *
 * Sigue el mismo patrón y estilo que src/app/salaries/page.tsx.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { generarPerfilPDF } from '@/lib/perfil-pdf';
import { Spinner } from '@/lib/spinner';
import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  Cell,
  LineChart,
  Line,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};

// ---------------------------------------------------------------------------
// Tipos (espejo del JSON del backend)
// ---------------------------------------------------------------------------
interface Kpis { mediana: number; media: number; p25: number; p75: number; p10: number; p90: number; n: number; }
interface NivelEdu { codigo: string; nombre: string; orden: number; mediana: number; p25: number; p75: number; n: number; }
interface RangoSpe { rango: string; min_cop: number | null; max_cop: number | null; participacion: number; variacion: number; }
interface Skill { nombre: string; descripcion: string; peso: number; }
interface AtributoCno { nombre: string; descripcion: string | null; nivel: number; especifica: boolean; }
interface Riasec { codigo: string; nombre: string; valor: number; }
interface NivelSen { codigo: string; etiqueta: string; demanda_pct: number; n: number; salario_indice: number | null; n_con_salario: number; }
interface PuntoSerie { periodo: string; indice: number; }

interface Perfil {
  programa: string;
  encontrado: boolean;
  onet: {
    codigo_soc: string | null;
    ocupacion_ref: string | null;
    descripcion: string | null;
    job_zone: { nivel: number; etiqueta: string; descripcion: string } | null;
    riasec: Riasec[];
    bright_outlook: boolean;
  };
  salario: {
    cno: { codigo: string; nombre: string } | null;
    kpis: Kpis | null;
    vs_nacional_pct: number | null;
    mediana_nacional: number | null;
    rango_spe: RangoSpe | null;
    spe_rangos: RangoSpe[];
    nivel_educativo: NivelEdu[];
    nivel_educativo_nacional: boolean;
    nivel_top_paga: { nombre: string; mediana: number; incremento_vs_pregrado_pct: number | null } | null;
  };
  skills: { competencias: Skill[]; tecnologias: Skill[] };
  cno_sena: {
    sin_datos: boolean;
    ocupacion?: { codigo: string; nombre: string | null } | null;
    habilidades?: AtributoCno[];
    conocimientos?: AtributoCno[];
  };
  seniority: {
    niveles: NivelSen[];
    recomendado: { codigo: string; etiqueta: string; motivo: string } | null;
    confianza: string;
    n_total_etiquetadas: number;
    n_total: number;
    fuente: string;
    nota_indice: string;
  };
  tendencia: { serie: PuntoSerie[]; direccion: string; variacion_pct: number | null; n_meses: number };
  sectores: { category: string; count: number }[];
  ciudades_colombia: { city: string; count: number }[];
  meta: { fuentes: string[] };
}

// ---------------------------------------------------------------------------
// Helpers de formato y presentación
// ---------------------------------------------------------------------------
const fmtCOP = (v: number) => '$' + v.toLocaleString('es-CO', { maximumFractionDigits: 0 });
const fmtM = (v: number) => `$${(v / 1e6).toFixed(1)}M`;

const TENDENCIA_UI: Record<string, { label: string; icono: string; color: string }> = {
  creciente: { label: 'Creciente', icono: '▲', color: 'var(--trend-up)' },
  estable: { label: 'Estable', icono: '▬', color: 'var(--trend-flat)' },
  decreciente: { label: 'Decreciente', icono: '▼', color: 'var(--trend-down)' },
  sin_datos: { label: 'Sin datos', icono: '–', color: 'var(--sabana-black-50)' },
};

export default function PerfilOcupacionalPage() {
  const [programas, setProgramas] = useState<string[]>([]);
  const [programa, setPrograma] = useState<string>('');
  const [data, setData] = useState<Perfil | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Lista de programas: se reutiliza el endpoint de salarios (mismos programas).
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/analytics/salarios`);
        if (!res.ok) throw new Error('No se pudo cargar la lista de programas');
        const d = await res.json();
        const lista: string[] = d.programas ?? [];
        setProgramas(lista);
        setPrograma(lista.includes('Ingeniería Informática') ? 'Ingeniería Informática' : lista[0] ?? '');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido');
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!programa) return;
    (async () => {
      setLoading(true);
      setError(null);
      // Limpia el perfil del programa anterior ANTES de pedir el nuevo: la
      // consulta tarda hasta ~10s, y sin esto la vista se quedaba mostrando el
      // perfil viejo todo ese tiempo sin ningún aviso de que estaba desactualizado.
      setData(null);
      try {
        const url = new URL(`${BACKEND_URL}/perfil-ocupacional`);
        url.searchParams.append('programa', programa);
        const res = await fetch(url);
        if (!res.ok) throw new Error('No se pudo cargar el perfil');
        setData(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido');
      } finally {
        setLoading(false);
      }
    })();
  }, [programa]);

  const kpis = data?.salario.kpis;
  const tend = data ? TENDENCIA_UI[data.tendencia.direccion] ?? TENDENCIA_UI.sin_datos : null;

  return (
    <>
      <PageLayout title="Perfil ocupacional">
        <div className="space-y-6">
          <div>
            <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
              Todo lo esencial de un programa en una vista: cuánto se gana, qué competencias
              pesan, qué nivel de experiencia conviene y hacia dónde va la demanda.
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--sabana-black-50)' }}>
              Fuentes: <b>O*NET</b> · <b>GEIH — DANE</b> · <b>SPE</b> · <b>Adzuna</b> · <b>Google Jobs</b>.
            </p>
          </div>

          {/* Selector de programa + botón PDF */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 shadow flex flex-col md:flex-row md:items-end gap-4">
            <div className="flex-1">
              <label className="block text-sm font-semibold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                Programa académico
              </label>
              <select
                value={programa}
                onChange={(e) => setPrograma(e.target.value)}
                className="w-full md:w-96 rounded-lg border px-3 py-2 text-sm"
                style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' }}
              >
                {programas.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <button
              onClick={() => data && data.encontrado && generarPerfilPDF(data)}
              disabled={!data || !data.encontrado}
              className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
              style={{ backgroundColor: 'var(--sabana-dark-navy)' }}
            >
              Descargar reporte PDF
            </button>
          </div>

          {error && <div className="rounded-lg p-4 bg-red-50 text-red-700 text-sm">{error}</div>}
          {loading && <Spinner label={`Cargando perfil de ${programa}...`} />}

          {data && data.encontrado && kpis && tend && (
            <>
              {/* Ocupación de referencia */}
              {data.onet.ocupacion_ref && (
                <p className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>
                  Ocupación de referencia O*NET: <b style={{ color: 'var(--sabana-dark-navy)' }}>{data.onet.ocupacion_ref}</b>
                  {data.salario.cno ? ` · Grupo ocupacional CNO ${data.salario.cno.codigo} (${data.salario.cno.nombre})` : ''}
                  {data.onet.bright_outlook ? ' · Perspectiva de crecimiento' : ''}
                </p>
              )}

              {/* ── SECCIÓN 0 · VEREDICTO ─────────────────────────────────── */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-lg p-4 border-l-4 bg-white dark:bg-zinc-800 shadow" style={{ borderColor: 'var(--sabana-dark-navy)' }}>
                  <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Salario mediano</p>
                  <p className="text-xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>{fmtCOP(kpis.mediana)}</p>
                  {data.salario.vs_nacional_pct !== null && (
                    <p className="text-xs mt-1" style={{ color: data.salario.vs_nacional_pct >= 0 ? 'var(--trend-up)' : 'var(--trend-down)' }}>
                      {data.salario.vs_nacional_pct >= 0 ? '+' : ''}{data.salario.vs_nacional_pct}% vs. promedio nacional
                    </p>
                  )}
                </div>
                <div className="rounded-lg p-4 border-l-4 bg-white dark:bg-zinc-800 shadow" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                  <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Demanda</p>
                  <p className="text-xl font-bold mt-1" style={{ color: tend.color }}>{tend.icono} {tend.label}</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
                    {data.tendencia.variacion_pct !== null ? `${data.tendencia.variacion_pct > 0 ? '+' : ''}${data.tendencia.variacion_pct}% en el periodo` : 'tendencia observada'}
                  </p>
                </div>
                <div className="rounded-lg p-4 border-l-4 bg-white dark:bg-zinc-800 shadow" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                  <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Seniority que conviene</p>
                  <p className="text-lg font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {data.seniority.recomendado ? data.seniority.recomendado.etiqueta : 'Señal limitada'}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
                    {data.seniority.confianza === 'alta' ? 'confianza alta' : `muestra limitada (n=${data.seniority.n_total_etiquetadas})`}
                  </p>
                </div>
                <div className="rounded-lg p-4 border-l-4 bg-white dark:bg-zinc-800 shadow" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                  <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Competencia clave</p>
                  <p className="text-lg font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {data.skills.competencias[0]?.nombre ?? '—'}
                  </p>
                  {data.skills.competencias[0] && (
                    <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>importancia {Math.round(data.skills.competencias[0].peso)}/100</p>
                  )}
                </div>
              </div>

              {/* ── SECCIÓN 1 · SALARIO + NIVEL EDUCATIVO ─────────────────── */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>Salario en Colombia (COP)</h3>
                <div className="mb-6">
                  <div className="rounded-lg p-4 border-l-4 max-w-xs" style={{ borderColor: 'var(--sabana-dark-navy)' }}>
                    <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Mediana mensual</p>
                    <p className="text-lg font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>{fmtCOP(kpis.mediana)}</p>
                  </div>
                </div>

                {data.salario.nivel_educativo.length > 0 && (
                  <>
                    <p className="text-sm mb-2" style={{ color: 'var(--sabana-black-50)' }}>
                      Salario por nivel educativo{data.salario.nivel_top_paga?.incremento_vs_pregrado_pct != null && (
                        <> — <b style={{ color: 'var(--sabana-dark-navy)' }}>{data.salario.nivel_top_paga.nombre}</b> paga
                        {' '}<b style={{ color: 'var(--trend-up)' }}>+{data.salario.nivel_top_paga.incremento_vs_pregrado_pct}%</b> sobre el pregrado</>
                      )}.
                    </p>
                    <ResponsiveContainer width="100%" height={Math.max(200, data.salario.nivel_educativo.length * 44)}>
                      <BarChart data={data.salario.nivel_educativo} layout="vertical" margin={{ left: 8, right: 40 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" tickFormatter={(v) => fmtM(v as number)} tick={{ fontSize: 12, fill: 'var(--sabana-dark-navy)' }} />
                        <YAxis dataKey="nombre" type="category" width={170} tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                        <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} labelStyle={{ color: 'var(--white-background)' }} formatter={(v) => [fmtCOP(v as number), 'Mediana']} />
                        <Bar dataKey="mediana" radius={[0, 4, 4, 0]}>
                          {data.salario.nivel_educativo.map((nv) => (
                            <Cell key={nv.codigo} fill={nv.orden >= 10 ? 'var(--sabana-dark-navy)' : 'var(--sabana-light-blue)'} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </>
                )}
              </div>

              {/* ── SECCIÓN 2 · SKILLS ─────────────────────────────────────── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <SkillsCard titulo="Competencias clave" skills={data.skills.competencias} color="var(--sabana-navy)" />
                <SkillsCard titulo="Tecnologías y herramientas" skills={data.skills.tecnologias} color="var(--sabana-light-blue)" />
              </div>

              {/* ── SECCIÓN 2b · CNO 2025 (SENA) ───────────────────────────── */}
              {!data.cno_sena.sin_datos && (
                <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                  <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    Perfil oficial colombiano — CNO 2025 (SENA)
                  </h3>
                  <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                    Lo que la <b style={{ color: 'var(--sabana-dark-navy)' }}>Clasificación Nacional de Ocupaciones</b> exige
                    para {data.cno_sena.ocupacion?.nombre
                      ? <b style={{ color: 'var(--sabana-dark-navy)' }}>{data.cno_sena.ocupacion.nombre}</b>
                      : 'esta ocupación'}
                    {data.cno_sena.ocupacion?.codigo && <> (código {data.cno_sena.ocupacion.codigo})</>}.
                    {' '}Es la referencia <b>normativa del país</b>, no una medición del mercado.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <CnoLista titulo="Habilidades" items={data.cno_sena.habilidades ?? []} color="var(--sabana-navy)" />
                    <CnoLista titulo="Conocimientos" items={data.cno_sena.conocimientos ?? []} color="var(--sabana-light-blue)" />
                  </div>
                </div>
              )}

              {/* ── SECCIÓN 3 · TENDENCIA ──────────────────────────────────── */}
              {data.tendencia.serie.length > 1 && (
                <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                  <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Tendencia de demanda</h3>
                  <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                    Evolución del índice de demanda del programa. <b>Tendencia observada, no es una proyección.</b>
                    {' '}Señal: <span style={{ color: tend.color, fontWeight: 600 }}>{tend.icono} {tend.label}</span>.
                  </p>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={data.tendencia.serie} margin={{ left: 8, right: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="periodo" tick={{ fontSize: 10, fill: 'var(--sabana-dark-navy)' }} tickFormatter={(v) => String(v).slice(0, 7)} />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} labelStyle={{ color: 'var(--white-background)' }} formatter={(v) => [(v as number).toFixed(2), 'Índice']} />
                      <Line type="monotone" dataKey="indice" stroke="var(--sabana-navy)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* ── SECCIÓN 4 · SENIORITY ÓPTIMO ───────────────────────────── */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>¿Qué seniority conviene más?</h3>
                <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                  Balance entre <b>acceso</b> (cuántas vacantes hay) y <b>pago</b> por nivel de experiencia.
                  Índice de pago relativo entre niveles (promedio = 100). Fuente: {data.seniority.fuente}.
                </p>
                {data.seniority.confianza === 'limitada' && (
                  <div className="rounded-lg px-3 py-2 mb-4 text-xs" style={{ background: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}>
                    Señal limitada: solo {data.seniority.n_total_etiquetadas} vacantes declaran nivel en el título. Tómese como orientación, no como conclusión.
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {data.seniority.niveles.map((nv) => {
                    const rec = data.seniority.recomendado?.codigo === nv.codigo;
                    return (
                      <div key={nv.codigo} className="rounded-lg p-3 border" style={{ borderColor: rec ? 'var(--sabana-dark-navy)' : 'var(--sabana-sky-blue)', borderWidth: rec ? 2 : 1, background: rec ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                        <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>{nv.etiqueta}</p>
                        <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>Demanda: <b style={{ color: 'var(--sabana-dark-navy)' }}>{nv.demanda_pct}%</b></p>
                        <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Pago: <b style={{ color: 'var(--sabana-dark-navy)' }}>{nv.salario_indice != null ? `${nv.salario_indice} / 100` : '—'}</b></p>
                      </div>
                    );
                  })}
                </div>
                {data.seniority.recomendado && (
                  <p className="text-sm mt-4" style={{ color: 'var(--sabana-dark-navy)' }}>
                    <b>Recomendado: {data.seniority.recomendado.etiqueta}.</b> {data.seniority.recomendado.motivo}
                  </p>
                )}
              </div>

              {/* ── SECCIÓN 5 · PERFIL O*NET (RIASEC + Job Zone) ───────────── */}
              {(data.onet.riasec.length > 0 || data.onet.job_zone || data.onet.descripcion) && (
                <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Perfil de intereses (RIASEC)</h3>
                    <p className="text-sm mb-2" style={{ color: 'var(--sabana-black-50)' }}>Afinidad vocacional de la ocupación (modelo de Holland, Holland, J. L. (1997). Making vocational choices: A theory of vocational personalities and work environments (3rd ed.). Psychological Assessment Resources.).</p>
                    {data.onet.riasec.length > 0 ? (
                      <ResponsiveContainer width="100%" height={280}>
                        <RadarChart data={data.onet.riasec} outerRadius="72%">
                          <PolarGrid stroke="var(--sabana-sky-blue)" />
                          <PolarAngleAxis dataKey="nombre" tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                          <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: 'var(--sabana-black-50)' }} />
                          <Radar dataKey="valor" stroke="var(--sabana-navy)" fill="var(--sabana-navy)" fillOpacity={0.25} />
                          <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} labelStyle={{ color: 'var(--white-background)' }} formatter={(v) => [(v as number).toFixed(0), 'Afinidad']} />
                        </RadarChart>
                      </ResponsiveContainer>
                    ) : <p className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>Sin datos de intereses.</p>}
                    <a
                      href="https://personality.co/es/test/start?t=career&gclid=CjwKCAjw4dDTBhAqEiwAkHYmSvzxU3dHMp7MLg2PrXsAo2m86jpxoprK-5MmCXELR3t3t1IR8UC_nhoC6doQAvD_BwE&gclid=CjwKCAjw4dDTBhAqEiwAkHYmSvzxU3dHMp7MLg2PrXsAo2m86jpxoprK-5MmCXELR3t3t1IR8UC_nhoC6doQAvD_BwE&utm_source=google&utm_medium=cpc&utm_campaign=23301191485&utm_content=187856935574&utm_term=test+de+inter%C3%A9s+profesional+holland&matchtype=b&device=c&gad_source=1&gad_campaignid=23301191485&gbraid=0AAAABCDT4dz_AJ2DcVsdg4z10eimSvk6X"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 inline-block text-sm font-semibold underline"
                      style={{ color: 'var(--sabana-navy)' }}
                    >
                      Conoce tu perfil
                    </a>
                  </div>
                  <div className="space-y-4">
                    {data.onet.job_zone && (
                      <div>
                        <h4 className="text-sm font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Nivel de preparación (Job Zone {data.onet.job_zone.nivel}/5)</h4>
                        <span className="inline-block rounded px-2 py-1 text-xs font-semibold text-white" style={{ background: 'var(--sabana-dark-navy)' }}>{data.onet.job_zone.etiqueta}</span>
                        <p className="text-sm mt-2" style={{ color: 'var(--sabana-black-50)' }}>{data.onet.job_zone.descripcion}</p>
                      </div>
                    )}
                    {data.onet.descripcion && (
                      <div className="rounded-lg p-4" style={{ background: 'var(--sabana-sky-blue)' }}>
                        <h4 className="text-sm font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Sobre la ocupación</h4>
                        <p className="text-sm" style={{ color: 'var(--sabana-dark-navy)' }}>{data.onet.descripcion}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ── SECCIÓN 6 · SECTORES Y CIUDADES QUE CONTRATAN ──────────── */}
              {(data.sectores.length > 0 || data.ciudades_colombia.length > 0) && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {data.sectores.length > 0 && (
                    <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                      <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Sectores que contratan</h3>
                      <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>Vacantes por sector (referencia internacional, Adzuna).</p>
                      <ResponsiveContainer width="100%" height={Math.max(200, data.sectores.length * 42)}>
                        <BarChart data={data.sectores} layout="vertical" margin={{ left: 8, right: 30 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--sabana-dark-navy)' }} />
                          <YAxis dataKey="category" type="category" width={180} tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                          <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} formatter={(v) => [`${v}`, 'Vacantes']} />
                          <Bar dataKey="count" fill="var(--sabana-light-blue)" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                  {data.ciudades_colombia.length > 0 && (
                    <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
                      <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Dónde se contrata en Colombia</h3>
                      <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>Vacantes por ciudad (Google Jobs + LinkedIn, Colombia).</p>
                      <ResponsiveContainer width="100%" height={Math.max(200, data.ciudades_colombia.length * 42)}>
                        <BarChart data={data.ciudades_colombia} layout="vertical" margin={{ left: 8, right: 30 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--sabana-dark-navy)' }} />
                          <YAxis dataKey="city" type="category" width={180} tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                          <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} formatter={(v) => [`${v}`, 'Vacantes']} />
                          <Bar dataKey="count" fill="var(--sabana-navy)" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              )}

              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                Fuentes: {data.meta.fuentes.join(' · ')}. Salario y educación: Colombia (GEIH/SPE). Skills y perfil vocacional:
                O*NET (normativo). Seniority y sectores: Adzuna (mercado internacional). Ciudades: Google Jobs (Colombia).
              </p>
            </>
          )}

          {data && !data.encontrado && !loading && (
            <div className="rounded-lg p-4 text-sm" style={{ background: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}>
              No hay datos suficientes para <b>{programa}</b> todavía.
            </div>
          )}
        </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Perfil Ocupacional"
        pageContent={
          data && data.encontrado && kpis
            ? `Perfil ocupacional de ${data.programa}. Salario mediano ${fmtCOP(kpis.mediana)} ` +
              `(${data.salario.vs_nacional_pct ?? 0}% vs nacional). Tendencia: ${data.tendencia.direccion}. ` +
              `Seniority recomendado: ${data.seniority.recomendado?.etiqueta ?? 'señal limitada'}. ` +
              `Top competencias: ${data.skills.competencias.slice(0, 3).map((c) => c.nombre).join(', ')}. ` +
              `Ocupación O*NET: ${data.onet.ocupacion_ref ?? '—'}.`
            : 'Página de perfil ocupacional por programa académico (salario, skills, seniority, tendencia y perfil O*NET).'
        }
      />
    </>
  );
}

// Lista de atributos del CNO. Sin barras a propósito: el CNO no pondera, solo
// declara qué exige la ocupación. Se marca lo que es propio de la ocupación
// frente a lo que se hereda del grupo ocupacional superior.
function CnoLista({ titulo, items, color }: { titulo: string; items: AtributoCno[]; color: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--sabana-dark-navy)' }}>{titulo}</h4>
      <ul className="space-y-2">
        {items.map((it) => (
          <li key={it.nombre} className="flex items-start gap-2">
            <span className="mt-1.5 shrink-0 rounded-full" style={{ width: 6, height: 6, background: color }} />
            <div>
              <span className="text-sm" style={{ color: 'var(--sabana-dark-navy)' }}>{it.nombre}</span>
              {!it.especifica && (
                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded"
                  style={{ color: 'var(--sabana-black-50)', border: '1px solid var(--sabana-black-20, #ddd)' }}
                  title="Requisito del grupo ocupacional, no exclusivo de esta ocupación">
                  del grupo
                </span>
              )}
              {it.descripcion && (
                <p className="text-xs mt-0.5" style={{ color: 'var(--sabana-black-50)' }}>{it.descripcion}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Tarjeta reutilizable de skills (competencias o tecnologías) con barras de peso.
function SkillsCard({ titulo, skills, color }: { titulo: string; skills: Skill[]; color: string }) {
  if (skills.length === 0) return null;
  return (
    <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
      <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>{titulo}</h3>
      <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>Importancia según O*NET (0–100).</p>
      <ResponsiveContainer width="100%" height={Math.max(260, skills.length * 34)}>
        <BarChart data={skills} layout="vertical" margin={{ left: 8, right: 30 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12, fill: 'var(--sabana-dark-navy)' }} />
          <YAxis dataKey="nombre" type="category" width={175} tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            itemStyle={{ color: 'var(--white-background)' }}
            labelStyle={{ color: 'var(--white-background)' }}
            formatter={(v, _n, item) => [`${Math.round(v as number)}/100`, item?.payload?.descripcion ? String(item.payload.descripcion).slice(0, 60) : 'Peso']}
          />
          <Bar dataKey="peso" fill={color} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
