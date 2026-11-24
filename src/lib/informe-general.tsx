'use client';

/**
 * <InformeGeneral /> — botón de Administrador que descarga un PDF con el panorama
 * COMPLETO del Observatorio: tendencias de cargos, demanda actual y competencias
 * y tecnologías más demandadas, sin filtrar por programa.
 *
 * El diseño sigue la infografía institucional «Global Skills Report 2026» de la
 * Universidad: UNA sola página larga con franjas de color (azul oscuro, blanco,
 * gris, azul pálido y crema), titulares en serif cursiva, kicker numerado
 * («01 · …») y tarjetas con barras o listas numeradas.
 *
 * Todo se arma en el navegador con jsPDF a partir de los mismos GET públicos
 * que alimentan las páginas (no hay endpoint nuevo): usa TODAS las fuentes que
 * ofrece /tendencias/opciones, igual que la vista por defecto de Tendencias.
 * Quien lo monta lo envuelve en <SoloAdmin>.
 */

import { useState } from 'react';
import { jsPDF } from 'jspdf';
import { Spinner } from '@/lib/spinner';
import { rgb, cortar, fechaHoy } from '@/lib/perfil-pdf';
import { cachedFetch } from './cache-api';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Item { label: string; count: number }
interface Skill { nombre: string; indice: number }
interface Termino { tendencia: string; score_tendencia: number }
interface Datos {
  tend: { meta: { total_terminos: number; crecientes: number; estables: number; decrecientes: number }; terminos: Record<string, Termino> };
  dem: { cargos: Item[]; sectores: Item[]; empresas: Item[]; programas: Item[]; meta: { total: number } };
  comp: Skill[];
  tec: Skill[];
}

// Paleta de la infografía (azul institucional + franjas de apoyo).
const C = {
  oscuro: '#001c64', azul: '#193f9e', claro: '#9dc4ff', palido: '#e0edff',
  gris: '#f4f4f4', crema: '#fffae0', texto: '#282828', suave: '#6d6d6d',
  rojo: '#dc2626', borde: '#e3e6ec', pista: '#eceff5', blanco: '#ffffff',
};

async function get<T>(ruta: string): Promise<T> {
  const r = await cachedFetch(`${BACKEND_URL}${ruta}`);
  if (!r.ok) throw new Error(`${ruta.split('?')[0]}: HTTP ${r.status}`);
  return r.json();
}

// El logo es un JPEG con fondo blanco: va en una ficha blanca sobre el azul.
// Si no se puede leer, el informe sale igual con el nombre en texto.
async function cargarLogo(): Promise<string | null> {
  try {
    const r = await fetch('/logo-talenthub.jpeg');
    if (!r.ok) return null;
    const b = await r.blob();
    return await new Promise<string>((ok, mal) => {
      const f = new FileReader();
      f.onload = () => ok(f.result as string);
      f.onerror = () => mal(f.error);
      f.readAsDataURL(b);
    });
  } catch {
    return null;
  }
}

export async function reunirDatos(): Promise<Datos> {
  const opc = await get<{ fuentes: { pais: string }[] }>('/tendencias/opciones');
  const paises = encodeURIComponent(opc.fuentes.map((f) => f.pais).join(','));
  const base = `programa=TODOS&seniority=TODOS&paises=${paises}`;
  const [tend, dem, comp, tec] = await Promise.all([
    get<Datos['tend']>(`/tendencias?dimension=cargo&${base}`),
    get<Datos['dem']>(`/tendencias/demanda?${base}&escolaridad=TODOS&top=10`),
    get<{ items: Skill[] }>(`/skills-demandadas?tipo=competencia&${base}&top=15`),
    get<{ items: Skill[] }>(`/skills-demandadas?tipo=tecnologia&${base}&top=15`),
  ]);
  return { tend, dem, comp: comp.items, tec: tec.items };
}

const W = 210, M = 14, CW = W - M * 2, GAP = 6;
const COL = (CW - GAP) / 2, X2 = M + COL + GAP;
const num = (n: number) => n.toLocaleString('es-CO');

