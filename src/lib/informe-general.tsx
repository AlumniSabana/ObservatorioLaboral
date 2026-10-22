'use client';

/**
 * <InformeGeneral /> — botón de Administrador que descarga un PDF con el panorama
 * COMPLETO del Observatorio: tendencias de cargos, demanda actual y competencias
 * y tecnologías más demandadas. Es el hermano del PDF de Perfil ocupacional
 * (src/lib/perfil-pdf.ts, misma paleta y estilo) pero sin filtrar por programa.
 *
 * Todo se arma en el navegador con jsPDF a partir de los mismos GET públicos
 * que alimentan las páginas (no hay endpoint nuevo): usa TODAS las fuentes que
 * ofrece /tendencias/opciones, igual que la vista por defecto de Tendencias.
 * Quien lo monta lo envuelve en <SoloAdmin>.
 */

import { useState } from 'react';
import { jsPDF } from 'jspdf';
import { Spinner } from '@/lib/spinner';
import { NAVY, NAVY2, LIGHT, SKY, GRAY, rgb, cortar, fechaHoy } from '@/lib/perfil-pdf';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Item { label: string; count: number }
interface Skill { nombre: string; indice: number }
interface Termino { tendencia: string; score_tendencia: number }

async function get<T>(ruta: string): Promise<T> {
  const r = await fetch(`${BACKEND_URL}${ruta}`);
  if (!r.ok) throw new Error(`${ruta.split('?')[0]}: HTTP ${r.status}`);
  return r.json();
}

