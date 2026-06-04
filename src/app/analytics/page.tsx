'use client';

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

interface Analytics {
  total_jobs: number;
  jobs_with_salary: number;
  job_titles: Array<{ title: string; count: number }>;
  categories: Array<{ category: string; count: number }>;
  contract_types: Array<{ type: string; count: number }>;
  salary_ranges: Array<{ range: string; count: number }>;
  companies: Array<{ company: string; count: number }>;
  programas: Array<{ programa: string; count: number }>;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Función para obtener colores de la paleta de La Sabana
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

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics(false);
  }, []);

  const fetchAnalytics = async (borrar: boolean = false) => {
    setLoading(true);
    setError(null);

    const url = new URL(`${BACKEND_URL}/scrape`);
    url.searchParams.append('borrar', borrar.toString());
    
    try {
      // Primero hacemos el scrape (actualiza los datos)
      const scrapeResponse = await fetch(url, {
        method: 'POST',
      });
      
      if (!scrapeResponse.ok) {
        console.warn("Error en scrape, pero continuamos con analytics...");
      }

      // Luego cargamos los nuevos analytics
      const analyticsResponse = await fetch(`${BACKEND_URL}/analytics`);
      if (!analyticsResponse.ok) throw new Error('Error al cargar análisis');
      
      const data = await analyticsResponse.json();
      setAnalytics(data);
      
      alert("✅ Datos actualizados correctamente desde Adzuna");
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <PageLayout title="Análisis de mercado (Adzuna)">
        <div className="flex items-center justify-center py-12">
          <p className="text-lg text-zinc-600 font-bold">⏳ Cargando análisis...</p>
        </div>
      </PageLayout>
    );
  }

  if (error || !analytics) {
    return (
      <PageLayout title="Análisis de mercado (Adzuna)">
        <div className="bg-red-100 rounded-lg p-6">
          <p className="text-red-700">❌ {error || 'No se pudieron cargar los análisis'}</p>
          <button
            onClick={() => fetchAnalytics(false)}
            className="mt-4 px-4 py-2 rounded-lg font-semibold transition-colors"
            style={{ backgroundColor: 'var(--sabana-light-blue)', color: 'white' }}
          >
            Reintentar
          </button>
        </div>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout title="Análisis de mercado (Adzuna)">
        <div className="space-y-8">
          {/* Header Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              className="rounded-lg p-6 text-white"
              style={{ backgroundColor: 'var(--sabana-light-blue)' }}
            >
              <p className="text-sm opacity-90 font-bold" style = {{color: 'var(--sabana-dark-navy)'}}>Total de Ofertas</p>
              <p className="text-4xl font-bold mt-2 font-bold" style = {{color: 'var(--sabana-dark-navy)'}}>{analytics.total_jobs}</p>
            </div>
            <div
              className="rounded-lg p-6 text-white"
              style={{ backgroundColor: 'var(--sabana-navy)' }}
            >
              <p className="text-sm opacity-90 font-bold">Con Información de Salario</p>
              <p className="text-4xl font-bold mt-2 font-bold" >{analytics.jobs_with_salary}</p>
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
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'var(--white-background)', borderColor: 'var(--sabana-dark-navy)', borderRadius: '8px' }}
                  itemStyle={{ color: 'var(--white-background)' }}
                />
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
                <YAxis dataKey="category" type="category" width={150} tick={{ fontSize: 12, fill: 'var(--white-background)' }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'var(--white-background)', borderColor: 'var(--sabana-dark-navy)', borderRadius: '8px' }}
                  itemStyle={{ color: 'var(--white-background)' }}
                />
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
                    contentStyle={{ 
                      backgroundColor: 'var(--sabana-dark-navy)', 
                      color: 'var(--white-background)', 
                      borderColor: 'var(--sabana-dark-navy)', 
                      borderRadius: '8px',
                      fontWeight: 'bold', 
                    }}
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
                    tick={{ fontSize: 12, fill: 'var(--white-background)' }}
                    angle={-45}
                    textAnchor="end"
                    height={100}
                  />
                  <YAxis 
                  tick={{ fontSize: 12, fill: 'var(--white-background)' }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'var(--white-background)', borderColor: 'var(--sabana-dark-navy)', borderRadius: '8px' }}
                    itemStyle={{ color: 'var(--white-background)' }}
                  />
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
                  tick={{ fontSize: 12, fill: 'var(--white-background)' }}
                  tickMargin={10}
                />
                <XAxis 
                  tick={{ fontSize: 12, fill: 'var(--white-background)' }}
                  type="number"
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'var(--white-background)', borderColor: 'var(--sabana-dark-navy)', borderRadius: '8px' }}
                  itemStyle={{ color: 'var(--white-background)' }}
                  formatter={(value) => [`${value}`, 'Vacantes']}
                />
                <Bar dataKey="count" fill="var(--sabana-light-blue)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 6. Universidades demandadas (Programs) */}
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
                <YAxis
                  dataKey="programa"
                  type="category"
                  width={300}
                  tick={{ fontSize: 11, fill: 'var(--white-background)' }}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'var(--white-background)', borderColor: 'var(--sabana-dark-navy)', borderRadius: '8px' }}
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

          {/* Refresh Button */}
          <div className="flex justify-center">
            <button
              onClick={() => fetchAnalytics(true)}
              className="px-6 py-2 rounded-lg font-semibold transition-colors"
              style={{
                backgroundColor: 'var(--sabana-navy)',
                color: 'white',
                cursor: 'pointer',
              }}
            >
              🔄 Actualizar Análisis
            </button>
          </div>
        </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Análisis de mercado (Adzuna)"
        pageContent="Dashboard de Análisis de mercado (Adzuna) con gráficos de cargos demandados, salarios, sectores, empresas, modalidades de trabajo y programas académicos relacionados. Estas vacantes son extraídas del mercado de ESTADOS UNIDOS a través de la API de Adzuna, proporcionando insights sobre tendencias laborales actuales."
      />
    </>
  );
}