/**
 * Dibuja el informe en UNA página. Las franjas de fondo se pintan ANTES que su
 * contenido, y su alto solo se conoce al terminar: por eso se dibuja dos veces
 * (la primera mide las franjas, la segunda las usa) y el alto de la página sale
 * de la primera pasada. Devuelve ese alto y la lista de franjas.
 */
export function dibujar(doc: jsPDF, d: Datos, logo: string | null, medidas?: number[]) {
  const bandas: number[] = [];
  let y = 0, idx = 0;
  const fill = (h: string) => doc.setFillColor(...rgb(h));
  const ink = (h: string) => doc.setTextColor(...rgb(h));
  const trazo = (h: string) => doc.setDrawColor(...rgb(h));
  const fuente = (estilo: 'normal' | 'bold' | 'italic', tam: number, fam: 'helvetica' | 'times' = 'helvetica') => {
    doc.setFont(fam, estilo); doc.setFontSize(tam);
  };
  const kicker = (t: string, x: number, yy: number, color: string) => {
    ink(color); fuente('bold', 7); doc.text(t.toUpperCase(), x, yy, { charSpace: 0.45 });
  };

  // Franja de ancho completo: el fondo se pinta con el alto medido en la 1.ª pasada.
  const banda = (bg: string, pad: number, contenido: () => void) => {
    const i = idx++, y0 = y, h = medidas?.[i];
    if (h) { fill(bg); doc.rect(0, y0, W, h, 'F'); }
    y += pad; contenido(); y += pad;
    bandas[i] = y - y0;
  };

  const encabezado = (n: string, etiqueta: string, titulo: string, lead: string) => {
    kicker(`${n} · ${etiqueta}`, M, y + 3, C.azul);
    ink(C.oscuro); fuente('italic', 22, 'times'); doc.text(titulo, M, y + 14);
    ink(C.texto); fuente('normal', 9);
    const lineas = doc.splitTextToSize(lead, CW * 0.82) as string[];
    doc.text(lineas, M, y + 22, { lineHeightFactor: 1.45 });
    y += 22 + lineas.length * 4.4 + 7;
  };

  // Tarjeta con barras (estilo «Crecimiento YoY por habilidad»).
  const tarjetaBarras = (
    x: number, w: number, titulo: string, items: Item[], max: number,
    topColor: string, colorBarra: (i: number) => string, filas: number,
  ) => {
    const h = 19 + filas * 9;
    fill(C.blanco); trazo(C.borde); doc.setLineWidth(0.25); doc.rect(x, y, w, h, 'FD');
    fill(topColor); doc.rect(x, y, w, 1.2, 'F');
    ink(C.oscuro); fuente('bold', 9.5); doc.text(titulo, x + 5, y + 9);
    trazo(C.borde); doc.line(x + 5, y + 12, x + w - 5, y + 12);
    if (!items.length) { ink(C.suave); fuente('normal', 8); doc.text('Sin datos suficientes.', x + 5, y + 19); }
    items.forEach((it, i) => {
      const yy = y + 18.5 + i * 9;
      ink(C.texto); fuente('normal', 8); doc.text(cortar(it.label, 36), x + 5, yy);
      ink(C.oscuro); fuente('bold', 8); doc.text(num(it.count), x + w - 5, yy, { align: 'right' });
      fill(C.pista); doc.rect(x + 5, yy + 1.8, w - 10, 2, 'F');
      fill(colorBarra(i)); doc.rect(x + 5, yy + 1.8, Math.max(0.6, ((w - 10) * it.count) / (max || 1)), 2, 'F');
    });
    return h;
  };

  // Tarjeta de lista numerada (estilo «Top 10 habilidades»), cabecera de color.
  const tarjetaRanking = (x: number, w: number, titulo: string, items: Item[], color: string, filas: number) => {
    const h = 10 + filas * 9.5 + 2;
    fill(C.blanco); trazo(C.borde); doc.setLineWidth(0.25); doc.rect(x, y, w, h, 'FD');
    fill(color); doc.rect(x, y, w, 10, 'F');
    ink(C.blanco); fuente('bold', 9.5); doc.text(titulo, x + 5, y + 6.6);
    if (!items.length) { ink(C.suave); fuente('normal', 8); doc.text('Sin datos suficientes.', x + 5, y + 18); }
    items.forEach((it, i) => {
      const yy = y + 10 + i * 9.5;
      if (i > 0) { trazo(C.borde); doc.line(x + 1, yy, x + w - 1, yy); }
      ink(C.azul); fuente('italic', 10, 'times'); doc.text(String(i + 1).padStart(2, '0'), x + 5, yy + 6);
      ink(C.oscuro); fuente('bold', 8); doc.text(cortar(it.label, 36), x + 14, yy + 5.8);
      ink(C.suave); fuente('normal', 7.5); doc.text(num(it.count), x + w - 5, yy + 5.8, { align: 'right' });
    });
    return h;
  };

  const par = (alto: (x: number, w: number, f: number) => number, alto2: (x: number, w: number, f: number) => number, filas: number) => {
    const h = Math.max(alto(M, COL, filas), alto2(X2, COL, filas));
    y += h + GAP;
  };

  // ── Datos derivados ─────────────────────────────────────────────────────────
  const { tend, dem } = d;
  const ordenados = (dir: string): Item[] =>
    Object.entries(tend.terminos).filter(([, t]) => t.tendencia === dir)
      .sort((a, b) => b[1].score_tendencia - a[1].score_tendencia).slice(0, 10)
      .map(([label, t]) => ({ label, count: Math.round(t.score_tendencia * 100) }));
  const cre = ordenados('creciente'), dec = ordenados('decreciente');
  const sk = (a: Skill[]): Item[] => a.map((s) => ({ label: s.nombre, count: s.indice }));
  const comp = sk(d.comp), tec = sk(d.tec);
  const banda3 = (i: number) => (i < 3 ? C.oscuro : i < 8 ? C.azul : C.claro);

  // ── Barra superior ──────────────────────────────────────────────────────────
  fill(C.gris); doc.rect(0, 0, W, 8, 'F');
  ink(C.oscuro); fuente('bold', 6.8); doc.text('Dirección de Alumni', M, 5);
  const wAlumni = doc.getTextWidth('Dirección de Alumni');
  ink(C.suave); fuente('normal', 6.8); doc.text(' · Observatorio Laboral', M + wAlumni, 5);
  ink(C.oscuro); doc.text('Informe general   |   Todas las fuentes   |   Todos los programas', W - M, 5, { align: 'right' });
  y = 8;

  // ── Portada (franja azul oscuro) ────────────────────────────────────────────
  banda(C.oscuro, 0, () => {
    const y0 = y;
    fill('#0b2c86'); doc.circle(W - 6, y0 + 36, 30, 'F'); // adorno, como en la infografía
    // Logo (ficha blanca) o nombre en texto.
    if (logo) {
      fill(C.blanco); doc.roundedRect(M, y0 + 8, 46, 24.5, 2, 2, 'F');
      doc.addImage(logo, 'JPEG', M + 1, y0 + 8.6, 44, 23.4);
    } else {
      ink(C.blanco); fuente('bold', 13); doc.text('TalentHub UniSabana', M, y0 + 20);
    }
    // Etiquetas de la derecha.
    fuente('bold', 7); const tI = 'INFORME ESTRATÉGICO', wI = doc.getTextWidth(tI) + tI.length * 0.4 + 10;
    fill(C.azul); doc.rect(W - M - wI, y0 + 15, wI, 8, 'F');
    ink(C.blanco); doc.text(tI, W - M - wI / 2, y0 + 20.2, { align: 'center', charSpace: 0.4 });
    const tE = `Edición ${new Date().getFullYear()}`;
    fuente('normal', 7); const wE = doc.getTextWidth(tE) + 9;
    trazo('#6f8fd6'); doc.setLineWidth(0.3); doc.rect(W - M - wI - 4 - wE, y0 + 15, wE, 8, 'S');
    ink(C.blanco); doc.text(tE, W - M - wI - 4 - wE / 2, y0 + 20.1, { align: 'center' });

    trazo('#22409a'); doc.setLineWidth(0.25); doc.line(M, y0 + 40, W - M, y0 + 40);
    kicker('Síntesis ejecutiva · Mercado laboral', M, y0 + 49, C.claro);
    fuente('italic', 25, 'times');
    ink('#e8f0ff'); doc.text('El mercado laboral hoy:', M, y0 + 61);
    ink(C.claro); doc.text('demanda, tendencias y competencias', M, y0 + 72);

    ink('#c9d6f0'); fuente('normal', 9.5);
    const lead = `Lectura consolidada de ${num(dem.meta.total)} vacantes de todas las fuentes y todos los programas académicos: qué cargos crecen o decrecen, dónde se concentra la contratación y qué competencias y tecnologías piden las empresas.`;
    const lineas = doc.splitTextToSize(lead, CW * 0.78) as string[];
    doc.text(lineas, M, y0 + 82, { lineHeightFactor: 1.45 });
    const ky = y0 + 82 + lineas.length * 4.9 + 4;

    // Franja de cifras con borde, como en la infografía.
    const kpis: [string, string][] = [
      [num(dem.meta.total), 'Vacantes analizadas en todas las fuentes'],
      [String(tend.meta.total_terminos), 'Cargos con tendencia medible'],
      [String(tend.meta.crecientes), `Cargos en crecimiento (${tend.meta.estables} estables)`],
      [String(tend.meta.decrecientes), 'Cargos en descenso'],
    ];
    const cw = CW / 4;
    trazo('#2a4aa0'); doc.setLineWidth(0.3); doc.rect(M, ky, CW, 25, 'S');
    kpis.forEach(([v, l], i) => {
      const x = M + i * cw;
      if (i > 0) doc.line(x, ky, x, ky + 25);
      ink(C.blanco); fuente('italic', 21, 'times'); doc.text(v, x + 5, ky + 11);
      ink('#b5c5e6'); fuente('normal', 7);
      doc.text(doc.splitTextToSize(l, cw - 10) as string[], x + 5, ky + 16.5, { lineHeightFactor: 1.35 });
    });
    y = ky + 25 + 14;
  });

  // ── 01 Tendencias ───────────────────────────────────────────────────────────
  banda(C.blanco, 13, () => {
    encabezado('01', 'Diagnóstico de tendencias',
      `${tend.meta.crecientes} cargos crecen y ${tend.meta.decrecientes} decrecen`,
      'Índice de tendencia (0–100) de los cargos publicados: se muestran los 10 con mayor puntaje en cada dirección.');
    const f = Math.max(cre.length, dec.length, 1);
    par(
      (x, w, fi) => tarjetaBarras(x, w, 'Cargos crecientes', cre, 100, C.claro, () => C.oscuro, fi),
      (x, w, fi) => tarjetaBarras(x, w, 'Cargos decrecientes', dec, 100, C.rojo, () => C.rojo, fi), f);
    y -= GAP;
  });

  // ── 02 Demanda ──────────────────────────────────────────────────────────────
  banda(C.gris, 13, () => {
    encabezado('02', 'Demanda actual',
      'Dónde se concentra la contratación',
      `Número de vacantes por categoría, sobre un total de ${num(dem.meta.total)} vacantes analizadas.`);
    par(
      (x, w, fi) => tarjetaRanking(x, w, 'Cargos más demandados', dem.cargos, C.oscuro, fi),
      (x, w, fi) => tarjetaRanking(x, w, 'Sectores', dem.sectores, C.azul, fi),
      Math.max(dem.cargos.length, dem.sectores.length, 1));
    par(
      (x, w, fi) => tarjetaRanking(x, w, 'Empresas que más contratan', dem.empresas, C.oscuro, fi),
      (x, w, fi) => tarjetaRanking(x, w, 'Programas con más demanda', dem.programas, C.azul, fi),
      Math.max(dem.empresas.length, dem.programas.length, 1));
    y -= GAP;
  });

  // ── 03 Competencias y tecnologías ───────────────────────────────────────────
  banda(C.palido, 13, () => {
    encabezado('03', 'Competencias y tecnologías',
      'Lo que piden las empresas',
      'Índice de demanda (0–100) de las 15 competencias y tecnologías más mencionadas en las vacantes.');
    const f = Math.max(comp.length, tec.length, 1);
    par(
      (x, w, fi) => tarjetaBarras(x, w, 'Competencias', comp, 100, C.oscuro, banda3, fi),
      (x, w, fi) => tarjetaBarras(x, w, 'Tecnologías', tec, 100, C.azul, banda3, fi), f);
    y -= GAP;
  });

  // ── 04 Lectura rápida (franja crema) ────────────────────────────────────────
  banda(C.crema, 13, () => {
    encabezado('04', 'Lectura rápida', 'Tres señales para la gestión',
      'Resumen automático de lo que más destaca en los datos consolidados.');
    const señales: [string, string, string][] = [
      ['Cargo en mayor ascenso', cre[0]?.label ?? 'Sin datos suficientes',
        cre[0] ? `Es el cargo con la tendencia creciente más fuerte (índice ${cre[0].count} de 100).` : 'Aún no hay cargos con tendencia creciente medible.'],
      ['Mayor demanda', dem.cargos[0]?.label ?? 'Sin datos suficientes',
        dem.cargos[0] ? `${num(dem.cargos[0].count)} vacantes. Sector líder: ${dem.sectores[0]?.label ?? '—'}.` : 'Sin vacantes para resumir.'],
      ['Habilidades líderes', comp[0]?.label ?? 'Sin datos suficientes',
        `Competencia con mayor índice${tec[0] ? `; en tecnologías, ${tec[0].label}` : ''}.`],
    ];
    const w = (CW - GAP * 2) / 3;
    señales.forEach(([t, v, txt], i) => {
      const x = M + i * (w + GAP);
      fill(C.blanco); trazo(C.borde); doc.setLineWidth(0.25); doc.rect(x, y, w, 40, 'FD');
      fill(C.claro); doc.rect(x, y, w, 1.2, 'F');
      kicker(t, x + 5, y + 9, C.azul);
      ink(C.oscuro); fuente('bold', 9.5);
      doc.text((doc.splitTextToSize(v, w - 10) as string[]).slice(0, 2), x + 5, y + 16, { lineHeightFactor: 1.3 });
      ink(C.suave); fuente('normal', 8);
      doc.text((doc.splitTextToSize(txt, w - 10) as string[]).slice(0, 4), x + 5, y + 27, { lineHeightFactor: 1.35 });
    });
    y += 40;
  });

  // ── Pie ─────────────────────────────────────────────────────────────────────
  banda(C.oscuro, 12, () => {
    ink(C.blanco); fuente('bold', 12); doc.text('Universidad de La Sabana', M, y + 5);
    ink(C.claro); fuente('normal', 8); doc.text('Dirección de Alumni · Observatorio Laboral', M, y + 11);
    ink('#b5c5e6'); fuente('normal', 7);
    const nota = doc.splitTextToSize(
      'Nota metodológica: informe consolidado de todas las fuentes y todos los programas académicos. Los índices de tendencia y de competencias van de 0 a 100.', CW * 0.5) as string[];
    doc.text(nota, M, y + 18, { lineHeightFactor: 1.4 });
    ink(C.blanco); fuente('bold', 7.5); doc.text('Fuentes: Adzuna · Google Jobs · LinkedIn · O*NET', W - M, y + 5, { align: 'right' });
    ink('#b5c5e6'); fuente('normal', 7.5); doc.text(`Generado: ${fechaHoy()}`, W - M, y + 11, { align: 'right' });
    y += 24;
  });

  return { alto: y, bandas };
}

async function descargar() {
  const [datos, logo] = await Promise.all([reunirDatos(), cargarLogo()]);
  // 1.ª pasada en una página enorme de prueba: solo para medir franjas y alto.
  const { alto, bandas } = dibujar(new jsPDF({ unit: 'mm', format: [W, 6000] }), datos, logo);
  const doc = new jsPDF({ unit: 'mm', format: [W, Math.ceil(alto)] });
  dibujar(doc, datos, logo, bandas);
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
    <section className="rounded-lg border p-4 mb-4 text-sm" style={{ borderColor: 'var(--line)' }}>
      <h3 className="font-bold mb-1" style={{ color: 'var(--ink-strong)' }}>Informe general (PDF)</h3>
      <p className="text-xs mb-3" style={{ color: 'var(--ink-muted)' }}>
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