async function descargar() {
  const opc = await get<{ fuentes: { pais: string }[] }>('/tendencias/opciones');
  const paises = encodeURIComponent(opc.fuentes.map((f) => f.pais).join(','));
  const base = `programa=TODOS&seniority=TODOS&paises=${paises}`;
  const [tend, dem, comp, tec] = await Promise.all([
    get<{ meta: { total_terminos: number; crecientes: number; estables: number; decrecientes: number }; terminos: Record<string, Termino> }>(`/tendencias?dimension=cargo&${base}`),
    get<{ cargos: Item[]; sectores: Item[]; empresas: Item[]; programas: Item[]; meta: { total: number } }>(`/tendencias/demanda?${base}&escolaridad=TODOS&top=10`),
    get<{ items: Skill[] }>(`/skills-demandadas?tipo=competencia&${base}&top=15`),
    get<{ items: Skill[] }>(`/skills-demandadas?tipo=tecnologia&${base}&top=15`),
  ]);

  const ordenados = (dir: string) =>
    Object.entries(tend.terminos).filter(([, t]) => t.tendencia === dir)
      .sort((a, b) => b[1].score_tendencia - a[1].score_tendencia).slice(0, 10)
      .map(([label, t]) => ({ label, count: Math.round(t.score_tendencia * 100) }));

  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const W = 210, M = 14, CW = W - M * 2;
  let y = 38;
  const fill = (h: string) => doc.setFillColor(...rgb(h));
  const ink = (h: string) => doc.setTextColor(...rgb(h));
  const ensure = (h: number) => { if (y + h > 285) { doc.addPage(); y = M; } };

  fill(NAVY); doc.rect(0, 0, W, 30, 'F'); ink('#ffffff');
  doc.setFont('helvetica', 'bold'); doc.setFontSize(17); doc.text('Informe general del mercado laboral', M, 14);
  doc.setFont('helvetica', 'normal'); doc.setFontSize(10);
  doc.text('Observatorio Laboral — Dirección de Alumni · Universidad de La Sabana', M, 21);
  doc.setFontSize(9); doc.text(fechaHoy(), W - M, 14, { align: 'right' });

  const titulo = (t: string) => {
    ensure(12); y += 2; ink(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(11);
    doc.text(t, M, y); y += 2; fill(SKY); doc.rect(M, y, CW, 0.6, 'F'); y += 5;
  };
  // Lista de barras; `max` fija la escala (100 en índices, el mayor conteo en demanda).
  const barras = (t: string, items: Item[], x: number, w: number, hex: string, max: number, y0: number) => {
    let yy = y0; ink(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(9); doc.text(t, x, yy); yy += 5;
    doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5);
    if (!items.length) { ink(GRAY); doc.text('Sin datos suficientes.', x, yy); yy += 6; }
    items.forEach((it) => {
      ink(NAVY2); doc.text(cortar(it.label, 34), x, yy);
      fill(SKY); doc.rect(x, yy + 1.4, w, 1.6, 'F');
      fill(hex); doc.rect(x, yy + 1.4, (w * it.count) / (max || 1), 1.6, 'F');
      yy += 6.5;
    });
    return yy;
  };
  const colW = (CW - 8) / 2, X2 = M + colW + 8;
  const par = (izq: [string, Item[], string, number], der: [string, Item[], string, number]) => {
    ensure(10 + Math.max(izq[1].length, der[1].length, 1) * 6.5);
    const y0 = y;
    y = Math.max(barras(izq[0], izq[1], M, colW, izq[2], izq[3], y0), barras(der[0], der[1], X2, colW, der[2], der[3], y0)) + 4;
  };
  const max = (a: Item[]) => Math.max(...a.map((i) => i.count), 1);

  ink(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(9);
  doc.text('Consolidado de todas las fuentes y todos los programas académicos.', M, y); y += 4;

  titulo('Resumen');
  const kpis: [string, string][] = [
    ['VACANTES ANALIZADAS', dem.meta.total.toLocaleString('es-CO')],
    ['CARGOS CON TENDENCIA', String(tend.meta.total_terminos)],
    ['CRECIENTES / ESTABLES', `${tend.meta.crecientes} / ${tend.meta.estables}`],
    ['DECRECIENTES', String(tend.meta.decrecientes)],
  ];
  const cw = (CW - 9) / 4;
  kpis.forEach(([l, v], i) => {
    const x = M + i * (cw + 3);
    fill(SKY); doc.rect(x, y, cw, 20, 'F'); fill(NAVY); doc.rect(x, y, 1.5, 20, 'F');
    ink(GRAY); doc.setFont('helvetica', 'bold'); doc.setFontSize(6.5); doc.text(l, x + 4, y + 6);
    ink(NAVY); doc.setFontSize(13); doc.text(v, x + 4, y + 15);
  });
  y += 26;

  titulo('Tendencias de cargos (índice de tendencia 0–100)');
  const cre = ordenados('creciente'), dec = ordenados('decreciente');
  par(['Cargos crecientes', cre, NAVY, 100], ['Cargos decrecientes', dec, LIGHT, 100]);

  titulo('Demanda actual (vacantes)');
  par(['Cargos más demandados', dem.cargos, NAVY, max(dem.cargos)], ['Sectores', dem.sectores, LIGHT, max(dem.sectores)]);
  par(['Empresas que más contratan', dem.empresas, NAVY, max(dem.empresas)], ['Programas con más demanda', dem.programas, LIGHT, max(dem.programas)]);

  titulo('Competencias y tecnologías más demandadas (índice 0–100)');
  const sk = (a: Skill[]) => a.map((s) => ({ label: s.nombre, count: s.indice }));
  par(['Competencias', sk(comp.items), NAVY, 100], ['Tecnologías', sk(tec.items), LIGHT, 100]);

  const n = doc.getNumberOfPages();
  for (let i = 1; i <= n; i++) {
    doc.setPage(i); ink(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(7);
    doc.text('Fuentes: Adzuna · Google Jobs · LinkedIn · O*NET', M, 292);
    doc.text(`${i}/${n}`, W - M, 292, { align: 'right' });
  }
  doc.save(`Informe_General_Observatorio_${new Date().toISOString().slice(0, 10)}.pdf`);
}

export function InformeGeneral() {
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generar = async () => {
    setCargando(true);
    setError(null);
    try {
      await descargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el informe');
    } finally {
      setCargando(false);
    }
  };

  return (
    <section className="rounded-lg border p-4 mb-4 text-sm" style={{ borderColor: 'var(--sabana-light-blue)' }}>
      <h3 className="font-bold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>Informe general (PDF)</h3>
      <p className="text-xs mb-3" style={{ color: 'var(--sabana-black-50)' }}>
        Descarga el panorama completo —tendencias, demanda actual, competencias y tecnologías— de todas las
        fuentes y todos los programas, sin discriminar por carrera. Puede tardar un minuto.
      </p>
      <button
        onClick={generar}
        disabled={cargando}
        className="px-5 py-2 rounded-lg font-semibold text-white disabled:opacity-50"
        style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: cargando ? 'wait' : 'pointer' }}
      >
        {cargando ? 'Generando…' : 'Descargar informe general'}
      </button>
      {cargando && <Spinner size="sm" compact label="Reuniendo datos de todas las fuentes..." />}
      {error && <div className="rounded-lg p-3 mt-3 bg-red-50 text-red-700 text-xs">{error}</div>}
    </section>
  );
}
