'use client';

/**
 * <GraficasInforme /> — las gráficas PROPIAS de un informe: qué dice ESE
 * documento (top de skills por menciones y reparto técnicas / power skills),
 * sin cruzarlo con las vacantes (para eso está el contraste en Skills).
 *
 * Es un componente aparte porque lo pintan las dos vistas de /informes: el
 * Admin al pulsar "Ver gráficas" y el Usuario en el "Análisis" de cada PDF
 * suyo. Recibe el `Detalle` ya cargado (o null mientras llega) y no hace
 * ningún fetch: quién y cuándo lo pide lo decide cada vista.
 */

import type { Detalle } from './comun';
import { COLORES_CAT, TOOLTIP_STYLE } from './comun';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

export function GraficasInforme({ detalle }: { detalle: Detalle | null }) {
  if (!detalle) {
    return (
      <p className="text-sm text-center py-4" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
    );
  }
  if (!detalle.informe || detalle.items.length === 0) {
    return (
      <p className="text-sm text-center py-4" style={{ color: 'var(--sabana-black-50)' }}>
        Este informe no tiene skills extraídas todavía.
      </p>
    );
  }

  return (
    <>
      <p className="text-xs mb-4" style={{ color: 'var(--sabana-black-50)' }}>
        {detalle.informe.total_skills} skills · {detalle.informe.paginas} páginas ·
        cobertura {detalle.informe.cobertura} · idioma {detalle.informe.idioma}
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top skills del informe */}
        <div className="lg:col-span-2">
          <h4 className="text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
            Skills más citadas en el informe
          </h4>
          <ResponsiveContainer width="100%" height={Math.max(240, detalle.items.length * 24)}>
            <BarChart data={detalle.items} layout="vertical" margin={{ left: 8, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
              <YAxis dataKey="termino" type="category" width={165} interval={0}
                tick={{ fontSize: 10, fill: 'var(--sabana-dark-navy)' }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }}
                labelStyle={{ color: 'var(--sabana-light-blue)' }}
                formatter={(v, _n, it) => [`${v} menciones · pág. ${it?.payload?.pagina ?? '—'}`, 'En el informe']} />
              <Bar dataKey="valor" fill="var(--sabana-navy)" radius={[0, 4, 4, 0]} barSize={12} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
            El nº de menciones ordena dentro de ESTE informe; no es comparable con otro
            documento, porque depende de su extensión.
          </p>
        </div>

        {/* Reparto por categoría */}
        <div>
          <h4 className="text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
            Por categoría
          </h4>
          {detalle.por_categoria.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Sin categorías.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={detalle.por_categoria} dataKey="n" nameKey="categoria"
                  innerRadius={45} outerRadius={80} paddingAngle={2}>
                  {detalle.por_categoria.map((c, i) => (
                    <Cell key={c.categoria} fill={COLORES_CAT[i % COLORES_CAT.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} />
                <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </>
  );
}
