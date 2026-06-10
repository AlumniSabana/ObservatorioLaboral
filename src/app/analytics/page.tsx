'use client';

/**
 * Dashboard "Análisis de mercado" (ruta '/analytics').
 *
 * Es la ÚNICA página que muestra datos REALES traídos del backend. Permite elegir
 * la FUENTE de los datos con un combo box (ver objeto FUENTES más abajo). CADA
 * FUENTE TIENE SU PROPIO DASHBOARD porque cada una entrega campos distintos:
 *   - 'adzuna'      -> <AdzunaDashboard>  : EE.UU., incluye salario y sectores.
 *   - 'google_jobs' -> <GoogleDashboard>  : Colombia, incluye ciudades y
 *                                            plataforma de origen; NO trae salario
 *                                            ni sector (Google Jobs no los provee).
 *
 * Flujo:
 *   - Al cargar la página o cambiar de fuente -> loadAnalytics() hace
 *     GET /analytics?fuente=... (solo LEE lo que ya hay en la BD).
 *   - El botón "Actualizar Análisis" -> fetchAnalytics() hace
 *     POST /scrape?fuente=...&borrar=true (RECOLECTA datos nuevos) y luego recarga.
 *
 * Los gráficos se dibujan con la librería recharts.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

// ---------------------------------------------------------------------------
// Tipos de datos que devuelve el backend (uno por fuente, porque difieren)
// ---------------------------------------------------------------------------

// GET /analytics?fuente=adzuna  (tabla `vacantes`)
interface AdzunaAnalytics {
  total_jobs: number;                                          // total de vacantes
  jobs_with_salary: number;                                    // cuántas traen salario
  job_titles: Array<{ title: string; count: number }>;        // cargos más demandados
  categories: Array<{ category: string; count: number }>;     // sectores
  contract_types: Array<{ type: string; count: number }>;     // modalidades (full/part time)
  salary_ranges: Array<{ range: string; count: number }>;     // distribución salarial
  companies: Array<{ company: string; count: number }>;       // empresas con más ofertas
  programas: Array<{ programa: string; count: number }>;      // programas académicos
}

// GET /analytics?fuente=google_jobs  (tabla `vacantes_google`)
interface GoogleAnalytics {
  total_jobs: number;                                          // total de vacantes
  remote_count: number;                                        // cuántas son remotas
  job_titles: Array<{ title: string; count: number }>;        // cargos más demandados
  companies: Array<{ company: string; count: number }>;       // empresas con más ofertas
  contract_types: Array<{ type: string; count: number }>;     // modalidad/jornada
  cities: Array<{ city: string; count: number }>;             // ciudades con más vacantes
  sources: Array<{ source: string; count: number }>;          // plataforma de origen (via)
  programas: Array<{ programa: string; count: number }>;      // programas académicos
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

type Fuente = 'adzuna' | 'google_jobs';

// Metadatos de cada fuente de datos disponible
const FUENTES: Record<Fuente, {
  label: string;
  title: string;
  chatContent: string;
}> = {
  adzuna: {
    label: 'Adzuna — Estados Unidos',
    title: 'Análisis de mercado — Adzuna (Estados Unidos)',
    chatContent:
      'Dashboard de Análisis de mercado con gráficos de cargos demandados, salarios, sectores, empresas, modalidades de trabajo y programas académicos relacionados. Estas vacantes son extraídas del mercado de ESTADOS UNIDOS a través de la API de Adzuna, proporcionando insights sobre tendencias laborales actuales.',
  },
  google_jobs: {
    label: 'Google Jobs — Colombia',
    title: 'Análisis de mercado — Google Jobs (Colombia)',
    chatContent:
      'Dashboard de Análisis de mercado con gráficos de cargos demandados, ciudades, empresas, modalidades de trabajo, plataformas de origen y programas académicos relacionados. Estas vacantes son extraídas del mercado de COLOMBIA a través de Google Jobs (SerpApi). Nota: esta fuente no entrega salario ni sector de forma estructurada.',
  },
};

// Devuelve un color de la paleta de La Sabana según un índice, rotando de forma
// cíclica. Se usa para pintar los segmentos de los gráficos (ej. el pie chart).
const getSabanaColor = (index: number) => {
  const sabanaColors = [
    'var(--sabana-dark-navy)',    // #002058
    'var(--sabana-navy)',          // #003870
    'var(--sabana-light-blue)',    // #93aac9
    'var(--sabana-sky-blue)',      // #d9e1ef
    'var(--sabana-cream)',         // #f7e6d9
    'var(--sabana-black-70)',      // #4d4d4d
    'var(--sabana-black-50)',      // #808080
    'var(--sabana-black-30)',      // #b3b3b3
  ];
  return sabanaColors[index % sabanaColors.length];
};

// Construye un resumen en TEXTO de los datos reales que se están visualizando,
// para dárselo como contexto al asistente de chat. Así Claude puede citar cifras
// concretas (y calcular porcentajes/comparaciones) en lugar de hablar en términos
// genéricos. Son los mismos valores agregados que pintan las gráficas.
function buildChatContext(
  fuente: Fuente,
  analytics: AdzunaAnalytics | GoogleAnalytics,
): string {
  // Formatea una lista "- nombre: conteo" a partir de los datos de un gráfico.
  const fmtList = <T extends { count: number }>(
    items: T[],
    label: (it: T) => string,
  ) => items.map((it) => `  - ${label(it) || 'Desconocido'}: ${it.count}`).join('\n');

  const intro = [
    FUENTES[fuente].chatContent,
    '',
    'DATOS ACTUALES EN PANTALLA (son valores AGREGADOS — los mismos que muestran las gráficas —, no la lista completa de vacantes):',
  ];

  if (fuente === 'adzuna') {
    const a = analytics as AdzunaAnalytics;
    return [
      ...intro,
      `Total de ofertas: ${a.total_jobs}`,
      `Ofertas con información de salario: ${a.jobs_with_salary}`,
      '',
      'Cargos más demandados (cargo: número de ofertas):',
      fmtList(a.job_titles, (it) => it.title),
      '',
      'Sectores con mayor actividad:',
      fmtList(a.categories, (it) => it.category),
      '',
      'Modalidades de trabajo:',
      fmtList(a.contract_types, (it) => it.type),
      '',
      'Rangos salariales (franja: número de ofertas):',
      fmtList(a.salary_ranges, (it) => it.range),
      '',
      'Empresas con más ofertas:',
      fmtList(a.companies, (it) => it.company),
      '',
      'Programas académicos relacionados:',
      fmtList(a.programas, (it) => it.programa),
    ].join('\n');
  }

  const g = analytics as GoogleAnalytics;
  return [
    ...intro,
    `Total de ofertas: ${g.total_jobs}`,
    `Vacantes remotas: ${g.remote_count}`,
    '',
    'Cargos más demandados (cargo: número de ofertas):',
    fmtList(g.job_titles, (it) => it.title),
    '',
    'Ciudades con más vacantes:',
    fmtList(g.cities, (it) => it.city),
    '',
    'Modalidades de trabajo:',
    fmtList(g.contract_types, (it) => it.type),
    '',
    'Plataformas de origen (portal: número de ofertas):',
    fmtList(g.sources, (it) => it.source),
    '',
    'Empresas con más ofertas:',
    fmtList(g.companies, (it) => it.company),
    '',
    'Programas académicos relacionados:',
    fmtList(g.programas, (it) => it.programa),
  ].join('\n');
}

// Estilos comunes de tooltips/ejes para no repetirlos en cada gráfico.
const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};
const AXIS_TICK = { fontSize: 12, fill: 'var(--white-background)' };

export default function AnalyticsPage() {
  // El tipo del estado depende de la fuente; en el render lo "estrechamos" por fuente.
  const [analytics, setAnalytics] = useState<AdzunaAnalytics | GoogleAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fuente, setFuente] = useState<Fuente>('adzuna');

  // Solo consulta los analytics ya almacenados para la fuente indicada
  const loadAnalytics = async (fuenteSel: Fuente) => {
    setLoading(true);
    setError(null);

    try {
      const url = new URL(`${BACKEND_URL}/analytics`);
      url.searchParams.append('fuente', fuenteSel);

      const analyticsResponse = await fetch(url);
      if (!analyticsResponse.ok) throw new Error('Error al cargar análisis');

      const data = await analyticsResponse.json();
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  // Re-ejecuta la recolección (scrape) de la fuente actual y recarga los datos
  const fetchAnalytics = async (borrar: boolean = false) => {
    setLoading(true);
    setError(null);

    const url = new URL(`${BACKEND_URL}/scrape`);
    url.searchParams.append('borrar', borrar.toString());
    url.searchParams.append('fuente', fuente);

    try {
      // Primero hacemos el scrape (actualiza los datos de la fuente seleccionada)
      const scrapeResponse = await fetch(url, {
        method: 'POST',
      });

      if (!scrapeResponse.ok) {
        console.warn("Error en scrape, pero continuamos con analytics...");
      }

      // Luego cargamos los nuevos analytics de esa fuente
      const analyticsUrl = new URL(`${BACKEND_URL}/analytics`);
      analyticsUrl.searchParams.append('fuente', fuente);

      const analyticsResponse = await fetch(analyticsUrl);
      if (!analyticsResponse.ok) throw new Error('Error al cargar análisis');

      const data = await analyticsResponse.json();
      setAnalytics(data);

      alert(`✅ Datos actualizados correctamente desde ${FUENTES[fuente].label}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  // Carga los analytics desde el backend cada vez que cambia la fuente seleccionada
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAnalytics(fuente);
  }, [fuente]);

  // Combo box para elegir la fuente de los datos (siempre visible)
  const SourceSelector = (
    <div className="mb-6 flex flex-col sm:flex-row sm:items-center gap-2">
      <label
        htmlFor="fuente-select"
        className="text-sm font-bold"
        style={{ color: 'var(--sabana-dark-navy)' }}
      >
        Fuente de datos:
      </label>
      <select
        id="fuente-select"
        value={fuente}
        // Activamos "loading" de inmediato para que el render intermedio (con la
        // fuente nueva pero los datos viejos aún en estado) NO intente pintar un
        // dashboard con datos de la otra forma. loadAnalytics() recargará al instante.
        onChange={(e) => {
          setLoading(true);
          setFuente(e.target.value as Fuente);
        }}
        className="rounded-lg px-4 py-2 font-semibold border cursor-pointer"
        style={{
          backgroundColor: 'var(--sabana-sky-blue)',
          color: 'var(--sabana-dark-navy)',
          borderColor: 'var(--sabana-light-blue)',
        }}
      >
        {(Object.keys(FUENTES) as Fuente[]).map((key) => (
          <option key={key} value={key}>
            {FUENTES[key].label}
          </option>
        ))}
      </select>
    </div>
  );

  if (loading) {
    return (
      <PageLayout title={FUENTES[fuente].title}>
        {SourceSelector}
        <div className="flex items-center justify-center py-12">
          <p className="text-lg text-zinc-600 font-bold">⏳ Cargando análisis...</p>
        </div>
      </PageLayout>
    );
  }

  if (error || !analytics) {
    return (
      <PageLayout title={FUENTES[fuente].title}>
        {SourceSelector}
        <div className="bg-red-100 rounded-lg p-6">
          <p className="text-red-700">❌ {error || 'No se pudieron cargar los análisis'}</p>
          <button
            onClick={() => loadAnalytics(fuente)}
            className="mt-4 px-4 py-2 rounded-lg font-semibold transition-colors"
            style={{ backgroundColor: 'var(--sabana-light-blue)', color: 'white' }}
          >
            Reintentar
          </button>
        </div>
      </PageLayout>
    );
  }

  // Sin datos para la fuente seleccionada (ej. Google Jobs aún sin recolectar)
  if (analytics.total_jobs === 0) {
    return (
      <PageLayout title={FUENTES[fuente].title}>
        {SourceSelector}
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-8 shadow text-center space-y-4">
          <p className="text-lg font-bold" style={{ color: 'var(--sabana-light-blue)' }}>
            Aún no hay vacantes recolectadas para {FUENTES[fuente].label}.
          </p>
          <p className="text-sm text-zinc-500">
            Usa el botón para recolectar los datos de esta fuente.
          </p>
          <button
            onClick={() => fetchAnalytics(true)}
            className="px-6 py-2 rounded-lg font-semibold transition-colors"
            style={{ backgroundColor: 'var(--sabana-navy)', color: 'white', cursor: 'pointer' }}
          >
            🔄 Recolectar datos
          </button>
        </div>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout title={FUENTES[fuente].title}>
        {SourceSelector}
        {/* Cada fuente renderiza su propio dashboard con los campos que sí tiene */}
        {fuente === 'adzuna' ? (
          <AdzunaDashboard
            analytics={analytics as AdzunaAnalytics}
            onRefresh={() => fetchAnalytics(true)}
          />
        ) : (
          <GoogleDashboard
            analytics={analytics as GoogleAnalytics}
            onRefresh={() => fetchAnalytics(true)}
          />
        )}
      </PageLayout>

      <FloatingChat
        pageTitle={FUENTES[fuente].title}
        pageContent={buildChatContext(fuente, analytics)}
      />
    </>
  );
}

