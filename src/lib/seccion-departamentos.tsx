'use client';

/**
 * <SeccionDepartamentos /> — análisis geográfico de las vacantes colombianas.
 *
 * Abre la página de Tendencias cuando las fuentes seleccionadas son SOLO
 * colombianas: mapa de departamentos arriba, y debajo el detalle del que se
 * elija (o el consolidado nacional mientras no se elija ninguno).
 *
 * Por qué NO trae crecimiento
 * ---------------------------
 * Es una foto del estado actual, no una serie. Las vacantes colombianas se
 * concentran en 2 meses (Google Jobs y LinkedIn solo dan fechas relativas, así
 * que cada recolección alcanza ~2 meses hacia atrás) y una tendencia necesita
 * un mínimo de 3 periodos. Partida por departamento no queda ni de lejos, y
 * dibujar una flecha con 2 puntos sería inventar la señal. Ver el docstring de
 * `src/backend/Tendencias/geografia.py`.
 */

import { useEffect, useMemo, useState } from 'react';
import { MapPin, Info, AlertTriangle } from 'lucide-react';
import { MapaColombia, type DatoDepartamento } from '@/lib/mapa-colombia';
import { Spinner } from '@/lib/spinner';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Item {
  nombre: string;
  vacantes: number;
}

interface Panel {
  vacantes: number;
  cargos_distintos: number;
  empresas_distintas: number;
  ciudades_distintas: number;
  top_cargos: Item[];
  top_empresas: Item[];
  ciudades: Item[];
  grupos_cuoc: Item[];
  seniority: Item[];
  por_fuente: Item[];
  muestra_suficiente: boolean;
}

interface Departamento extends Panel, DatoDepartamento {}

interface Respuesta {
  departamentos: Departamento[];
  nacional: Panel;
  sin_departamento: { vacantes: number } & Partial<Panel>;
  meta: {
    total: number;
    con_departamento: number;
    sin_departamento: number;
    cobertura: number;
    departamentos_con_datos: number;
    min_muestra: number;
  };
}

