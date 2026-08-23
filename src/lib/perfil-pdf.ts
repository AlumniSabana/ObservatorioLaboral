/**
 * perfil-pdf.ts — genera el reporte PDF del Perfil Ocupacional (client-side).
 *
 * Se dibuja PROGRAMÁTICAMENTE con jsPDF a partir del JSON del perfil (no se
 * rasteriza el DOM): produce un PDF nítido, ligero y fiable, y ya tenemos todos
 * los números. El sitio es estático (output: 'export'), así que todo ocurre en el
 * navegador del usuario; el archivo se descarga localmente, no se envía a nadie.
 *
 * Contiene lo más importante que se lleva quien analiza el trabajo: veredicto
 * (salario, tendencia, seniority, competencia clave), salario y nivel que más
 * paga, top competencias y tecnologías, seniority recomendado y perfil O*NET.
 */

import { jsPDF } from 'jspdf';

// Test vocacional externo enlazado bajo RIASEC, igual que en la página web
// (src/app/perfil-ocupacional/page.tsx) — mismo destino en ambos lugares.
const LINK_TEST_PERFIL =
  'https://personality.co/es/test/start?t=career&gclid=CjwKCAjw4dDTBhAqEiwAkHYmSvzxU3dHMp7MLg2PrXsAo2m86jpxoprK-5MmCXELR3t3t1IR8UC_nhoC6doQAvD_BwE' +
  '&gclid=CjwKCAjw4dDTBhAqEiwAkHYmSvzxU3dHMp7MLg2PrXsAo2m86jpxoprK-5MmCXELR3t3t1IR8UC_nhoC6doQAvD_BwE' +
  '&utm_source=google&utm_medium=cpc&utm_campaign=23301191485&utm_content=187856935574' +
  '&utm_term=test+de+inter%C3%A9s+profesional+holland&matchtype=b&device=c&gad_source=1' +
  '&gad_campaignid=23301191485&gbraid=0AAAABCDT4dz_AJ2DcVsdg4z10eimSvk6X';

// Paleta Sabana en hex literal (el PDF no ve las CSS vars).
const NAVY = '#002058';
const NAVY2 = '#003870';
const LIGHT = '#93aac9';
const SKY = '#d9e1ef';
const CREAM = '#f7e6d9';
const GRAY = '#64748b';

// Estructura mínima que consume el PDF (subconjunto del Perfil del backend).
interface PerfilPDF {
  programa: string;
  onet: {
    ocupacion_ref: string | null;
    descripcion: string | null;
    job_zone: { nivel: number; etiqueta: string } | null;
    riasec: { nombre: string; valor: number }[];
    bright_outlook: boolean;
  };
  salario: {
    kpis: { mediana: number; p25: number; p75: number; p10: number; p90: number; n: number } | null;
    vs_nacional_pct: number | null;
    rango_spe: { rango: string } | null;
    nivel_top_paga: { nombre: string; incremento_vs_pregrado_pct: number | null } | null;
  };
  skills: { competencias: { nombre: string; peso: number }[]; tecnologias: { nombre: string; peso: number }[] };
  cno_sena?: {
    sin_datos: boolean;
    ocupacion?: { codigo: string; nombre: string | null } | null;
    habilidades?: { nombre: string }[];
    conocimientos?: { nombre: string }[];
  };
  seniority: {
    niveles: { etiqueta: string; demanda_pct: number; salario_indice: number | null; n: number }[];
    recomendado: { etiqueta: string; motivo: string } | null;
    confianza: string;
    n_total_etiquetadas: number;
  };
  tendencia: { direccion: string; variacion_pct: number | null };
  meta: { fuentes: string[] };
}

const fmtCOP = (v: number) => '$' + v.toLocaleString('es-CO', { maximumFractionDigits: 0 });
const TEND_ES: Record<string, string> = { creciente: 'Creciente', estable: 'Estable', decreciente: 'Decreciente', sin_datos: 'Sin datos' };