// ===========================================================================
// Dashboard de ADZUNA (Estados Unidos)
// Incluye salario y sectores porque la API de Adzuna sí los entrega.
// ===========================================================================
function AdzunaDashboard({
  analytics,
  onRefresh,
}: {
  analytics: AdzunaAnalytics;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-8">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          className="rounded-lg p-6 text-white"
          style={{ backgroundColor: 'var(--sabana-light-blue)' }}
        >
          <p className="text-sm opacity-90 font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>Total de Ofertas</p>
          <p className="text-4xl font-bold mt-2 font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>{analytics.total_jobs}</p>
        </div>
        <div
          className="rounded-lg p-6 text-white"
          style={{ backgroundColor: 'var(--sabana-navy)' }}
        >
          <p className="text-sm opacity-90 font-bold">Con Información de Salario</p>
          <p className="text-4xl font-bold mt-2 font-bold">{analytics.jobs_with_salary}</p>
        </div>
      </div>

      {/* 1. Cargos más demandados */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          💼 Cargos Más Demandados
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Los 20 títulos de empleos con mayor frecuencia en el mercado laboral
        </p>
        <ResponsiveContainer width="100%" height={600}>
          <BarChart
            data={analytics.job_titles}
            layout="vertical"
            margin={{ top: 0, right: 30, left: -80, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis
              dataKey="title"
              type="category"
              width={400}
              tick={{ fontSize: 10, fill: 'var(--white-background)' }}
            />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 2. Sectores con mayor actividad */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          🏢 Sectores con Mayor Actividad de Contratación
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución de empleos por categoría laboral
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={analytics.categories} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="category" type="category" width={150} tick={AXIS_TICK} />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 3. Modalidades de trabajo prevalente */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          ⏰ Modalidades de Trabajo Prevalentes
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución de tipos de contrato (tiempo completo, parcial, etc.)
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={analytics.contract_types}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry) => `${entry.type}: ${entry.count}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
                nameKey="type"
              >
                {analytics.contract_types.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getSabanaColor(index)} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name, props) => {
                  return [`${value} ofertas`, props.payload.type || 'Desconocido'];
                }}
                contentStyle={{ ...TOOLTIP_STYLE, fontWeight: 'bold' }}
                itemStyle={{ color: 'var(--white-background)' }}
                labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col justify-center space-y-2">
            {analytics.contract_types.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: getSabanaColor(index) }}
                />
                <span className="text-sm" style={{ color: 'var(--white-background)' }}>
                  <strong>{item.type || 'Desconocido'}</strong>: {item.count} ofertas
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        /* Asegurar que los labels del pie chart sean blancos */
        :global(.recharts-pie-label-text) {
          fill: white !important;
          font-weight: bold !important;
          font-size: 15px !important;
        }
      `}</style>

      {/* 4. Rangos salariales */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          💰 Rangos Salariales por Frecuencia
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución de empleos en diferentes franjas salariales anuales
        </p>
        {analytics.salary_ranges.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={analytics.salary_ranges}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="range"
                tick={AXIS_TICK}
                angle={-45}
                textAnchor="end"
                height={100}
              />
              <YAxis tick={AXIS_TICK} />
              <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="var(--sabana-light-blue)"
                dot={{ fill: 'var(--sabana-light-blue)' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-center text-zinc-500 py-8">
            No hay datos salariales disponibles
          </p>
        )}
      </div>

      {/* 5. Empresas líderes por sector */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          🏆 Empresas con Mayor Actividad de Contratación
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Las 15 empresas con más ofertas de empleo activas
        </p>
        <ResponsiveContainer width="100%" height={500}>
          <BarChart
            data={analytics.companies}
            layout="vertical"
            margin={{ top: 15, right: 30, left: -30, bottom: 15 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <YAxis
              dataKey="company"
              type="category"
              textAnchor="end"
              width={300}
              interval={0}
              tick={AXIS_TICK}
              tickMargin={10}
            />
            <XAxis tick={AXIS_TICK} type="number" />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              itemStyle={{ color: 'var(--white-background)' }}
              formatter={(value) => [`${value}`, 'Vacantes']}
            />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 6. Programas académicos relacionados */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          🎓 Programas Académicos Relacionados con Mayor Demanda
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución de ofertas por programa académico relacionado
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={analytics.programas} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="programa" type="category" width={300} tick={{ fontSize: 11, fill: 'var(--white-background)' }} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              itemStyle={{ color: 'var(--white-background)' }}
              formatter={(value) => [`${value}`, 'Vacantes']}
            />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg p-4 border-l-4" style={{ fontWeight: 'bold', borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm text-zinc-600" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            Promedio de Empleos por Título
          </p>
          <p className="text-2xl font-bold mt-2" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            {analytics.job_titles.length > 0
              ? (
                  analytics.total_jobs /
                  analytics.job_titles.reduce((sum, j) => sum + j.count, 0) *
                  analytics.job_titles.length
                ).toFixed(1)
              : 'N/A'}
          </p>
        </div>
        <div className="rounded-lg p-4 border-l-4" style={{ fontWeight: 'bold', borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm text-zinc-600" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            Número de Sectores
          </p>
          <p className="text-2xl font-bold mt-2" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            {analytics.categories.length}
          </p>
        </div>
        <div className="rounded-lg p-4 border-l-4" style={{ fontWeight: 'bold', borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm text-zinc-600" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            Empresas Únicas
          </p>
          <p className="text-2xl font-bold mt-2" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            {analytics.companies.length}
          </p>
        </div>
      </div>

      <RefreshButton onRefresh={onRefresh} />
    </div>
  );
}

// ===========================================================================
// Dashboard de GOOGLE JOBS (Colombia)
// Solo muestra dimensiones que esta fuente sí provee (cargos, ciudades,
// empresas, modalidad, plataforma de origen, programa). No hay salario ni
// sector: eso llegará en la fase de extracción con IA sobre las descripciones.
// ===========================================================================
function GoogleDashboard({
  analytics,
  onRefresh,
}: {
  analytics: GoogleAnalytics;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-8">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg p-6 text-white" style={{ backgroundColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm opacity-90 font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>Total de Ofertas</p>
          <p className="text-4xl font-bold mt-2" style={{ color: 'var(--sabana-dark-navy)' }}>{analytics.total_jobs}</p>
        </div>
        <div className="rounded-lg p-6 text-white" style={{ backgroundColor: 'var(--sabana-navy)' }}>
          <p className="text-sm opacity-90 font-bold">Vacantes Remotas</p>
          <p className="text-4xl font-bold mt-2">{analytics.remote_count}</p>
        </div>
      </div>

      {/* Aviso sobre los datos que esta fuente no entrega */}
      <div
        className="rounded-lg p-4 border-l-4 text-sm"
        style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' }}
      >
        ℹ️ Google Jobs no entrega salario ni sector de forma estructurada. Esas
        métricas (y seniority, competencias y experiencia) se obtendrán en una fase
        posterior, extrayéndolas de las descripciones con IA.
      </div>

      {/* 1. Cargos más demandados */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          💼 Cargos Más Demandados
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Los 20 títulos de empleos con mayor frecuencia
        </p>
        <ResponsiveContainer width="100%" height={600}>
          <BarChart data={analytics.job_titles} layout="vertical" margin={{ top: 0, right: 30, left: -80, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="title" type="category" width={400} tick={{ fontSize: 10, fill: 'var(--white-background)' }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 2. Ciudades con más vacantes */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          📍 Ciudades con Más Vacantes
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución geográfica de las ofertas en Colombia
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={analytics.cities} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="city" type="category" width={180} tick={AXIS_TICK} />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} formatter={(value) => [`${value}`, 'Vacantes']} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 3. Modalidades de trabajo */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          ⏰ Modalidades de Trabajo
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución por tipo de jornada
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={analytics.contract_types}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry) => `${entry.type}: ${entry.count}`}
                outerRadius={80}
                dataKey="count"
                nameKey="type"
              >
                {analytics.contract_types.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getSabanaColor(index)} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name, props) => [`${value} ofertas`, props.payload.type || 'Desconocido']}
                contentStyle={{ ...TOOLTIP_STYLE, fontWeight: 'bold' }}
                itemStyle={{ color: 'var(--white-background)' }}
                labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col justify-center space-y-2">
            {analytics.contract_types.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getSabanaColor(index) }} />
                <span className="text-sm" style={{ color: 'var(--white-background)' }}>
                  <strong>{item.type || 'No especificado'}</strong>: {item.count} ofertas
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        :global(.recharts-pie-label-text) {
          fill: white !important;
          font-weight: bold !important;
          font-size: 15px !important;
        }
      `}</style>

      {/* 4. Plataformas de origen (via) */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          🌐 Plataformas de Origen
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          En qué portales aparecen publicadas las vacantes (LinkedIn, Computrabajo, etc.)
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={analytics.sources} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="source" type="category" width={180} tick={AXIS_TICK} />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} formatter={(value) => [`${value}`, 'Vacantes']} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 5. Empresas con más ofertas */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          🏆 Empresas con Mayor Actividad de Contratación
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Las 15 empresas con más ofertas de empleo activas
        </p>
        <ResponsiveContainer width="100%" height={500}>
          <BarChart data={analytics.companies} layout="vertical" margin={{ top: 15, right: 30, left: -30, bottom: 15 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <YAxis dataKey="company" type="category" textAnchor="end" width={300} interval={0} tick={AXIS_TICK} tickMargin={10} />
            <XAxis tick={AXIS_TICK} type="number" />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} formatter={(value) => [`${value}`, 'Vacantes']} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 6. Programas académicos relacionados */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-light-blue)' }}>
          🎓 Programas Académicos Relacionados con Mayor Demanda
        </h3>
        <p className="text-sm text-zinc-600 mb-4" style={{ color: 'var(--white-background)' }}>
          Distribución de ofertas por programa académico relacionado
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={analytics.programas} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="programa" type="category" width={300} tick={{ fontSize: 11, fill: 'var(--white-background)' }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} formatter={(value) => [`${value}`, 'Vacantes']} />
            <Bar dataKey="count" fill="var(--sabana-light-blue)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg p-4 border-l-4" style={{ fontWeight: 'bold', borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>Ciudades Distintas</p>
          <p className="text-2xl font-bold mt-2" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            {analytics.cities.length}
          </p>
        </div>
        <div className="rounded-lg p-4 border-l-4" style={{ fontWeight: 'bold', borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>Plataformas de Origen</p>
          <p className="text-2xl font-bold mt-2" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            {analytics.sources.length}
          </p>
        </div>
        <div className="rounded-lg p-4 border-l-4" style={{ fontWeight: 'bold', borderColor: 'var(--sabana-light-blue)' }}>
          <p className="text-sm" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>Empresas Únicas</p>
          <p className="text-2xl font-bold mt-2" style={{ fontWeight: 'bold', color: 'var(--sabana-dark-navy)' }}>
            {analytics.companies.length}
          </p>
        </div>
      </div>

      <RefreshButton onRefresh={onRefresh} />
    </div>
  );
}

// Botón de recolección/actualización, compartido por ambos dashboards.
function RefreshButton({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="flex justify-center">
      <button
        onClick={onRefresh}
        className="px-6 py-2 rounded-lg font-semibold transition-colors"
        style={{ backgroundColor: 'var(--sabana-navy)', color: 'white', cursor: 'pointer' }}
      >
        🔄 Actualizar Análisis
      </button>
    </div>
  );
}
