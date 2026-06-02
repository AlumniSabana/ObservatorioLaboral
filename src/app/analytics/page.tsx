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
  Legend,
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

const COLORS = [
  '#0076ba', // sabana-light-blue
  '#003366', // sabana-navy
  '#4A90E2',
  '#F39C12',
  '#E74C3C',
  '#9B59B6',
  '#1ABC9C',
  '#34495E',
  '#D35400',
  '#27AE60',
];

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${BACKEND_URL}/analytics`);
      if (!response.ok) throw new Error('Error al cargar análisis');
      const data = await response.json();
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <PageLayout title="Análisis de Empleos">
        <div className="flex items-center justify-center py-12">
          <p className="text-lg text-zinc-600">⏳ Cargando análisis...</p>
        </div>
      </PageLayout>
    );
  }

  if (error || !analytics) {
    return (
      <PageLayout title="Análisis de Empleos">
        <div className="bg-red-100 rounded-lg p-6">
          <p className="text-red-700">❌ {error || 'No se pudieron cargar los análisis'}</p>
          <button
            onClick={fetchAnalytics}
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
      <PageLayout title="Análisis de Empleos">
        <div className="space-y-8">
          {/* Header Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              className="rounded-lg p-6 text-white"
              style={{ backgroundColor: 'var(--sabana-light-blue)' }}
            >
              <p className="text-sm opacity-90">Total de Ofertas</p>
              <p className="text-4xl font-bold mt-2">{analytics.total_jobs}</p>
            </div>
            <div
              className="rounded-lg p-6 text-white"
              style={{ backgroundColor: 'var(--sabana-navy)' }}
            >
              <p className="text-sm opacity-90">Con Información de Salario</p>
              <p className="text-4xl font-bold mt-2">{analytics.jobs_with_salary}</p>
            </div>
          </div>

          {/* 1. Cargos más demandados */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>
              💼 Cargos Más Demandados
            </h3>
            <p className="text-sm text-zinc-600 mb-4">
              Los 20 títulos de empleos con mayor frecuencia en el mercado laboral
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart
                data={analytics.job_titles}
                margin={{ top: 20, right: 30, left: 0, bottom: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="title"
                  angle={-45}
                  textAnchor="end"
                  height={120}
                  interval={0}
                  tick={{ fontSize: 12 }}
                />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="var(--sabana-light-blue)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 2. Sectores con mayor actividad */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>
              🏢 Sectores con Mayor Actividad de Contratación
            </h3>
            <p className="text-sm text-zinc-600 mb-4">
              Distribución de empleos por categoría laboral
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={analytics.categories} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="category" type="category" width={150} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="var(--sabana-navy)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 3. Modalidades de trabajo prevalentes */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>
              ⏰ Modalidades de Trabajo Prevalentes
            </h3>
            <p className="text-sm text-zinc-600 mb-4">
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
                    label={({ type, count }) => `${type}: ${count}`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="count"
                  >
                    {analytics.contract_types.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col justify-center space-y-2">
                {analytics.contract_types.map((item, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <span className="text-sm">
                      <strong>{item.type || 'Desconocido'}</strong>: {item.count} ofertas
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 4. Rangos salariales */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>
              💰 Rangos Salariales por Frecuencia
            </h3>
            <p className="text-sm text-zinc-600 mb-4">
              Distribución de empleos en diferentes franjas salariales anuales
            </p>
            {analytics.salary_ranges.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={analytics.salary_ranges}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="range"
                    tick={{ fontSize: 12 }}
                    angle={-45}
                    textAnchor="end"
                    height={100}
                  />
                  <YAxis />
                  <Tooltip />
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
            <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>
              🏆 Empresas con Mayor Actividad de Contratación
            </h3>
            <p className="text-sm text-zinc-600 mb-4">
              Las 15 empresas con más ofertas de empleo activas
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart
                data={analytics.companies}
                margin={{ top: 20, right: 30, left: 0, bottom: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="company"
                  angle={-45}
                  textAnchor="end"
                  height={120}
                  interval={0}
                  tick={{ fontSize: 12 }}
                />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="var(--sabana-navy)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 6. Universidades demandadas (Programs) */}
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-xl font-semibold mb-4" style={{ color: 'var(--sabana-dark-navy)' }}>
              🎓 Programas Académicos Relacionados con Mayor Demanda
            </h3>
            <p className="text-sm text-zinc-600 mb-4">
              Distribución de ofertas por programa académico de origen
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={analytics.programas} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis
                  dataKey="programa"
                  type="category"
                  width={200}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip />
                <Bar dataKey="count" fill="var(--sabana-light-blue)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg p-4 border-l-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
              <p className="text-sm text-zinc-600">Promedio de Empleos por Título</p>
              <p className="text-2xl font-bold mt-2">
                {analytics.job_titles.length > 0
                  ? (
                      analytics.total_jobs /
                      analytics.job_titles.reduce((sum, j) => sum + j.count, 0) *
                      analytics.job_titles.length
                    ).toFixed(1)
                  : 'N/A'}
              </p>
            </div>
            <div className="rounded-lg p-4 border-l-4" style={{ borderColor: 'var(--sabana-navy)' }}>
              <p className="text-sm text-zinc-600">Número de Sectores</p>
              <p className="text-2xl font-bold mt-2">{analytics.categories.length}</p>
            </div>
            <div className="rounded-lg p-4 border-l-4" style={{ borderColor: '#1ABC9C' }}>
              <p className="text-sm text-zinc-600">Empresas Únicas</p>
              <p className="text-2xl font-bold mt-2">{analytics.companies.length}</p>
            </div>
          </div>

          {/* Refresh Button */}
          <div className="flex justify-center">
            <button
              onClick={fetchAnalytics}
              className="px-6 py-2 rounded-lg font-semibold transition-colors"
              style={{
                backgroundColor: 'var(--sabana-light-blue)',
                color: 'white',
              }}
            >
              🔄 Actualizar Análisis
            </button>
          </div>
        </div>
      </PageLayout>

      <FloatingChat
        pageTitle="Análisis de Empleos"
        pageContent="Dashboard de análisis de empleos con gráficos de cargos demandados, salarios, sectores, empresas, modalidades de trabajo y programas académicos relacionados."
      />
    </>
  );
}