export function generarPerfilPDF(data: PerfilPDF): void {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const W = 210;
  const M = 14;                 // margen lateral
  const CW = W - M * 2;         // ancho útil
  let y = 0;

  // Salto de página cuando no cabe lo que sigue.
  const ensure = (h: number) => {
    if (y + h > 285) { doc.addPage(); y = M; }
  };

  const setFill = (hex: string) => { const [r, g, b] = rgb(hex); doc.setFillColor(r, g, b); };
  const setText = (hex: string) => { const [r, g, b] = rgb(hex); doc.setTextColor(r, g, b); };

  // ── Cabecera de marca ──────────────────────────────────────────────────
  setFill(NAVY);
  doc.rect(0, 0, W, 30, 'F');
  setText('#ffffff');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(17);
  doc.text('Perfil Ocupacional', M, 14);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.text('Observatorio Laboral — Dirección de Alumni · Universidad de La Sabana', M, 21);
  doc.setFontSize(9);
  doc.text(fechaHoy(), W - M, 14, { align: 'right' });
  y = 38;

  // Programa + ocupación de referencia
  setText(NAVY);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(15);
  doc.text(data.programa, M, y);
  y += 6;
  setText(GRAY);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  const ref = [
    data.onet.ocupacion_ref ? `Ocupación de referencia: ${data.onet.ocupacion_ref}` : null,
    data.onet.bright_outlook ? 'Perspectiva de crecimiento' : null,
  ].filter(Boolean).join('  ·  ');
  if (ref) { doc.text(ref, M, y); y += 6; } else { y += 2; }

  const k = data.salario.kpis;

  // ── Veredicto (4 tarjetas) ─────────────────────────────────────────────
  sectionTitle('Veredicto');
  const cardW = (CW - 9) / 4;
  const veredicto: [string, string, string][] = [
    ['SALARIO MEDIANO', k ? fmtCOP(k.mediana) : '—',
      data.salario.vs_nacional_pct != null ? `${data.salario.vs_nacional_pct >= 0 ? '+' : ''}${data.salario.vs_nacional_pct}% vs nacional` : ''],
    ['DEMANDA', TEND_ES[data.tendencia.direccion] ?? '—',
      data.tendencia.variacion_pct != null ? `${data.tendencia.variacion_pct > 0 ? '+' : ''}${data.tendencia.variacion_pct}%` : 'observada'],
    ['SENIORITY', data.seniority.recomendado?.etiqueta ?? 'Señal limitada',
      data.seniority.confianza === 'alta' ? 'confianza alta' : `n=${data.seniority.n_total_etiquetadas}`],
    ['COMPETENCIA CLAVE', data.skills.competencias[0]?.nombre ?? '—',
      data.skills.competencias[0] ? `${Math.round(data.skills.competencias[0].peso)}/100` : ''],
  ];
  ensure(26);
  veredicto.forEach(([label, val, sub], i) => {
    const x = M + i * (cardW + 3);
    setFill(SKY); doc.rect(x, y, cardW, 24, 'F');
    setFill(NAVY); doc.rect(x, y, 1.5, 24, 'F');
    setText(GRAY); doc.setFont('helvetica', 'bold'); doc.setFontSize(6.5);
    doc.text(label, x + 4, y + 5);
    setText(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(10);
    doc.text(cortar(val, 20), x + 4, y + 12);
    setText(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(7);
    if (sub) doc.text(cortar(sub, 24), x + 4, y + 19);
  });
  y += 30;

  // ── Salario ────────────────────────────────────────────────────────────
  if (k) {
    sectionTitle('Salario en Colombia (COP)');
    ensure(12);
    kvRow([
      ['Mediana mensual', fmtCOP(k.mediana)],
      ['Rango SPE de la mediana', data.salario.rango_spe?.rango ?? '—'],
    ]);
    if (data.salario.nivel_top_paga?.incremento_vs_pregrado_pct != null) {
      setText(NAVY2); doc.setFont('helvetica', 'normal'); doc.setFontSize(9);
      doc.text(`Nivel educativo que más paga: ${data.salario.nivel_top_paga.nombre} (+${data.salario.nivel_top_paga.incremento_vs_pregrado_pct}% sobre el pregrado).`, M, y);
      y += 7;
    }
  }

  // ── Skills ──────────────────────────────────────────────────────────────
  sectionTitle('Competencias y tecnologías clave (importancia O*NET 0–100)');
  const colW = (CW - 8) / 2;
  const yStart = y;
  const yA = barList('Competencias', data.skills.competencias.slice(0, 10), M, colW, NAVY);
  const yB = barList('Tecnologías', data.skills.tecnologias.slice(0, 10), M + colW + 8, colW, LIGHT, yStart);
  y = Math.max(yA, yB) + 4;

  // ── Seniority ────────────────────────────────────────────────────────────
  sectionTitle('¿Qué seniority conviene más?');
  if (data.seniority.confianza === 'limitada') {
    ensure(8); setFill(CREAM); doc.rect(M, y, CW, 7, 'F');
    setText(NAVY2); doc.setFont('helvetica', 'normal'); doc.setFontSize(8);
    doc.text(`Señal limitada: solo ${data.seniority.n_total_etiquetadas} vacantes declaran nivel. Tómese como orientación.`, M + 3, y + 4.6);
    y += 10;
  }
  ensure(6 + data.seniority.niveles.length * 6);
  setText(GRAY); doc.setFont('helvetica', 'bold'); doc.setFontSize(8);
  doc.text('Nivel', M, y); doc.text('Demanda', M + 70, y);
  y += 5;
  doc.setFont('helvetica', 'normal');
  data.seniority.niveles.forEach((nv) => {
    const rec = data.seniority.recomendado?.etiqueta === nv.etiqueta;
    setText(rec ? NAVY : NAVY2); doc.setFont('helvetica', rec ? 'bold' : 'normal'); doc.setFontSize(9);
    doc.text((rec ? '★ ' : '') + nv.etiqueta, M, y);
    doc.text(`${nv.demanda_pct}%`, M + 70, y);
    y += 6;
  });
  if (data.seniority.recomendado) {
    y += 1; ensure(12);
    setText(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(9);
    doc.text(`Recomendado: ${data.seniority.recomendado.etiqueta}`, M, y); y += 5;
    setText(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(8.5);
    wrap(data.seniority.recomendado.motivo, CW).forEach((ln) => { ensure(5); doc.text(ln, M, y); y += 4.5; });
  }

  // ── Perfil O*NET ─────────────────────────────────────────────────────────
  if (data.onet.job_zone || data.onet.riasec.length || data.onet.descripcion) {
    sectionTitle('Perfil ocupacional (O*NET)');
    if (data.onet.job_zone) {
      ensure(6); setText(NAVY2); doc.setFont('helvetica', 'bold'); doc.setFontSize(9);
      doc.text(`Preparación: ${data.onet.job_zone.etiqueta} (Job Zone ${data.onet.job_zone.nivel}/5)`, M, y); y += 6;
    }
    if (data.onet.riasec.length) {
      const top3 = [...data.onet.riasec].sort((a, b) => b.valor - a.valor).slice(0, 3);
      ensure(6); setText(NAVY2); doc.setFont('helvetica', 'normal'); doc.setFontSize(9);
      doc.text(`Intereses dominantes (RIASEC): ${top3.map((r) => `${r.nombre} ${Math.round(r.valor)}`).join('  ·  ')}`, M, y); y += 6;
      ensure(6); setText(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(8.5);
      doc.textWithLink('Conoce tu perfil', M, y, { url: LINK_TEST_PERFIL });
      y += 6;
    }
    if (data.onet.descripcion) {
      setText(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(8.5);
      wrap(data.onet.descripcion, CW).forEach((ln) => { ensure(5); doc.text(ln, M, y); y += 4.5; });
    }
  }

  // ── CNO 2025 (SENA) ──────────────────────────────────────────────────────
  // Va después de O*NET a propósito: es la contraparte colombiana del mismo
  // enfoque normativo, así el lector las compara una junto a la otra.
  const cno = data.cno_sena;
  if (cno && !cno.sin_datos) {
    sectionTitle('Perfil oficial colombiano (CNO 2025 - SENA)');
    if (cno.ocupacion?.nombre) {
      ensure(6); setText(NAVY2); doc.setFont('helvetica', 'bold'); doc.setFontSize(9);
      doc.text(`Ocupacion CNO ${cno.ocupacion.codigo}: ${cno.ocupacion.nombre}`, M, y); y += 6;
    }
    const lista = (titulo: string, items: { nombre: string }[]) => {
      if (!items.length) return;
      ensure(6); setText(GRAY); doc.setFont('helvetica', 'bold'); doc.setFontSize(8);
      doc.text(titulo.toUpperCase(), M, y); y += 5;
      setText(NAVY2); doc.setFont('helvetica', 'normal'); doc.setFontSize(8.5);
      wrap(items.map((i) => i.nombre).join(' · '), CW).forEach((ln) => { ensure(5); doc.text(ln, M, y); y += 4.5; });
      y += 2;
    };
    lista('Habilidades', cno.habilidades ?? []);
    lista('Conocimientos', cno.conocimientos ?? []);
  }

  // ── Pie en cada página ───────────────────────────────────────────────────
  const total = doc.getNumberOfPages();
  for (let i = 1; i <= total; i++) {
    doc.setPage(i);
    setText(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(7);
    doc.text(`Fuentes: ${data.meta.fuentes.join(' · ')}`, M, 292);
    doc.text(`${i}/${total}`, W - M, 292, { align: 'right' });
  }

  doc.save(`Perfil_Ocupacional_${data.programa.replace(/[^\wáéíóúñ]+/gi, '_')}.pdf`);

  // ── Helpers de dibujo (cierran sobre doc/y/M/CW) ────────────────────────
  function sectionTitle(txt: string) {
    ensure(12); y += 2;
    setText(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(11);
    doc.text(txt, M, y); y += 2;
    setFill(SKY); doc.rect(M, y, CW, 0.6, 'F'); y += 5;
  }
  function kvRow(pairs: [string, string][]) {
    ensure(11);
    const w = CW / pairs.length;
    pairs.forEach(([label, val], i) => {
      const x = M + i * w;
      setText(GRAY); doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5);
      doc.text(label, x, y);
      setText(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(10);
      doc.text(val, x, y + 5.5);
    });
    y += 12;
  }
  function barList(titulo: string, items: { nombre: string; peso: number }[], x: number, w: number, hex: string, yFixed?: number): number {
    let yy = yFixed ?? y;
    setText(NAVY); doc.setFont('helvetica', 'bold'); doc.setFontSize(9);
    doc.text(titulo, x, yy); yy += 5;
    doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5);
    items.forEach((it) => {
      setText(NAVY2); doc.text(cortar(it.nombre, 34), x, yy);
      const barY = yy + 1.4;
      setFill(SKY); doc.rect(x, barY, w, 1.6, 'F');
      setFill(hex); doc.rect(x, barY, (w * Math.min(100, it.peso)) / 100, 1.6, 'F');
      yy += 6.5;
    });
    return yy;
  }
  function wrap(txt: string, widthMm: number): string[] {
    return doc.splitTextToSize(txt, widthMm) as string[];
  }
}

// ── utilidades puras ───────────────────────────────────────────────────────
function rgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function cortar(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}
function fechaHoy(): string {
  const d = new Date();
  return d.toLocaleDateString('es-CO', { year: 'numeric', month: 'long', day: 'numeric' });
}
