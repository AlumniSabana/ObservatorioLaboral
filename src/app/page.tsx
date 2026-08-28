'use client';

/**
 * Página "Tendencias" — es la PORTADA del Observatorio (ruta '/').
 *
 * Muestra qué términos del mercado laboral CRECEN, se mantienen ESTABLES o
 * DECRECEN a lo largo del tiempo, usando la fecha de publicación real de cada
 * vacante (`created_at` de Adzuna).
 *
 * Dos dimensiones (combo box):
 *   - 'cargo'  : títulos de cargo normalizados (ej. 'software engineer')
 *   - 'sector' : categorías de Adzuna (ej. 'IT Jobs')
 *
 * La métrica es el SHARE, no el conteo: cada mes se muestrea con un número
 * distinto de vacantes, así que se compara "qué % de las vacantes del mes
 * mencionan el término". Ver src/backend/Tendencias/tendencias_service.py.
 *
 * Los datos los sirve GET /tendencias?dimension=... y los llena el backfill
 * POST /tendencias/recolectar.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { SelectorFuentes, type FuenteOpcion as OpcionSelector } from '@/lib/selector-fuentes';
import { Spinner } from '@/lib/spinner';
import { useState, useEffect, useMemo } from 'react';
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

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Tipos que devuelve GET /tendencias
// ---------------------------------------------------------------------------

type Tendencia = 'creciente' | 'estable' | 'decreciente';

interface PuntoHistorial {
  menciones: number;
  // Proporción de las vacantes de ese mes. Alimenta el eje de la gráfica de
  // evolución; no se muestra como indicador suelto.
  share: number;
  n_vacantes: number;
}

interface TerminoTendencia {
  historial: Record<string, PuntoHistorial>; // periodo (YYYY-MM-01) -> punto
  tendencia: Tendencia;
  score_tendencia: number;
  total_menciones: number;
  primera_aparicion: string;
  ultima_aparicion: string;
  periodos_cubiertos: number;
}

interface ResumenTermino {
  termino: string;
  score: number;
}

interface Insights {
  mas_dinamico: ResumenTermino | null;
  emergentes: { total: number; top: ResumenTermino[] };
  a_monitorear: { total: number; top: ResumenTermino[] };
}

interface TendenciasResponse {
  meta: {
    dimension: string;
    fuente?: string;
    pais?: string;
    programa?: string;
    seniority?: string;
    total_terminos: number;
    crecientes: number;
    estables: number;
    decrecientes: number;
    periodos: string[];
    vacantes_por_periodo?: Record<string, number>;
    sin_datos: boolean;
  };
  terminos: Record<string, TerminoTendencia>;
  insights: Insights;
}

// Salario por programa (GEIH+SPE, /analytics/salarios) — solo se pide lo que
// esta página necesita: el promedio ("media") cuando se filtra un programa.
// La granularidad real es por gran-grupo CNO (2 dígitos), no por cargo exacto.
interface SalarioPrograma {
  kpis: { media: number; mediana: number; n: number } | null;
  tiene_geih: boolean;
  // Promedio mensual en COP de las vacantes de Adzuna seleccionadas (ver
  // Tendencias/demanda_actual.py::salario_vacantes_cop). Solo Adzuna trae
  // salario estructurado — Google Jobs y LinkedIn no aportan aquí.
  salario_vacantes?: {
    disponible: boolean;
    media_cop?: number;
    n?: number;
    paises?: string[];
    trm_fecha?: string;
  };
}

interface FuenteOpcion {
  fuente: string;
  pais: string;
  label: string;
  // Dimensiones con datos en esa fuente. Google Jobs no entrega sector, y solo
  // las fuentes con descripción completa producen 'skill'.
  dimensiones?: string[];
}

interface Opciones {
  programas: string[];
  seniorities: string[];
  escolaridades: string[];
  periodos: string[];
  fuentes: FuenteOpcion[];
}

// 'skill' se quitó a propósito: nunca llegó a mostrar datos (requiere ≥3 meses
// de Google Jobs con volumen, algo que nunca se acumuló) y esa función ya la
// cubre la página Competencias con su propio mecanismo, independiente de esto.
type Dimension = 'cargo' | 'sector';

const TODOS = 'TODOS';

// Fuente por defecto mientras cargan las opciones reales del backend.
const FUENTE_DEFECTO: FuenteOpcion = { fuente: 'adzuna', pais: 'us', label: 'Adzuna — Estados Unidos' };

// Etiquetas legibles de seniority (el backend usa las claves crudas).
const SENIORITY_LABEL: Record<string, string> = {
  TODOS: 'Todos los niveles',
  senior: 'Senior',
  junior: 'Junior',
  graduado: 'Recién graduado',
  no_especificado: 'No especificado',
};

// Etiquetas legibles de escolaridad. Es un filtro DISTINTO de seniority: no
// mide experiencia sino tipo de ocupación (Grandes Grupos CIUO-08 + Junior y
// Recién Graduado, que sí se solapan con seniority pero se repiten aquí
// porque el título los señala igual de bien). Ver Tendencias/escolaridad.py.
const ESCOLARIDAD_LABEL: Record<string, string> = {
  TODOS: 'Todos',
  directivo: 'Directores y gerentes',
  profesional: 'Profesionales, científicos e intelectuales',
  tecnico: 'Técnicos y profesionales de nivel medio',
  apoyo_administrativo: 'Personal de apoyo administrativo',
  servicios_ventas: 'Trabajadores de servicios y vendedores',
  oficios: 'Oficiales, operarios y artesanos',
  operadores: 'Operadores de máquinas y ensambladores',
  elemental: 'Ocupaciones elementales',
  junior: 'Junior',
  graduado: 'Recién graduado',
};

const DIMENSIONES: Record<Dimension, { label: string; titulo: string; singular: string }> = {
  cargo: {
    label: 'Cargos',
    titulo: 'Tendencias por cargo',
    singular: 'cargo',
  },
  sector: {
    label: 'Sectores',
    titulo: 'Tendencias por sector',
    singular: 'sector',
  },
};

// Color por tendencia: par divergente + neutro (ver globals.css).
const COLOR_TENDENCIA: Record<Tendencia, string> = {
  creciente: 'var(--trend-up)',
  estable: 'var(--trend-flat)',
  decreciente: 'var(--trend-down)',
};

// El símbolo acompaña siempre al color: la identidad nunca depende solo del color.
const SIMBOLO: Record<Tendencia, string> = {
  creciente: '▲',
  estable: '■',
  decreciente: '▼',
};

const ETIQUETA: Record<Tendencia, string> = {
  creciente: 'Creciente',
  estable: 'Estable',
  decreciente: 'Decreciente',
};

// ── Serie mensual del SPE (Colombia) ───────────────────────────────────────
// Va en su propia sección y NO en la gráfica principal: aquella son mercados
// extranjeros (Adzuna) medidos en share de vacantes recientes, y esta es
// Colombia en oct-2022–sep-2023. Superponerlas insinuaría una comparación que
// ni el periodo ni el universo permiten.
interface SerieSpe {
  nombre: string;
  valores: number[];
}
interface TendenciaSpe {
  periodos: string[];
  series: SerieSpe[];
  dimension: string;
  sin_datos: boolean;
}

const DIMENSIONES_SPE: { clave: string; etiqueta: string; singular: string }[] = [
  { clave: 'ocupacion', etiqueta: 'Ocupaciones', singular: 'ocupación' },
  { clave: 'transversal', etiqueta: 'Competencias transversales', singular: 'competencia transversal' },
  { clave: 'digital', etiqueta: 'Competencias digitales', singular: 'competencia digital' },
];

// Orden FIJO de colores de serie: el color sigue al término, no a su ranking.
const CAT_COLORS = [
  'var(--cat-1)',
  'var(--cat-2)',
  'var(--cat-3)',
  'var(--cat-4)',
  'var(--cat-5)',
  'var(--cat-6)',
];
const MAX_SERIES = 6;

// Filas visibles en la tabla de detalle antes de "Ver todos".
const TABLA_LIMITE = 20;

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};

// '2026-06-01' -> 'jun 2026'
function fmtPeriodo(periodo: string): string {
  const [y, m] = periodo.split('-');
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  return `${meses[Number(m) - 1]} ${y}`;
}

// ---------------------------------------------------------------------------
// Demanda actual: top-N (cargos, sectores, empresas, programas) que respetan los
// filtros de esta página (país, programa, seniority). Datos de GET /tendencias/demanda.
// ---------------------------------------------------------------------------
interface ItemDemanda { label: string; count: number; }
interface DemandaResp {
  cargos: ItemDemanda[];
  sectores: ItemDemanda[];
  empresas: ItemDemanda[];
  programas: ItemDemanda[];
  meta: { total: number; paises: string[]; programa: string; seniority: string; escolaridad: string };
}

// Una gráfica de barras horizontal reutilizable para las 4 vistas de demanda.
function GraficaDemanda({
  titulo, descripcion, datos, color, vacio,
}: {
  titulo: string; descripcion: string;
  datos: ItemDemanda[]; color: string; vacio: string;
}) {
  return (
    <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
      <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
        {titulo}
      </h3>
      <p className="text-sm text-zinc-500 mb-4">{descripcion}</p>
      {datos.length === 0 ? (
        <p className="text-center text-zinc-500 py-8">{vacio}</p>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(260, datos.length * 32)}>
          <BarChart data={datos} layout="vertical" margin={{ top: 5, right: 60, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
            <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }} />
            <YAxis dataKey="label" type="category" width={210} interval={0} tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              itemStyle={{ color: 'var(--white-background)' }}
              labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
              formatter={(value) => [`${value}`, 'Vacantes']}
            />
            <Bar dataKey="count" fill={color} radius={[0, 4, 4, 0]} barSize={16} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function TendenciasPage() {
  const [dimension, setDimension] = useState<Dimension>('cargo');
  const [programa, setPrograma] = useState<string>(TODOS);
  const [seniority, setSeniority] = useState<string>(TODOS);
  const [escolaridad, setEscolaridad] = useState<string>(TODOS);
  const [desde, setDesde] = useState<string>('');
  const [hasta, setHasta] = useState<string>('');
  const [topN, setTopN] = useState<number>(15);
  // Países seleccionados (códigos, ej. ['us','gb']). Por defecto TODOS los que
  // tengan datos: la vista arranca combinando todas las fuentes.
  const [paisesSel, setPaisesSel] = useState<string[]>([FUENTE_DEFECTO.pais]);
  const [opciones, setOpciones] = useState<Opciones>({
    programas: [TODOS],
    seniorities: [TODOS],
    escolaridades: [TODOS],
    periodos: [],
    fuentes: [FUENTE_DEFECTO],
  });

  const [data, setData] = useState<TendenciasResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recolectando, setRecolectando] = useState(false);
  const [filtro, setFiltro] = useState<Tendencia | 'todas'>('todas');
  const [seleccionados, setSeleccionados] = useState<string[]>([]);
  // La tabla de detalle muestra solo las primeras filas; el resto se despliega.
  const [tablaExpandida, setTablaExpandida] = useState(false);
  // Demanda actual (4 gráficas top-N), independiente del bloque de tendencias.
  const [demanda, setDemanda] = useState<DemandaResp | null>(null);
  const [demandaLoading, setDemandaLoading] = useState(true);
  // Salario promedio del programa filtrado (GEIH+SPE). Independiente de si la
  // fuente de vacantes ya tiene tendencia madura: el salario sale de otra
  // fuente, así que se muestra aunque arriba salga el aviso "en desarrollo".
  const [salario, setSalario] = useState<SalarioPrograma | null>(null);
  const [salarioLoading, setSalarioLoading] = useState(false);

  const cargar = async (
    dim: Dimension,
    prog: string,
    sen: string,
    d1: string,
    d2: string,
    pais: string[],
  ) => {
    if (pais.length === 0) return; // sin países no hay nada que pedir
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${BACKEND_URL}/tendencias`);
      url.searchParams.set('dimension', dim);
      url.searchParams.set('programa', prog);
      url.searchParams.set('seniority', sen);
      url.searchParams.set('paises', pais.join(','));
      if (d1) url.searchParams.set('desde', d1);
      if (d2) url.searchParams.set('hasta', d2);

      const r = await fetch(url);
      if (!r.ok) throw new Error('No se pudieron cargar las tendencias');
      const d: TendenciasResponse = await r.json();
      setData(d);
      // Preselección: primero los que más crecen (es lo que se viene a ver) y,
      // si no llegan a 4, se completa con los de mayor volumen. Si solo hubiera
      // un término creciente, el gráfico arrancaría con una única línea.
      const entradas = Object.entries(d.terminos || {});
      const crecientes = entradas
        .filter(([, v]) => v.tendencia === 'creciente')
        .sort((a, b) => b[1].score_tendencia - a[1].score_tendencia)
        .map(([k]) => k);
      const porVolumen = entradas
        .sort((a, b) => b[1].total_menciones - a[1].total_menciones)
        .map(([k]) => k);
      const inicial = [...new Set([...crecientes, ...porVolumen])].slice(0, 4);
      setSeleccionados(inicial);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  const recolectar = async () => {
    setRecolectando(true);
    setError(null);
    try {
      const r = await fetch(`${BACKEND_URL}/tendencias/recolectar?meses=24&presupuesto=250`, {
        method: 'POST',
      });
      if (!r.ok) throw new Error('Falló la recolección histórica');
      await cargarOpciones();
      await cargar(dimension, programa, seniority, desde, hasta, paisesSel);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido');
    } finally {
      setRecolectando(false);
    }
  };

  const cargarOpciones = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/tendencias/opciones`);
      if (!r.ok) return;
      const d: Opciones = await r.json();
      setOpciones(d);
      // Arranca con TODAS las fuentes combinadas. Se descartan las que no tienen
      // país (O*NET, informes): colarlas dejaba entradas vacías en `?paises=`.
      const paises = (d.fuentes ?? []).map((f) => f.pais).filter(Boolean);
      if (paises.length) setPaisesSel([...new Set(paises)]);
    } catch {
      // Sin opciones, los selectores quedan solo con 'TODOS': la página sigue usable.
    }
  };

  useEffect(() => {
    cargarOpciones();
  }, []);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargar(dimension, programa, seniority, desde, hasta, paisesSel);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [dimension, programa, seniority, desde, hasta, paisesSel]);

  // Demanda actual: usa los mismos filtros (programa, seniority, países) + Top N.
  // No depende de la dimensión ni del rango de fechas (es una foto, no una serie).
  const cargarDemanda = async (prog: string, sen: string, esc: string, pais: string[], top: number) => {
    if (pais.length === 0) return;
    setDemandaLoading(true);
    // Limpia el dato viejo ANTES de pedir el nuevo: si no, mientras el fetch
    // está en curso (puede tardar) la gráfica sigue mostrando el resultado del
    // filtro anterior sin avisar que está desactualizado — parece que el
    // filtro no aplicó, cuando en realidad solo va lento.
    setDemanda(null);
    try {
      const url = new URL(`${BACKEND_URL}/tendencias/demanda`);
      url.searchParams.set('programa', prog);
      url.searchParams.set('seniority', sen);
      url.searchParams.set('escolaridad', esc);
      url.searchParams.set('paises', pais.join(','));
      url.searchParams.set('top', String(top));
      const r = await fetch(url);
      if (!r.ok) throw new Error('demanda');
      setDemanda(await r.json());
    } catch {
      setDemanda(null);
    } finally {
      setDemandaLoading(false);
    }
  };

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargarDemanda(programa, seniority, escolaridad, paisesSel, topN);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [programa, seniority, escolaridad, paisesSel, topN]);

  // Salario: solo tiene sentido con un programa concreto (el endpoint sin
  // `programa` devuelve un resumen distinto, no un KPI puntual).
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (programa === TODOS) {
      setSalario(null);
      setSalarioLoading(false);
      return;
    }
    let cancelado = false;
    setSalarioLoading(true);
    (async () => {
      try {
        const url = new URL(`${BACKEND_URL}/analytics/salarios`);
        url.searchParams.set('programa', programa);
        url.searchParams.set('paises', paisesSel.join(','));
        const r = await fetch(url);
        const d = r.ok ? await r.json() : null;
        if (!cancelado) setSalario(d);
      } catch {
        if (!cancelado) setSalario(null);
      } finally {
        if (!cancelado) setSalarioLoading(false);
      }
    })();
    return () => { cancelado = true; };
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [programa, paisesSel]);

  // Nombres legibles de las fuentes seleccionadas (para el chat y los textos).
  const etiquetasPaises = opciones.fuentes
    .filter((f) => paisesSel.includes(f.pais))
    .map((f) => f.label)
    .join(', ');

  // Dimensiones que ofrecen las fuentes elegidas: no todas tienen todas.
  // Google Jobs y LinkedIn no dan sector (ninguna entrega categoría
  // estructurada). 'skill' no vive aquí: ver nota en `type Dimension`.
  const dimsDisponibles = useMemo(() => {
    const sel = opciones.fuentes.filter((f) => paisesSel.includes(f.pais));
    const union = new Set<string>();
    sel.forEach((f) => (f.dimensiones ?? ['cargo', 'sector']).forEach((d) => union.add(d)));
    const orden: Dimension[] = ['cargo', 'sector'];
    const disponibles = orden.filter((d) => union.has(d));
    return disponibles.length ? disponibles : (['cargo'] as Dimension[]);
  }, [opciones.fuentes, paisesSel]);

  // Si la dimensión activa deja de estar disponible (p. ej. se quitó la fuente
  // que la aportaba), se vuelve a la primera válida.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!dimsDisponibles.includes(dimension)) setDimension(dimsDisponibles[0]);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [dimsDisponibles, dimension]);

  // ── Puente entre el selector (trabaja con ids) y el estado (códigos de país) ──
  //
  // La API de tendencias se filtra por `paises`, que es lo que entiende el backend.
  // El selector, en cambio, maneja un id por fuente para poder incluir también las
  // que no son vacantes (O*NET, informes PDF). Aquí se traduce en ambos sentidos,
  // así no hace falta tocar el contrato del backend.
  const idDeFuente = (f: { fuente: string; pais?: string | null; id?: string }) =>
    f.id ?? (f.pais ? `${f.fuente}:${f.pais}` : f.fuente);

  const fuentesParaSelector: OpcionSelector[] = useMemo(
    () =>
      opciones.fuentes.map((f) => ({
        id: idDeFuente(f),
        label: f.label,
        pais: f.pais,
        sublabel: (f as { sublabel?: string }).sublabel,
        tipo: ((f as { tipo?: string }).tipo ?? 'vacantes') as OpcionSelector['tipo'],
        naturaleza: (f as { naturaleza?: string }).naturaleza,
        dimensiones: f.dimensiones,
        nota: (f as { sesgos_conocidos?: string }).sesgos_conocidos,
      })),
    [opciones.fuentes],
  );

  const idsFuentesSel = useMemo(
    () => opciones.fuentes.filter((f) => f.pais && paisesSel.includes(f.pais)).map(idDeFuente),
    [opciones.fuentes, paisesSel],
  );

  const alCambiarFuentes = (ids: string[]) => {
    // Solo las fuentes de vacantes aportan país; el resto (O*NET, informes) no
    // participa en esta vista y el selector ya las muestra deshabilitadas.
    const paises = opciones.fuentes
      .filter((f) => f.pais && ids.includes(idDeFuente(f)))
      .map((f) => f.pais);
    if (paises.length > 0) setPaisesSel([...new Set(paises)]);
  };

  // Fuentes seleccionadas que YA tienen historia madura para tendencia (solo
  // Adzuna, por ahora: es la única con backfill real de meses pasados). Sirve
  // para distinguir "sin datos porque falta recolectar" (Adzuna: se puede
  // arreglar con el botón de backfill) de "sin datos porque la fuente es nueva
  // y todavía no acumula suficiente historia mensual" (Google Jobs, LinkedIn:
  // no hay botón que lo arregle, solo tiempo y recolecciones periódicas).
  const soloFuentesEnDesarrollo = useMemo(() => {
    const sel = opciones.fuentes.filter((f) => f.pais && paisesSel.includes(f.pais));
    return sel.length > 0 && sel.every((f) => f.fuente !== 'adzuna');
  }, [opciones.fuentes, paisesSel]);

  const terminos = useMemo(() => data?.terminos ?? {}, [data]);
  const periodos = useMemo(() => data?.meta.periodos ?? [], [data]);

  // Términos filtrados y ordenados por fuerza de la señal.
  const listaFiltrada = useMemo(() => {
    return Object.entries(terminos)
      .filter(([, v]) => filtro === 'todas' || v.tendencia === filtro)
      .sort((a, b) => b[1].score_tendencia - a[1].score_tendencia);
  }, [terminos, filtro]);

  // Insights: los 5 con más fuerza de señal en cada dirección. Se calculan aquí
  // y no se leen de `data.insights` porque esa carga trae solo 3 y el conteo lo
  // decide la vista, no el backend.
  const TOP_INSIGHT = 5;
  const porTendencia = useMemo(() => {
    const orden = (t: Tendencia) =>
      Object.entries(terminos)
        .filter(([, v]) => v.tendencia === t)
        .sort((a, b) => b[1].score_tendencia - a[1].score_tendencia);
    const crecientes = orden('creciente');
    const decrecientes = orden('decreciente');
    return {
      crecientes: { total: crecientes.length, top: crecientes.slice(0, TOP_INSIGHT) },
      decrecientes: { total: decrecientes.length, top: decrecientes.slice(0, TOP_INSIGHT) },
    };
  }, [terminos]);

  // Al cambiar los datos o el filtro, la tabla vuelve a colapsarse a 20 filas.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setTablaExpandida(false);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [listaFiltrada]);

  // Tabla de detalle: se muestran TABLA_LIMITE filas y el resto se despliega.
  const filasTabla = tablaExpandida ? listaFiltrada : listaFiltrada.slice(0, TABLA_LIMITE);
  const ocultas = listaFiltrada.length - filasTabla.length;

  // Barras: top N por score.
  const datosBarras = useMemo(
    () =>
      listaFiltrada.slice(0, topN).map(([nombre, v]) => ({
        nombre,
        score: Number(v.score_tendencia.toFixed(3)),
        tendencia: v.tendencia,
      })),
    [listaFiltrada, topN],
  );

  // Dona: reparto de tendencias.
  const datosDona = useMemo(() => {
    if (!data) return [];
    return (
      [
        { tendencia: 'creciente' as Tendencia, valor: data.meta.crecientes },
        { tendencia: 'estable' as Tendencia, valor: data.meta.estables },
        { tendencia: 'decreciente' as Tendencia, valor: data.meta.decrecientes },
      ] as const
    )
      .filter((d) => d.valor > 0)
      .map((d) => ({ nombre: ETIQUETA[d.tendencia], valor: d.valor, tendencia: d.tendencia }));
  }, [data]);

  // Evolución: una fila por periodo, una columna por término seleccionado.
  const datosEvolucion = useMemo(() => {
    return periodos.map((p) => {
      const fila: Record<string, string | number> = { periodo: fmtPeriodo(p) };
      seleccionados.forEach((t) => {
        const punto = terminos[t]?.historial?.[p];
        // share en % para que el eje sea legible
        fila[t] = punto ? Number((punto.share * 100).toFixed(2)) : 0;
      });
      return fila;
    });
  }, [periodos, seleccionados, terminos]);

  const alternarSerie = (nombre: string) => {
    setSeleccionados((prev) =>
      prev.includes(nombre)
        ? prev.filter((x) => x !== nombre)
        : prev.length < MAX_SERIES
          ? [...prev, nombre]
          : prev,
    );
  };

  // Color estable por término: depende del índice en `seleccionados`, que solo
  // cambia al añadir/quitar esa serie concreta.
  const colorDeSerie = (nombre: string) => CAT_COLORS[seleccionados.indexOf(nombre) % CAT_COLORS.length];

  // ── Serie mensual del SPE ────────────────────────────────────────────────
  // Independiente de los filtros de arriba: el SPE no se cruza con programa ni
  // seniority, y su periodo es fijo. Tiene su propio selector de dimensión.
  const [dimSpe, setDimSpe] = useState<string>('ocupacion');
  // 'share' normaliza cada mes a 100. Es el modo por defecto porque en
  // volumen absoluto TODAS las series caen en diciembre a la vez: lo que se ve
  // es la estacionalidad del mercado, no el comportamiento de cada término.
  const [modoSpe, setModoSpe] = useState<'share' | 'volumen'>('share');
  const [tendSpe, setTendSpe] = useState<TendenciaSpe | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/spe/tendencias?dimension=${dimSpe}&top=6`);
        const d: TendenciaSpe | null = r.ok ? await r.json() : null;
        setTendSpe(d && !d.sin_datos ? d : null);
      } catch {
        setTendSpe(null);
      }
    })();
  }, [dimSpe]);

  // Formato ancho para recharts. En modo 'share' cada mes se divide entre el
  // total de ESE mes (solo de las series mostradas), que es lo que permite ver
  // si un término gana o pierde terreno con independencia del volumen.
  const datosSpe = useMemo(() => {
    if (!tendSpe) return [];
    return tendSpe.periodos.map((p, i) => {
      const fila: Record<string, string | number> = { periodo: fmtPeriodo(p) };
      const totalMes = tendSpe.series.reduce((acc, s) => acc + (s.valores[i] ?? 0), 0);
      tendSpe.series.forEach((s) => {
        const v = s.valores[i] ?? 0;
        fila[s.nombre] =
          modoSpe === 'share'
            ? totalMes > 0 ? Number(((v / totalMes) * 100).toFixed(2)) : 0
            : v;
      });
      return fila;
    });
  }, [tendSpe, modoSpe]);

  const colorSpe = (nombre: string) =>
    CAT_COLORS[(tendSpe?.series.findIndex((s) => s.nombre === nombre) ?? 0) % CAT_COLORS.length];

  const estiloSelect = {
    backgroundColor: 'var(--sabana-sky-blue)',
    color: 'var(--sabana-dark-navy)',
    borderColor: 'var(--sabana-light-blue)',
  };
  const claseSelect = 'rounded-lg px-3 py-2 text-sm font-semibold border cursor-pointer w-full';
  // Altura fija + alineado abajo: aunque una etiqueta ocupe 2 líneas (p. ej.
  // "Nivel de experiencia"), todos los selects arrancan a la misma altura.
  const claseEtiqueta =
    'flex items-end min-h-[2.1rem] text-xs font-bold uppercase tracking-wide leading-tight mb-1';

  const hayFiltros =
    programa !== TODOS || seniority !== TODOS || escolaridad !== TODOS || !!desde || !!hasta;

  const limpiarFiltros = () => {
    setPrograma(TODOS);
    setSeniority(TODOS);
    setEscolaridad(TODOS);
    setDesde('');
    setHasta('');
  };

  // Barra de filtros: una sola fila por encima de los gráficos.
  const selector = (
    <div
      className="mb-6 rounded-lg p-4 border"
      style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--white-background)' }}
    >
      {/* Fuentes de datos: desplegable con checkboxes. Contexto global del análisis. */}
      <div className="mb-3 pb-3 border-b" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
        <div className="max-w-md">
          <SelectorFuentes
            fuentes={fuentesParaSelector}
            seleccionadas={idsFuentesSel}
            onChange={alCambiarFuentes}
            dimensionActiva={dimension}
          />
        </div>

        {paisesSel.length > 1 && (
          <p className="text-xs text-zinc-400 mt-2">
            ⓘ Al combinar mercados, todos pesan igual. No se suman volúmenes: EE.UU. concentra el
            ~93% y haría invisibles a los mercados pequeños.
          </p>
        )}
      </div>

      {/* Filtros distribuidos por peso: programa (el más largo) recibe más ancho;
          en pantallas estrechas se envuelven gracias a flex-wrap + min-width. */}
      <div className="flex flex-wrap gap-3">
        <div className="flex-1 min-w-[130px]">
          <label htmlFor="f-dim" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Analizar por
          </label>
          <select
            id="f-dim"
            value={dimension}
            onChange={(e) => setDimension(e.target.value as Dimension)}
            className={claseSelect}
            style={estiloSelect}
          >
            {dimsDisponibles.map((k) => (
              <option key={k} value={k}>
                {DIMENSIONES[k].label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-[2.5] min-w-[220px]">
          <label htmlFor="f-prog" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Programa académico
          </label>
          <select
            id="f-prog"
            value={programa}
            onChange={(e) => setPrograma(e.target.value)}
            className={claseSelect}
            style={estiloSelect}
          >
            {opciones.programas.map((p) => (
              <option key={p} value={p}>
                {p === TODOS ? 'Todos los programas' : p}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-[1.3] min-w-[150px]">
          <label htmlFor="f-sen" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Nivel de experiencia
          </label>
          <select
            id="f-sen"
            value={seniority}
            onChange={(e) => setSeniority(e.target.value)}
            className={claseSelect}
            style={estiloSelect}
          >
            {opciones.seniorities.map((s) => (
              <option key={s} value={s}>
                {SENIORITY_LABEL[s] ?? s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-[1.6] min-w-[190px]">
          <label htmlFor="f-esc" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Nivel de escolaridad
          </label>
          <select
            id="f-esc"
            value={escolaridad}
            onChange={(e) => setEscolaridad(e.target.value)}
            className={claseSelect}
            style={estiloSelect}
          >
            {opciones.escolaridades.map((s) => (
              <option key={s} value={s}>
                {ESCOLARIDAD_LABEL[s] ?? s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[120px]">
          <label htmlFor="f-desde" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Desde
          </label>
          <select
            id="f-desde"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className={claseSelect}
            style={estiloSelect}
          >
            <option value="">Inicio</option>
            {opciones.periodos
              .filter((p) => !hasta || p <= hasta)
              .map((p) => (
                <option key={p} value={p}>
                  {fmtPeriodo(p)}
                </option>
              ))}
          </select>
        </div>

        <div className="flex-1 min-w-[120px]">
          <label htmlFor="f-hasta" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Hasta
          </label>
          <select
            id="f-hasta"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className={claseSelect}
            style={estiloSelect}
          >
            <option value="">Actualidad</option>
            {opciones.periodos
              .filter((p) => !desde || p >= desde)
              .map((p) => (
                <option key={p} value={p}>
                  {fmtPeriodo(p)}
                </option>
              ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 mt-4">
        <div className="flex items-center gap-2">
          <label htmlFor="f-top" className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>
            Top N
          </label>
          <input
            id="f-top"
            type="range"
            min={5}
            max={40}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
            className="cursor-pointer"
          />
          <span className="text-sm font-bold w-8" style={{ color: 'var(--sabana-dark-navy)' }}>
            {topN}
          </span>
        </div>

        {hayFiltros && (
          <button
            onClick={limpiarFiltros}
            className="text-xs font-semibold underline cursor-pointer"
            style={{ color: 'var(--sabana-navy)' }}
          >
            Limpiar filtros
          </button>
        )}
      </div>
    </div>
  );

  const contextoChat = data
    ? `Página de Tendencias del mercado laboral. Fuentes analizadas: ${etiquetasPaises}` +
      `${paisesSel.length > 1 ? ' (combinadas dando el mismo peso a cada mercado, no sumando volúmenes)' : ''}. ` +
      `Se analizan ${DIMENSIONES[dimension].label.toLowerCase()}. ` +
      `Se analizaron ${data.meta.total_terminos} ${DIMENSIONES[dimension].singular}s a lo largo de ${periodos.length} meses ` +
      `(${periodos.length ? `${fmtPeriodo(periodos[0])} a ${fmtPeriodo(periodos[periodos.length - 1])}` : 'sin datos'}). ` +
      `Crecientes: ${data.meta.crecientes}. Estables: ${data.meta.estables}. Decrecientes: ${data.meta.decrecientes}. ` +
      `La tendencia se mide sobre la proporción de vacantes de cada mes (no sobre el conteo absoluto, porque cada mes ` +
      `se muestrea con distinto número de vacantes) mediante una regresión lineal ponderada que da más peso a los meses ` +
      `recientes. El "score" resume la fuerza de esa señal, de 0 a 1.\n\n` +
      `Top crecientes: ${listaFiltrada
        .filter(([, v]) => v.tendencia === 'creciente')
        .slice(0, 8)
        .map(([n, v]) => `${n} (score ${v.score_tendencia})`)
        .join('; ') || 'ninguno'}.\n` +
      `Top decrecientes: ${Object.entries(terminos)
        .filter(([, v]) => v.tendencia === 'decreciente')
        .sort((a, b) => b[1].score_tendencia - a[1].score_tendencia)
        .slice(0, 8)
        .map(([n, v]) => `${n} (score ${v.score_tendencia})`)
        .join('; ') || 'ninguno'}.`
    : 'Página de tendencias temporales del mercado laboral.';

  // -------------------------------------------------------------------------
  // Estados de carga / error / vacío
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <PageLayout title={DIMENSIONES[dimension].titulo}>
        {selector}
        <Spinner label="Cargando tendencias..." />
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title={DIMENSIONES[dimension].titulo}>
        {selector}
        <div className="bg-red-100 rounded-lg p-6">
          <p className="text-red-700">{error}</p>
          <button
            onClick={() => cargar(dimension, programa, seniority, desde, hasta, paisesSel)}
            className="mt-4 px-4 py-2 rounded-lg font-semibold"
            style={{ backgroundColor: 'var(--sabana-light-blue)', color: 'white' }}
          >
            Reintentar
          </button>
        </div>
      </PageLayout>
    );
  }

  // Antes esto era un `return` que vaciaba TODA la página (incluida "Demanda
  // actual", que no depende de esta tendencia y sí tiene datos reales para
  // Google Jobs/LinkedIn). Ahora solo controla las secciones que de verdad
  // necesitan la serie temporal: KPIs, insights, evolución y tabla. Ver más
  // abajo dónde se usa.
  const hayTendencia = !!data && !data.meta.sin_datos && data.meta.total_terminos > 0;

  // -------------------------------------------------------------------------
  // Vista principal
  // -------------------------------------------------------------------------

  return (
    <>
      <PageLayout title={DIMENSIONES[dimension].titulo}>
        {selector}

        {/* ---------------- Salario del programa filtrado ----------------
            Independiente de si arriba hay tendencia madura: el salario sale
            de GEIH+SPE, no de la fuente de vacantes que se esté mirando. Solo
            aplica con UN programa elegido — el resumen sin programa no trae
            un KPI puntual, trae un panorama distinto. */}
        {programa !== TODOS && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <div
              className="rounded-lg p-5 bg-white dark:bg-zinc-800 shadow border-l-4"
              style={{ borderColor: 'var(--sabana-navy)' }}
            >
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>
                Salario promedio (GEIH) — {programa}
              </p>
              {salarioLoading ? (
                <Spinner size="sm" compact label="Cargando..." />
              ) : salario?.tiene_geih && salario.kpis ? (
                <>
                  <p className="text-3xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {salario.kpis.media.toLocaleString('es-CO', {
                      style: 'currency',
                      currency: 'COP',
                      maximumFractionDigits: 0,
                    })}
                  </p>
                  <p className="text-xs mt-1 text-zinc-500">
                    Mensual · GEIH (DANE), muestra de {salario.kpis.n.toLocaleString('es-CO')} personas del gran
                    grupo ocupacional asociado.
                  </p>
                </>
              ) : (
                <p className="text-sm text-zinc-500 mt-2">
                  Sin datos salariales resolubles para este programa todavía.
                </p>
              )}
            </div>

            {/* Promedio de las vacantes de Adzuna realmente seleccionadas arriba,
                convertido a COP con la TRM del día. Solo Adzuna (us/gb/ca/mx/es)
                trae salario estructurado — Google Jobs y LinkedIn no aportan
                aquí aunque estén marcados en el selector de fuentes. */}
            <div
              className="rounded-lg p-5 bg-white dark:bg-zinc-800 shadow border-l-4"
              style={{ borderColor: 'var(--sabana-light-blue)' }}
            >
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>
                Salario de las vacantes seleccionadas — {programa}
              </p>
              {salarioLoading ? (
                <Spinner size="sm" compact label="Cargando..." />
              ) : salario?.salario_vacantes?.disponible ? (
                <>
                  <p className="text-3xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {salario.salario_vacantes.media_cop!.toLocaleString('es-CO', {
                      style: 'currency',
                      currency: 'COP',
                      maximumFractionDigits: 0,
                    })}
                  </p>
                  <p className="text-xs mt-1 text-zinc-500">
                    Mensual · {salario.salario_vacantes.n} vacantes de Adzuna ({salario.salario_vacantes.paises?.join(', ')}),
                    convertido a COP con la TRM del {salario.salario_vacantes.trm_fecha}.
                  </p>
                </>
              ) : (
                <p className="text-sm text-zinc-500 mt-2">
                  Sin salario disponible: selecciona alguna fuente de Adzuna (EE.UU., Reino Unido, Canadá,
                  México o España) — Google Jobs y LinkedIn no traen salario estructurado.
                </p>
              )}
            </div>
          </div>
        )}

        {/* ---------------- KPIs ---------------- */}
        {hayTendencia && data && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            {/* Volumen crudo detrás del análisis. Va primero porque es la cifra
                que da escala: los "cargos con tendencia" de al lado son solo
                los que tuvieron suficiente historia mensual para calcularla —
                todas las vacantes recolectadas se normalizan/agrupan igual,
                sean o no suficientes para una tendencia. */}
            <div className="rounded-lg p-5" style={{ backgroundColor: 'var(--sabana-sky-blue)' }}>
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>
                Vacantes analizadas
              </p>
              <p className="text-3xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                {demanda ? demanda.meta.total.toLocaleString('es-CO') : '—'}
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--sabana-navy)' }}>
                ofertas recolectadas
              </p>
            </div>

            <div className="rounded-lg p-5" style={{ backgroundColor: 'var(--sabana-sky-blue)' }}>
              <p className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>
                {DIMENSIONES[dimension].singular}s con tendencia
              </p>
              <p className="text-3xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                {data.meta.total_terminos}
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--sabana-navy)' }}>
                con suficiente historia en {periodos.length} meses
              </p>
            </div>

            {(['creciente', 'estable', 'decreciente'] as Tendencia[]).map((t) => {
              const valor =
                t === 'creciente' ? data.meta.crecientes : t === 'estable' ? data.meta.estables : data.meta.decrecientes;
              const porc = data.meta.total_terminos ? (valor / data.meta.total_terminos) * 100 : 0;
              return (
                <div
                  key={t}
                  className="rounded-lg p-5 bg-white dark:bg-zinc-800 shadow border-l-4"
                  style={{ borderColor: COLOR_TENDENCIA[t] }}
                >
                  <p className="text-xs font-bold uppercase tracking-wide flex items-center gap-1" style={{ color: 'var(--sabana-navy)' }}>
                    <span style={{ color: COLOR_TENDENCIA[t] }}>{SIMBOLO[t]}</span> {ETIQUETA[t]}s
                  </p>
                  <p className="text-3xl font-bold mt-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {valor}
                  </p>
                  <p className="text-xs mt-1 text-zinc-500">{porc.toFixed(0)}% del total</p>
                </div>
              );
            })}
          </div>
        )}

        {/* ---------------- Demanda actual ----------------
            Con "Todos los programas" se muestran las 4 gráficas: son un buen
            panorama general. Al filtrar a UN programa, "Empresas" y sobre todo
            "Programas académicos" pierden sentido (esta última mostraría casi
            un solo programa), así que se reemplazan por una sola gráfica —
            Cargos o Sectores, la que coincida con "Analizar por" de arriba—
            para no repetir prácticamente la misma pregunta cuatro veces. */}
        <div className="mb-4">
          <h2 className="text-2xl font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
            Demanda actual
          </h2>
          <p className="text-sm text-zinc-500">
            {dimension === 'sector'
              ? 'Los sectores con más vacantes en la muestra, según los filtros de arriba (país, programa, nivel de experiencia y nivel de escolaridad). El nivel de escolaridad solo afecta esta sección, no la tendencia temporal de arriba.'
              : 'Los cargos con más vacantes en la muestra, según los filtros de arriba (país, programa, nivel de experiencia y nivel de escolaridad). El nivel de escolaridad solo afecta esta sección, no la tendencia temporal de arriba.'}
            {programa === TODOS ? ' Incluye además empresas y programas académicos.' : ''}
            {demanda ? ` Basado en ${demanda.meta.total.toLocaleString('es-CO')} vacantes.` : ''}
          </p>
        </div>

        {demandaLoading && !demanda ? (
          <Spinner label="Cargando demanda..." />
        ) : (
          <div className="space-y-6 mb-10">
            {dimension === 'cargo' && (
              <GraficaDemanda
                titulo="Cargos más demandados"
                descripcion="Títulos de cargo con mayor número de vacantes."
                datos={demanda?.cargos ?? []} color="var(--sabana-dark-navy)"
                vacio="No hay cargos con ese filtro."
              />
            )}
            {dimension === 'sector' && (
              <GraficaDemanda
                titulo="Sectores con mayor actividad de contratación"
                descripcion="Sectores económicos que más contratan (Adzuna; Google Jobs no aporta sector)."
                datos={demanda?.sectores ?? []} color="var(--sabana-navy)"
                vacio="No hay datos de sector para la selección (Google Jobs no trae sector)."
              />
            )}
            {programa === TODOS && (
              <>
                <GraficaDemanda
                  titulo="Empresas con mayor actividad de contratación"
                  descripcion="Empleadores con más vacantes publicadas."
                  datos={demanda?.empresas ?? []} color="var(--sabana-light-blue)"
                  vacio="No hay empresas con ese filtro."
                />
                <GraficaDemanda
                  titulo="Programas académicos relacionados con mayor demanda"
                  descripcion="Programas de La Sabana asociados a más vacantes."
                  datos={demanda?.programas ?? []} color="var(--sabana-navy)"
                  vacio="No hay programas con ese filtro."
                />
              </>
            )}
          </div>
        )}

        {/* ---------------- Aviso: fuente en desarrollo ----------------
            Reemplaza a KPIs/insights/evolución/tabla cuando la fuente elegida
            no tiene (todavía) suficiente historia mensual para una tendencia
            confiable. "Demanda actual" arriba SÍ tiene datos reales de esta
            fuente — por eso ya no se oculta la página entera: se explica por
            qué esta parte en concreto está vacía, sin fingir que no hay nada. */}
        {!hayTendencia && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-8 shadow text-center space-y-3 mb-10">
            {soloFuentesEnDesarrollo ? (
              <>
                <p className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
                  Esta fuente está en desarrollo
                </p>
                <p className="text-sm text-zinc-500 max-w-2xl mx-auto">
                  La demanda actual de arriba <b>sí es real</b> y viene de esta fuente. Lo que falta es
                  la <b>tendencia en el tiempo</b> (creciente/estable/decreciente): para calcularla con
                  confianza se necesitan al menos 3 meses con volumen suficiente, y esta fuente todavía
                  no los acumula. No es un error — es una fuente nueva que se sigue robusteciendo con
                  cada recolección periódica.
                </p>

                {/* Mientras no hay tendencia, mostrar al menos un ranking simple:
                    los cargos que más se repiten en lo ya recolectado (sin serie
                    de tiempo, solo conteo). Reusa `demanda`, que ya viene cargado
                    independientemente de este bloque. */}
                {demanda && demanda.cargos.length > 0 && (
                  <div className="max-w-md mx-auto text-left pt-2">
                    <p className="text-xs font-bold uppercase tracking-wide mb-2 text-center" style={{ color: 'var(--sabana-navy)' }}>
                      Top 10 cargos más encontrados
                    </p>
                    <table className="w-full text-sm">
                      <tbody>
                        {demanda.cargos.slice(0, 10).map((c, i) => (
                          <tr key={c.label} style={{ backgroundColor: i % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                            <td className="px-3 py-1.5 text-right font-semibold w-8" style={{ color: 'var(--sabana-navy)' }}>
                              {i + 1}.
                            </td>
                            <td className="px-3 py-1.5" style={{ color: 'var(--sabana-dark-navy)' }}>
                              {c.label}
                            </td>
                            <td className="px-3 py-1.5 text-right tabular-nums text-zinc-500">
                              {c.count.toLocaleString('es-CO')} vac.
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
                  Todavía no hay historia suficiente para calcular tendencias.
                </p>
                <p className="text-sm text-zinc-500 max-w-2xl mx-auto">
                  Una tendencia necesita varios meses de vacantes con su fecha de publicación real. El
                  botón de abajo muestrea los últimos 24 meses en Adzuna (unas 250 llamadas) y calcula
                  la serie. Se puede repetir sin duplicar datos.
                </p>
                <button
                  onClick={recolectar}
                  disabled={recolectando}
                  className="px-6 py-2 rounded-lg font-semibold disabled:opacity-60"
                  style={{ backgroundColor: 'var(--sabana-navy)', color: 'white', cursor: 'pointer' }}
                >
                  {recolectando ? 'Recolectando histórico...' : 'Recolectar histórico (24 meses)'}
                </button>
              </>
            )}
          </div>
        )}

        {hayTendencia && data && (
          <>
        {/* ---------------- Insights destacados ----------------
            Portadas del dashboard de Reto-Alumni, donde hablaban de "skills".
            Aquí van sobre cargos/sectores, que es lo que Adzuna soporta: sus
            descripciones vienen truncadas a 500 caracteres y no permiten
            extraer competencias (ver README §9.7). */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {([
            {
              clave: 'creciente' as Tendencia,
              titulo: `${DIMENSIONES[dimension].singular === 'cargo' ? 'Cargo' : 'Sector'}s crecientes`,
              datos: porTendencia.crecientes,
              color: 'var(--trend-up)',
              glosa: 'con tendencia al alza en el mercado laboral actual.',
              vacio: `Ningún ${DIMENSIONES[dimension].singular} crece de forma destacada bajo los filtros actuales.`,
            },
            {
              clave: 'decreciente' as Tendencia,
              titulo: `${DIMENSIONES[dimension].singular === 'cargo' ? 'Cargo' : 'Sector'}s en decrecimiento`,
              datos: porTendencia.decrecientes,
              color: 'var(--trend-down)',
              glosa: 'con tendencia a la baja en el mercado laboral actual.',
              vacio: `Ningún ${DIMENSIONES[dimension].singular} decrece de forma destacada bajo los filtros actuales.`,
            },
          ]).map((c) => (
            <div
              key={c.clave}
              className="rounded-lg p-5 bg-white dark:bg-zinc-800 shadow border-l-4"
              style={{ borderColor: c.color }}
            >
              <p className="text-sm font-bold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                {c.titulo}
              </p>
              {c.datos.total === 0 ? (
                <p className="text-sm text-zinc-500">{c.vacio}</p>
              ) : (
                <>
                  <p className="text-sm text-zinc-600 dark:text-zinc-300">
                    <strong style={{ color: c.color }}>{c.datos.total}</strong>{' '}
                    {DIMENSIONES[dimension].singular}
                    {c.datos.total === 1 ? '' : 's'} {c.glosa}
                  </p>
                  <ol className="mt-2 space-y-0.5 text-xs text-zinc-500">
                    {c.datos.top.map(([nombre], i) => (
                      <li key={nombre} className="flex items-baseline gap-1.5">
                        <span className="font-semibold" style={{ color: c.color }}>
                          {i + 1}.
                        </span>
                        <span className="flex-1 min-w-0 truncate" style={{ color: 'var(--sabana-dark-navy)' }}>
                          {nombre}
                        </span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </div>
          ))}
        </div>

            

        {/* ---------------- Filtro ---------------- */}
        <div className="flex flex-wrap gap-2 mb-6">
          {(['todas', 'creciente', 'estable', 'decreciente'] as const).map((f) => {
            const activo = filtro === f;
            return (
              <button
                key={f}
                onClick={() => setFiltro(f)}
                className="px-4 py-1.5 rounded-full text-sm font-semibold border transition-colors cursor-pointer"
                style={{
                  backgroundColor: activo ? 'var(--sabana-dark-navy)' : 'transparent',
                  color: activo ? 'white' : 'var(--sabana-dark-navy)',
                  borderColor: f === 'todas' ? 'var(--sabana-light-blue)' : COLOR_TENDENCIA[f],
                }}
              >
                {f === 'todas' ? 'Todas' : `${SIMBOLO[f]} ${ETIQUETA[f]}s`}
              </button>
            );
          })}
        </div>

        {/* ---------------- Barras: fuerza de la señal ---------------- */}
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow mb-8">
          <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
            Crecimiento de vacantes
          </h3>
          <p className="text-sm text-zinc-500 mb-4">
            
          </p>
          {datosBarras.length === 0 ? (
            <p className="text-center text-zinc-500 py-8">No hay {DIMENSIONES[dimension].singular}s con ese filtro.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(280, datosBarras.length * 34)}>
              <BarChart data={datosBarras} layout="vertical" margin={{ top: 5, right: 60, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
                <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }} />
                <YAxis
                  dataKey="nombre"
                  type="category"
                  width={210}
                  interval={0}
                  tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={{ color: 'var(--white-background)' }}
                  labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
                  formatter={(value, _n, props) => [
                    `score ${value} · ${ETIQUETA[props.payload.tendencia as Tendencia]}`,
                    'Tendencia',
                  ]}
                />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={16}>
                  {datosBarras.map((d) => (
                    <Cell key={d.nombre} fill={COLOR_TENDENCIA[d.tendencia as Tendencia]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {/* Leyenda explícita: la identidad no puede depender solo del color. */}
          <div className="flex flex-wrap gap-4 mt-4 justify-center">
            {(['creciente', 'estable', 'decreciente'] as Tendencia[]).map((t) => (
              <span key={t} className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--sabana-black-70)' }}>
                <span style={{ color: COLOR_TENDENCIA[t] }}>{SIMBOLO[t]}</span>
                {ETIQUETA[t]}
              </span>
            ))}
          </div>
        </div>


        {/* ---------------- Evolución temporal ---------------- */}
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow mb-8">
          <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
            Evolución temporal
          </h3>
          <p className="text-sm text-zinc-500 mb-4">
            % de las vacantes de cada mes. Elige hasta {MAX_SERIES} {DIMENSIONES[dimension].singular}s para comparar.
          </p>

          <div className="flex flex-wrap gap-2 mb-5">
            {listaFiltrada.slice(0, 18).map(([nombre]) => {
              const activo = seleccionados.includes(nombre);
              const lleno = !activo && seleccionados.length >= MAX_SERIES;
              return (
                <button
                  key={nombre}
                  onClick={() => alternarSerie(nombre)}
                  disabled={lleno}
                  className="px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                  style={{
                    backgroundColor: activo ? colorDeSerie(nombre) : 'transparent',
                    color: activo ? 'white' : 'var(--sabana-dark-navy)',
                    borderColor: activo ? colorDeSerie(nombre) : 'var(--sabana-light-blue)',
                  }}
                >
                  {nombre}
                </button>
              );
            })}
          </div>

          {seleccionados.length === 0 ? (
            <p className="text-center text-zinc-500 py-8">Selecciona al menos un {DIMENSIONES[dimension].singular}.</p>
          ) : (
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={datosEvolucion} margin={{ top: 5, right: 20, left: 0, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="periodo"
                  tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }}
                  angle={-40}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }}
                  tickFormatter={(v) => `${v}%`}
                  label={{
                    value: '% de vacantes del mes',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 11, fill: 'var(--sabana-black-70)' },
                  }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={{ color: 'var(--white-background)' }}
                  labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
                  formatter={(value, name) => [`${value}%`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                {seleccionados.map((nombre) => (
                  <Line
                    key={nombre}
                    type="monotone"
                    dataKey={nombre}
                    stroke={colorDeSerie(nombre)}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 6 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ---------------- Serie mensual del SPE (Colombia) ----------------
            Aparte de la gráfica de arriba a propósito: aquella son mercados
            extranjeros (Adzuna) en su periodo reciente y esta es Colombia en
            oct-2022–sep-2023. Ponerlas juntas insinuaría una comparación que ni
            el periodo ni el universo medido permiten. */}
        {tendSpe && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow mb-8">
            <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              Serie mensual del SPE — Colombia
            </h3>
            <p className="text-sm text-zinc-500 mb-4">
              La única tendencia <b>observada en Colombia</b> del Observatorio: las demás vienen de
              mercados extranjeros o se derivan de O*NET. Son vacantes registradas por el Servicio
              Público de Empleo entre <b>{fmtPeriodo(tendSpe.periodos[0])}</b> y{' '}
              <b>{fmtPeriodo(tendSpe.periodos[tendSpe.periodos.length - 1])}</b>.
            </p>

            <div className="flex flex-wrap gap-4 items-end mb-5">
              <div>
                <label htmlFor="spe-dim" className="block text-xs font-bold uppercase tracking-wide mb-1"
                  style={{ color: 'var(--sabana-navy)' }}>
                  Qué medir
                </label>
                <select
                  id="spe-dim"
                  value={dimSpe}
                  onChange={(e) => setDimSpe(e.target.value)}
                  className={claseSelect}
                  style={estiloSelect}
                >
                  {DIMENSIONES_SPE.map((d) => (
                    <option key={d.clave} value={d.clave}>{d.etiqueta}</option>
                  ))}
                </select>
              </div>

              <div>
                <span className="block text-xs font-bold uppercase tracking-wide mb-1"
                  style={{ color: 'var(--sabana-navy)' }}>
                  Cómo verlo
                </span>
                <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                  {([['share', 'Participación'], ['volumen', 'Volumen']] as const).map(([k, txt]) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setModoSpe(k)}
                      className="px-3 py-2 text-sm font-semibold cursor-pointer"
                      style={{
                        backgroundColor: modoSpe === k ? 'var(--sabana-dark-navy)' : 'var(--sabana-sky-blue)',
                        color: modoSpe === k ? 'var(--white-background)' : 'var(--sabana-dark-navy)',
                      }}
                    >
                      {txt}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <p className="text-sm text-zinc-500 mb-3">
              {modoSpe === 'share' ? (
                <>
                  Peso de cada {DIMENSIONES_SPE.find((d) => d.clave === dimSpe)?.singular}{' '}
                  sobre el total del mes. <b>Es la vista que informa</b>: en volumen absoluto todas las
                  series suben y bajan a la vez siguiendo el ciclo del mercado, y esa forma compartida
                  tapa lo único interesante —quién gana y quién pierde terreno—.
                </>
              ) : (
                <>
                  Menciones absolutas por mes. Útil para ver la escala real y la estacionalidad (la
                  caída de diciembre es del mercado entero, no de un término concreto), pero{' '}
                  <b>no sirve para comparar entre términos</b>: los de mayor volumen aplastan al resto.
                </>
              )}
            </p>

            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={datosSpe} margin={{ top: 5, right: 20, left: 0, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="periodo"
                  tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }}
                  angle={-40}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }}
                  tickFormatter={(v) =>
                    modoSpe === 'share' ? `${v}%` : `${Math.round((v as number) / 1000)}k`
                  }
                  label={{
                    value: modoSpe === 'share' ? '% del total del mes' : 'menciones en vacantes',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 11, fill: 'var(--sabana-black-70)' },
                  }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={{ color: 'var(--white-background)' }}
                  labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
                  formatter={(value, name) => [
                    modoSpe === 'share'
                      ? `${value}%`
                      : (value as number).toLocaleString('es-CO'),
                    name,
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                {tendSpe.series.map((s) => (
                  <Line
                    key={s.nombre}
                    type="monotone"
                    dataKey={s.nombre}
                    stroke={colorSpe(s.nombre)}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 6 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>

            <p className="text-xs text-zinc-400 mt-3">
              Se muestran las 6 series de mayor volumen para que la gráfica siga siendo legible.
              Los anexos publicados del SPE llegan hasta sep-2023: la serie <b>no está al día</b> y
              se actualiza a mano cuando el SPE publica un nuevo corte.
            </p>
          </div>
        )}

        {/* ---------------- Tabla ---------------- */}
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
          <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
            Detalle
          </h3>
          <p className="text-sm text-zinc-500 mb-4">
            Vista de tabla de los mismos datos de los gráficos
            {listaFiltrada.length > TABLA_LIMITE && !tablaExpandida
              ? ` (mostrando ${filasTabla.length} de ${listaFiltrada.length})`
              : ` (${listaFiltrada.length} filas)`}
            .
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                  <th className="text-left px-3 py-2 font-semibold">{DIMENSIONES[dimension].singular}</th>
                  <th className="text-left px-3 py-2 font-semibold">Tendencia</th>
                  <th className="text-right px-3 py-2 font-semibold">Vacantes</th>
                  <th className="text-right px-3 py-2 font-semibold">Meses</th>
                </tr>
              </thead>
              <tbody>
                {filasTabla.map(([nombre, v], i) => (
                  <tr key={nombre} style={{ backgroundColor: i % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                    <td className="px-3 py-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {nombre}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className="inline-flex items-center gap-1 font-semibold"
                        style={{ color: COLOR_TENDENCIA[v.tendencia] }}
                      >
                        {SIMBOLO[v.tendencia]} {ETIQUETA[v.tendencia]}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {v.total_menciones}
                    </td>
                    <td className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {v.periodos_cubiertos}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {listaFiltrada.length > TABLA_LIMITE && (
            <div className="flex justify-center mt-4">
              <button
                onClick={() => setTablaExpandida((v) => !v)}
                className="px-4 py-2 rounded-lg text-sm font-semibold border cursor-pointer transition-colors"
                style={{
                  borderColor: 'var(--sabana-light-blue)',
                  color: 'var(--sabana-dark-navy)',
                  backgroundColor: 'transparent',
                }}
              >
                {tablaExpandida
                  ? '▲ Ver menos'
                  : `▼ Ver los ${ocultas} restantes`}
              </button>
            </div>
          )}
        </div>

        <div className="flex justify-center mt-8">
          <button
            onClick={recolectar}
            disabled={recolectando}
            className="px-6 py-2 rounded-lg font-semibold disabled:opacity-60"
            style={{ backgroundColor: 'var(--sabana-navy)', color: 'white', cursor: 'pointer' }}
          >
            {recolectando ? 'Actualizando histórico...' : 'Actualizar histórico'}
          </button>
        </div>
          </>
        )}
      </PageLayout>

      <FloatingChat pageTitle={DIMENSIONES[dimension].titulo} pageContent={contextoChat} />
    </>
  );
}
