import { describe, expect, it } from 'vitest';
import { jsPDF } from 'jspdf';
import { dibujar } from '@/lib/informe-general';

const vacio = {
  tend: { meta: { total_terminos: 0, crecientes: 0, estables: 0, decrecientes: 0 }, terminos: {} },
  dem: { cargos: [], sectores: [], empresas: [], programas: [], meta: { total: 0 } },
  comp: [],
  tec: [],
};

describe('informe general (PDF)', () => {
  it('dibuja las 6 franjas aunque no haya datos', () => {
    const r = dibujar(new jsPDF({ unit: 'mm', format: [210, 6000] }), vacio, null);
    expect(r.bandas).toHaveLength(6);
    expect(r.alto).toBeGreaterThan(300);
  });

  it('con datos, la 2.ª pasada con las franjas medidas da el mismo alto', () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ label: `Cargo ${i}`, count: 100 - i }));
    const datos = {
      tend: {
        meta: { total_terminos: 2, crecientes: 1, estables: 0, decrecientes: 1 },
        terminos: { A: { tendencia: 'creciente', score_tendencia: 0.9 }, B: { tendencia: 'decrecientes', score_tendencia: 0.2 } },
      },
      dem: { cargos: items, sectores: items, empresas: items, programas: items, meta: { total: 1234 } },
      comp: [{ nombre: 'Escucha activa', indice: 100 }],
      tec: [{ nombre: 'SAP', indice: 80 }],
    };
    const a = dibujar(new jsPDF({ unit: 'mm', format: [210, 6000] }), datos, null);
    const b = dibujar(new jsPDF({ unit: 'mm', format: [210, Math.ceil(a.alto)] }), datos, null, a.bandas);
    expect(b.alto).toBeCloseTo(a.alto, 5);
  });
});