/** Lista en barras horizontales, que es como se leen mejor los rankings. */
function Ranking({
  titulo,
  items,
  vacio,
  color = 'var(--sabana-navy)',
}: {
  titulo: string;
  items: Item[];
  vacio: string;
  color?: string;
}) {
  const max = items.length ? Math.max(...items.map((i) => i.vacantes)) : 0;
  return (
    <div>
      <h4 className="text-xs font-bold uppercase tracking-wide mb-3" style={{ color: 'var(--sabana-navy)' }}>
        {titulo}
      </h4>
      {items.length === 0 ? (
        <p className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>{vacio}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((i) => (
            <li key={i.nombre}>
              <div className="flex justify-between items-baseline gap-3 mb-1">
                <span className="text-sm truncate" style={{ color: 'var(--sabana-black-90)' }} title={i.nombre}>
                  {i.nombre}
                </span>
                <span className="text-sm font-semibold tabular-nums shrink-0" style={{ color: 'var(--sabana-dark-navy)' }}>
                  {i.vacantes.toLocaleString('es-CO')}
                </span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--sabana-sky-blue)' }}>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${max ? (i.vacantes / max) * 100 : 0}%`, backgroundColor: color }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Kpi({ valor, etiqueta }: { valor: number; etiqueta: string }) {
  return (
    <div className="rounded-lg p-4" style={{ backgroundColor: 'var(--sabana-sky-blue)' }}>
      <p className="text-2xl font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
        {valor.toLocaleString('es-CO')}
      </p>
      <p className="text-xs font-medium mt-0.5" style={{ color: 'var(--sabana-navy)' }}>{etiqueta}</p>
    </div>
  );
}

export function SeccionDepartamentos({
  programa,
  paises,
}: {
  /** Programa académico activo en la página ('TODOS' = sin filtrar). */
  programa: string;
  /** Mercados colombianos seleccionados: 'co' (Google Jobs) y/o 'co_li' (LinkedIn). */
  paises: string[];
}) {
  const [data, setData] = useState<Respuesta | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);

  const clavePaises = paises.slice().sort().join(',');

  useEffect(() => {
    let vivo = true;
    setCargando(true);
    setError(null);
    const params = new URLSearchParams({ programa, paises: clavePaises });
    fetch(`${BACKEND_URL}/tendencias/departamentos?${params}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => {
        if (!vivo) return;
        if (d.error) throw new Error(d.error);
        setData(d);
      })
      .catch((e) => vivo && setError(e.message))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, [programa, clavePaises]);

  // Al cambiar de filtros, un departamento que ya no tiene datos deja de existir.
  useEffect(() => {
    if (!data || !seleccionado) return;
    if (!data.departamentos.some((d) => d.codigo === seleccionado)) setSeleccionado(null);
  }, [data, seleccionado]);

  const activo = useMemo(
    () => data?.departamentos.find((d) => d.codigo === seleccionado) ?? null,
    [data, seleccionado],
  );

  const panel: Panel | null = activo ?? data?.nacional ?? null;
  const titulo = activo ? activo.nombre : 'Colombia — consolidado nacional';

  return (
    <section className="mb-10">
      <div className="flex items-center gap-2 mb-1">
        <MapPin className="w-5 h-5" style={{ color: 'var(--sabana-navy)' }} />
        <h2 className="text-xl font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
          Vacantes por departamento
        </h2>
      </div>
      <p className="text-sm mb-5" style={{ color: 'var(--sabana-black-70)' }}>
        Seleccione un departamento en el mapa para ver su detalle. Es una foto del estado actual de las
        vacantes recolectadas, no una serie de crecimiento.
      </p>

      {cargando && !data ? (
        <Spinner label="Cargando análisis por departamento..." />
      ) : error ? (
        <div
          className="rounded-lg p-4 text-sm"
          style={{ backgroundColor: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}
        >
          No se pudo cargar el análisis por departamento ({error}).
        </div>
      ) : !data || data.meta.total === 0 ? (
        <div
          className="rounded-lg p-4 text-sm"
          style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-navy)' }}
        >
          No hay vacantes colombianas para los filtros seleccionados.
        </div>
      ) : (
        <div className="rounded-lg border p-5" style={{ borderColor: 'var(--sabana-light-blue)' }}>
          <div className="grid lg:grid-cols-[minmax(0,420px)_1fr] gap-8">
            {/* ---------------- Mapa ---------------- */}
            <div>
              <MapaColombia
                datos={data.departamentos}
                seleccionado={seleccionado}
                onSelect={setSeleccionado}
              />
              <p className="text-xs mt-3 text-center" style={{ color: 'var(--sabana-black-50)' }}>
                {data.meta.departamentos_con_datos} departamentos con vacantes ·{' '}
                {data.meta.cobertura}% de las {data.meta.total.toLocaleString('es-CO')} vacantes
                colombianas declaran ubicación
              </p>
            </div>

            {/* ---------------- Detalle ---------------- */}
            <div>
              <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <h3 className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
                  {titulo}
                </h3>
                {activo && (
                  <button
                    onClick={() => setSeleccionado(null)}
                    className="text-xs font-medium underline"
                    style={{ color: 'var(--sabana-navy)' }}
                  >
                    Ver todo el país
                  </button>
                )}
              </div>

              {/* Aviso de muestra corta: el dato se muestra igual, pero no se
                  presta a leerlo como un patrón del mercado. */}
              {activo && !activo.muestra_suficiente && (
                <div
                  className="flex gap-2 rounded-lg p-3 mb-4 text-xs"
                  style={{ backgroundColor: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}
                >
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>
                    Muestra insuficiente: {activo.vacantes} vacante{activo.vacantes === 1 ? '' : 's'}{' '}
                    (mínimo sugerido: {data.meta.min_muestra}). Las cifras son reales, pero son muy
                    pocas para leerlas como el patrón del departamento.
                  </span>
                </div>
              )}

              {panel && (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                    <Kpi valor={panel.vacantes} etiqueta="Vacantes" />
                    <Kpi valor={panel.cargos_distintos} etiqueta="Cargos distintos" />
                    <Kpi valor={panel.empresas_distintas} etiqueta="Empresas" />
                    <Kpi valor={panel.ciudades_distintas} etiqueta="Ciudades" />
                  </div>

                  <div className="grid sm:grid-cols-2 gap-x-8 gap-y-6">
                    <Ranking titulo="Cargos más demandados" items={panel.top_cargos} vacio="Sin cargos identificados." />
                    <Ranking
                      titulo="Ciudades"
                      items={panel.ciudades}
                      vacio="Sin ciudad especificada."
                      color="var(--cat-2)"
                    />
                    <Ranking
                      titulo="Empresas que más publican"
                      items={panel.top_empresas}
                      vacio="Sin empresas identificadas."
                      color="var(--cat-1)"
                    />
                    <div className="space-y-6">
                      <Ranking
                        titulo="Grupos de la CUOC"
                        items={panel.grupos_cuoc}
                        vacio="Sin clasificar."
                        color="var(--cat-4)"
                      />
                      <Ranking
                        titulo="Nivel de experiencia"
                        items={panel.seniority}
                        vacio="Sin clasificar."
                        color="var(--cat-5)"
                      />
                    </div>
                  </div>

                  {panel.por_fuente.length > 1 && (
                    <p className="text-xs mt-6" style={{ color: 'var(--sabana-black-50)' }}>
                      Origen:{' '}
                      {panel.por_fuente
                        .map((f) => `${f.nombre} (${f.vacantes.toLocaleString('es-CO')})`)
                        .join(' · ')}
                    </p>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Vacantes que no declaran departamento. No se reparten entre los
              demás: se reportan aparte para que el mapa no parezca incompleto
              sin explicación. */}
          {data.meta.sin_departamento > 0 && (
            <div
              className="flex gap-2 rounded-lg p-3 mt-6 text-xs"
              style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-navy)' }}
            >
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                {data.meta.sin_departamento.toLocaleString('es-CO')} vacante
                {data.meta.sin_departamento === 1 ? '' : 's'} no aparece
                {data.meta.sin_departamento === 1 ? '' : 'n'} en el mapa porque su publicación solo dice
                &quot;Colombia&quot;, sin ciudad ni departamento (suelen ser ofertas nacionales o
                remotas). Sí están contadas en el consolidado nacional.
              </span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
