'use client';

/**
 * Página "Skills más demandadas" (ruta '/skills-demandadas').
 *
 * Ranking de competencias y tecnologías ponderado por la demanda REAL de cada
 * programa (share de vacantes de Adzuna) × la importancia O*NET de cada skill en
 * la ocupación. Ver src/backend/Tendencias/skills_demandadas.py.
 *
 * NO es una tendencia temporal ni skills observadas en el texto de las vacantes
 * (Adzuna trunca las descripciones a 500 caracteres). Es una vista DERIVADA de
 * nivel de demanda. Las skills observadas en texto real llegarán con Google Jobs.
 */

import { PageLayout } from '@/lib/sidebar';
import { FloatingChat } from '@/lib/floating-chat';
import { SelectorFuentes, type FuenteOpcion as OpcionSelector } from '@/lib/selector-fuentes';
import { useState, useEffect, useMemo } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  Legend,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// ── Contraste con informes PDF ──────────────────────────────────────────────
// Un informe de un tercero NO se promedia con las vacantes: se muestra en una
// columna aparte. Su "#" es la posición DENTRO de ese informe, no un índice
// comparable con el nuestro; por eso se compara posición contra posición.
interface InformeContraste {
  id: string;
  label: string;
  anio_referencia: number;
  antiguo: boolean;
}
interface TerminoContraste {
  termino: string;
  termino_original: string;
  por_informe: Record<string, { posicion: number | null; pagina: number | null; cita: string | null }>;
}
interface Contraste {
  informes: InformeContraste[];
  terminos: TerminoContraste[];
  no_mapeados: { termino_original: string; informe_id: string; posicion: number | null }[];
}
const TODOS = 'TODOS';

type Tipo = 'tecnologia' | 'competencia';

interface Item {
  nombre: string;
  descripcion: string;
  indice: number; // 0-100, relativo al líder
  n_programas: number;
  // Categoría de las 13 competencias generales homologadas (estudio "Monitoreo
  // entorno 2025", Alumni Sabana) a la que pertenece, o null si no aplica.
  // Solo viene poblado para tipo='competencia'.
  homologada: string | null;
}

interface Respuesta {
  tipo: Tipo;
  programa: string;
  seniority: string;
  items: Item[];
  sin_datos: boolean;
}

// CNO 2025 (SENA). No trae índice ni ranking: el CNO declara qué exige la
// ocupación, no cuánto se pide. Por eso acompaña al ranking en vez de sustituirlo.
interface AtributoCno {
  nombre: string;
  descripcion: string | null;
  especifica: boolean;
}
interface RespuestaSena {
  items: AtributoCno[];
  ocupacion: { codigo: string; nombre: string | null } | null;
  sin_datos: boolean;
}

interface FuenteOpcion {
  fuente: string;
  pais: string;
  label: string;
  /** Dimensiones que aporta (cargo, sector, skill). La usa el selector de fuentes. */
  dimensiones?: string[];
}

interface Opciones {
  programas: string[];
  seniorities: string[];
  fuentes: FuenteOpcion[];
}

// Fuente por defecto mientras cargan las opciones reales del backend.
const FUENTE_DEFECTO: FuenteOpcion = { fuente: 'adzuna', pais: 'us', label: 'Adzuna — Estados Unidos' };

interface SerieEvolucion {
  nombre: string;
  valores: number[];
}

interface Movimiento {
  nombre: string;
  pendiente: number;
}

// Skills que más suben/bajan. El movimiento se mide siempre sobre el mercado
// completo; al filtrar por programa solo se restringe QUÉ skills se listan.
interface KpisMovimiento {
  modo: 'skills';
  emergentes: { total: number; top: Movimiento[] };
  en_declive: { total: number; top: Movimiento[] };
  // Las que se mantienen: sin esta zona neutra, una pendiente de -0.003 (ruido
  // alrededor de cero) se contaría como "en decrecimiento".
  estables: number;
  analizadas: number;
}

interface Evolucion {
  periodos: string[];
  series: SerieEvolucion[];
  // Skills que más suben / más bajan (ranking comparativo, no absoluto).
  kpis?: KpisMovimiento;
  sin_datos: boolean;
}

// Paleta categórica validada (ver globals.css). Orden fijo: el color sigue a la
// skill, no a su posición.
const CAT_COLORS = [
  'var(--cat-1)',
  'var(--cat-2)',
  'var(--cat-3)',
  'var(--cat-4)',
  'var(--cat-5)',
  'var(--cat-6)',
];
const EVOL_VISIBLES = 6; // nº máx. de skills dibujadas a la vez (= colores disponibles)
const EVOL_DISPONIBLES = 40; // nº de skills que se ofrecen para elegir en la gráfica

// '2026-06-01' -> 'jun 2026'
function fmtPeriodo(periodo: string): string {
  const [y, m] = periodo.split('-');
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  return `${meses[Number(m) - 1]} ${y}`;
}

// Tick del eje Y de la gráfica de ranking: en negrilla las competencias
// homologables a una de las 13 categorías generales (estudio "Monitoreo
// entorno 2025", Alumni Sabana). El tooltip de la barra ya dice a cuál; aquí
// solo se distingue visualmente para que se note de un vistazo en la lista.
function TickHomologada({
  x, y, payload, items,
}: {
  x?: number; y?: number; payload?: { value: string }; items: Item[];
}) {
  const nombre = payload?.value ?? '';
  const homologada = items.find((it) => it.nombre === nombre)?.homologada;
  return (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      fontSize={11}
      fill="var(--sabana-black-70)"
      fontWeight={homologada ? 900 : 400}
    >
      {nombre}
    </text>
  );
}

const SENIORITY_LABEL: Record<string, string> = {
  TODOS: 'Todos los niveles',
  senior: 'Senior',
  junior: 'Junior',
  graduado: 'Recién graduado',
  no_especificado: 'No especificado',
};

const TIPO_LABEL: Record<Tipo, string> = {
  tecnologia: 'Tecnologías y herramientas',
  competencia: 'Competencias',
};

// Sequential: una hue institucional, más oscura = más demanda. El color codifica
// la misma variable que la longitud de la barra (magnitud), así que es un refuerzo.
const BAR_COLOR = 'var(--sabana-navy)';

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};

export default function SkillsDemandadasPage() {
  const [tipo, setTipo] = useState<Tipo>('tecnologia');
  const [programa, setPrograma] = useState<string>(TODOS);
  const [seniority, setSeniority] = useState<string>(TODOS);
  // Países seleccionados. Por defecto TODOS los que tengan datos: la vista
  // arranca combinando todas las fuentes (promediando cada mercado).
  const [paisesSel, setPaisesSel] = useState<string[]>([FUENTE_DEFECTO.pais]);
  // Informes PDF marcados en el selector, y sus cifras para la columna de contraste.
  const [informesSel, setInformesSel] = useState<string[]>([]);
  const [contraste, setContraste] = useState<Contraste | null>(null);
  // SPE Colombia: si está marcado, el ranking pasa a usar competencias OBSERVADAS
  // en vacantes colombianas en vez de las derivadas de O*NET.
  const [speActivo, setSpeActivo] = useState(false);
  const [dataSpe, setDataSpe] = useState<Respuesta | null>(null);
  // Fuentes NORMATIVAS. Antes no tenían estado propio y por eso sus checkboxes no
  // respondían: `idsFuentesSel` solo derivaba de país/informe/SPE, y O*NET y el CNO
  // no tienen país. O*NET arranca marcado porque es la base del ranking derivado.
  const [onetActivo, setOnetActivo] = useState(true);
  const [senaActivo, setSenaActivo] = useState(false);
  const [dataSena, setDataSena] = useState<RespuestaSena | null>(null);
  const [opciones, setOpciones] = useState<Opciones>({
    programas: [TODOS],
    seniorities: [TODOS],
    fuentes: [FUENTE_DEFECTO],
  });

  const [data, setData] = useState<Respuesta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState<Item | null>(null);
  const [evolucion, setEvolucion] = useState<Evolucion | null>(null);
  // Qué skills se dibujan en la gráfica de evolución (elegidas por el usuario).
  const [skillsVisibles, setSkillsVisibles] = useState<string[]>([]);

  // Evolución de la demanda a lo largo del tiempo. Cada skill se mueve según su
  // demanda de mercado; al filtrar por programa solo se restringe qué skills se
  // listan (con su misma demanda de mercado).
  const cargarEvolucion = async (t: Tipo, prog: string, sen: string, pais: string[]) => {
    if (pais.length === 0) return;
    try {
      const url = new URL(`${BACKEND_URL}/skills-demandadas/evolucion`);
      url.searchParams.set('tipo', t);
      url.searchParams.set('programa', prog);
      url.searchParams.set('seniority', sen);
      url.searchParams.set('paises', pais.join(','));
      // Traemos un abanico amplio para poder elegir; se dibujan solo unas pocas.
      url.searchParams.set('top', String(EVOL_DISPONIBLES));
      const r = await fetch(url);
      const d: Evolucion | null = r.ok ? await r.json() : null;
      setEvolucion(d);
      // Por defecto se muestran las primeras (las más demandadas).
      setSkillsVisibles((d?.series ?? []).slice(0, EVOL_VISIBLES).map((s) => s.nombre));
    } catch {
      setEvolucion(null);
      setSkillsVisibles([]);
    }
  };

  const alternarSkill = (nombre: string) => {
    setSkillsVisibles((prev) =>
      prev.includes(nombre)
        ? prev.filter((x) => x !== nombre)
        : prev.length < EVOL_VISIBLES
          ? [...prev, nombre]
          : prev,
    );
  };

  const cargar = async (t: Tipo, prog: string, sen: string, pais: string[]) => {
    if (pais.length === 0) return;
    setLoading(true);
    setError(null);
    setSeleccion(null);
    try {
      const url = new URL(`${BACKEND_URL}/skills-demandadas`);
      url.searchParams.set('tipo', t);
      url.searchParams.set('programa', prog);
      url.searchParams.set('seniority', sen);
      url.searchParams.set('paises', pais.join(','));
      url.searchParams.set('top', '25');
      const r = await fetch(url);
      if (!r.ok) throw new Error('No se pudo cargar el ranking de skills');
      setData(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Reutiliza el endpoint de opciones de tendencias (mismos programas/seniority/fuentes).
    fetch(`${BACKEND_URL}/tendencias/opciones`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setOpciones({ programas: d.programas, seniorities: d.seniorities, fuentes: d.fuentes ?? [] });
        // Arranca con TODAS las fuentes combinadas.
        if (d.fuentes?.length) setPaisesSel(d.fuentes.map((f: FuenteOpcion) => f.pais));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargar(tipo, programa, seniority, paisesSel);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [tipo, programa, seniority, paisesSel]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargarEvolucion(tipo, programa, seniority, paisesSel);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [tipo, programa, seniority, paisesSel]);

  // Competencias del SPE (Colombia). A diferencia de los informes, esta fuente SÍ
  // sustituye el ranking: es demanda observada del mismo tipo que la derivada,
  // solo que medida en vacantes colombianas reales en vez de estimada con O*NET.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!speActivo) {
      setDataSpe(null);
      return;
    }
    const url = new URL(`${BACKEND_URL}/spe/competencias`);
    url.searchParams.set('programa', programa);
    url.searchParams.set('tipo', tipo);
    url.searchParams.set('top', '20');
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setDataSpe(d && !d.sin_datos ? d : null))
      .catch(() => setDataSpe(null));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [speActivo, programa, tipo]);

  // CNO 2025 (SENA): requisito OFICIAL de la ocupación, en español. No sustituye
  // el ranking (no mide demanda) sino que lo acompaña, igual que los informes.
  // Solo tiene sentido con un programa concreto: el CNO habla por ocupación.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!senaActivo || programa === TODOS) {
      setDataSena(null);
      return;
    }
    const url = new URL(`${BACKEND_URL}/sena/skills`);
    url.searchParams.set('programa', programa);
    // El CNO separa "habilidades" de "conocimientos"; se alinean con el conmutador
    // Competencias / Tecnologías, que es la distinción equivalente en esta vista.
    url.searchParams.set('tipo', tipo === 'competencia' ? 'habilidad' : 'conocimiento');
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setDataSena(d && !d.sin_datos ? d : null))
      .catch(() => setDataSena(null));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [senaActivo, programa, tipo]);

  // De dónde sale el ranking que se pinta: si el SPE está marcado manda él
  // (dato observado en Colombia); si no, el derivado de O*NET.
  const datosRanking = speActivo && dataSpe ? dataSpe : data;

  // Cifras de los informes marcados, para la columna de contraste. Va por separado
  // del ranking a propósito: el informe no lo altera, solo lo acompaña.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (informesSel.length === 0) {
      setContraste(null);
      return;
    }
    const url = new URL(`${BACKEND_URL}/informes/contraste`);
    url.searchParams.set('informes', informesSel.join(','));
    url.searchParams.set('dimension', 'skill');
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setContraste(d))
      .catch(() => setContraste(null));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [informesSel]);

  // ── Puente entre el selector (ids) y el estado (países + informes) ──────────
  // El backend de skills se filtra por `paises`; los informes van por su propio
  // endpoint. Se guardan por separado y el selector los presenta como una lista.
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
    () => [
      ...opciones.fuentes.filter((f) => f.pais && paisesSel.includes(f.pais)).map(idDeFuente),
      ...informesSel,
      ...(speActivo ? ['spe:co'] : []),
      ...(onetActivo ? ['onet'] : []),
      ...(senaActivo ? ['sena:cno'] : []),
    ],
    [opciones.fuentes, paisesSel, informesSel, speActivo, onetActivo, senaActivo],
  );

  const alCambiarFuentes = (ids: string[]) => {
    const paises = opciones.fuentes
      .filter((f) => f.pais && ids.includes(idDeFuente(f)))
      .map((f) => f.pais);
    if (paises.length > 0) setPaisesSel([...new Set(paises)]);
    setInformesSel(ids.filter((i) => i.startsWith('informe:')));
    setSpeActivo(ids.includes('spe:co'));
    setSenaActivo(ids.includes('sena:cno'));
    // O*NET solo se puede apagar si queda otra fuente que sepa producir un
    // ranking de skills; si no, la vista se quedaría en blanco.
    setOnetActivo(ids.includes('onet') || !ids.includes('spe:co'));
  };

  // Formato ancho para recharts: una fila por periodo, una columna por skill
  // VISIBLE (las que el usuario eligió mostrar).
  const datosEvolucion = useMemo(() => {
    if (!evolucion || evolucion.sin_datos) return [];
    const visibles = evolucion.series.filter((s) => skillsVisibles.includes(s.nombre));
    return evolucion.periodos.map((p, i) => {
      const fila: Record<string, string | number> = { periodo: fmtPeriodo(p) };
      visibles.forEach((s) => {
        fila[s.nombre] = s.valores[i];
      });
      return fila;
    });
  }, [evolucion, skillsVisibles]);

  // Color estable por skill: sigue su posición en la selección, no en el ranking.
  const colorDeSkill = (nombre: string) => CAT_COLORS[skillsVisibles.indexOf(nombre) % CAT_COLORS.length];

  const mostrarEvolucion = (evolucion?.series.length ?? 0) > 0 && !evolucion?.sin_datos;

  const estiloSelect = {
    backgroundColor: 'var(--sabana-sky-blue)',
    color: 'var(--sabana-dark-navy)',
    borderColor: 'var(--sabana-light-blue)',
  };
  const claseSelect = 'rounded-lg px-3 py-2 text-sm font-semibold border cursor-pointer w-full';
  const claseEtiqueta = 'block text-xs font-bold uppercase tracking-wide mb-1';

  const filtros = (
    <div
      className="mb-6 rounded-lg p-4 border"
      style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--white-background)' }}
    >
      {/* Fuentes de datos: desplegable con checkboxes (mismo componente que Tendencias).
          Aquí sí aplican los informes PDF: aportan dimensión 'skill'. */}
      <div className="mb-3 pb-3 border-b" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
        <div className="max-w-md">
          <SelectorFuentes
            fuentes={fuentesParaSelector}
            seleccionadas={idsFuentesSel}
            onChange={alCambiarFuentes}
            dimensionActiva="skill"
          />
        </div>

        {programa !== TODOS && (
          <p className="text-xs text-zinc-400 mt-2">
            ⓘ Con un programa concreto, las fuentes no cambian el ranking: las competencias O*NET de
            una ocupación son las mismas en cualquier mercado. Sí afectan a la evolución temporal.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label htmlFor="s-tipo" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Mostrar
          </label>
          <select
            id="s-tipo"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as Tipo)}
            className={claseSelect}
            style={estiloSelect}
          >
            <option value="tecnologia">Tecnologías y herramientas</option>
            <option value="competencia">Competencias</option>
          </select>
        </div>
        <div>
          <label htmlFor="s-prog" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Programa académico
          </label>
          <select
            id="s-prog"
            value={programa}
            onChange={(e) => setPrograma(e.target.value)}
            className={claseSelect}
            style={estiloSelect}
          >
            {opciones.programas.map((p) => (
              <option key={p} value={p}>
                {p === TODOS ? 'Todos (ponderado por demanda)' : p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="s-sen" className={claseEtiqueta} style={{ color: 'var(--sabana-navy)' }}>
            Nivel de experiencia
          </label>
          <select
            id="s-sen"
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
      </div>

      {programa !== TODOS && seniority !== TODOS && (
        <p className="text-xs text-zinc-400 mt-3">
          ⓘ Con un programa concreto, el nivel de experiencia no cambia el ranking: las competencias
          O*NET de una ocupación son fijas. El nivel sí tiene efecto con «Todos los programas»
          (cambia el mix de carreras demandadas).
        </p>
      )}
    </div>
  );

  const etiquetasPaises = opciones.fuentes
    .filter((f) => paisesSel.includes(f.pais))
    .map((f) => f.label)
    .join(', ');

  const chatContext =
    data && !data.sin_datos
      ? `Página "Competencias" (${TIPO_LABEL[tipo].toLowerCase()}). Ranking derivado: cruza la ` +
        `demanda real de cada programa académico (share de vacantes) con la importancia ` +
        `O*NET de cada skill en la ocupación. NO son skills observadas en el texto de las vacantes ni una ` +
        `tendencia temporal. Fuentes: ${etiquetasPaises}` +
        `${paisesSel.length > 1 ? ' (combinadas promediando la cuota de cada mercado, así cada país pesa igual)' : ''}. ` +
        `Programa: ${programa === TODOS ? 'todos (ponderado por demanda)' : programa}. ` +
        `Nivel: ${SENIORITY_LABEL[seniority]}. Ranking (índice 0-100 relativo al líder): ` +
        data.items
          .slice(0, 15)
          .map((i) => `${i.nombre} ${i.indice}`)
          .join(', ') +
        '.'
      : 'Página de skills más demandadas (competencias y tecnologías) derivadas de O*NET y la demanda de programas.';

  return (
    <>
      <PageLayout title="Competencias">
        {filtros}

        <div
          className="mb-6 rounded-lg p-4 text-sm border-l-4"
          style={{ borderColor: 'var(--sabana-light-blue)', backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}
        >
          {speActivo && dataSpe ? (
            <>
              🇨🇴 Ranking <strong>observado</strong>: son las competencias que los empleadores
              pidieron de verdad en las vacantes registradas por el <strong>Servicio Público de
              Empleo</strong> de Colombia. No es una estimación: se cuentan menciones reales sobre
              ~1,8 millones de ofertas. El índice va de 0 a 100 respecto a la skill líder.
              {programa !== TODOS && <> Filtrado por el grupo ocupacional de <strong>{programa}</strong>.</>}
            </>
          ) : (
            <>
              ℹ️ Ranking <strong>derivado</strong>: combina la <strong>demanda real</strong> de cada programa
              (share de vacantes de Adzuna) con la <strong>importancia O*NET</strong> de cada skill en la
              ocupación. No son skills leídas del texto de las vacantes —Adzuna no lo permite— sino una
              estimación de qué competencias y herramientas concentra el mercado que se está demandando. El
              índice va de 0 a 100 respecto a la skill líder. Para verlas <em>observadas</em> en Colombia,
              marca la fuente <strong>SPE — Colombia</strong> en el selector.
            </>
          )}
        </div>

        {/* ---------------- KPIs de movimiento ----------------
            Ranking COMPARATIVO ("las que más suben/bajan"), no una clasificación
            absoluta como la de cargos: la demanda de una skill es un promedio
            sobre muchos programas, así que se suaviza y sus pendientes son mucho
            menores. Ver Tendencias/skills_demandadas._kpis_movimiento. */}
        {!loading && !error && evolucion?.kpis?.modo === 'skills' && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div
                className="rounded-lg p-5 bg-white dark:bg-zinc-800 shadow border-l-4"
                style={{ borderColor: 'var(--trend-up)' }}
              >
                <p className="text-sm font-bold mb-1 flex items-center gap-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                  <span style={{ color: 'var(--trend-up)' }}>▲</span>{' '}
                  {tipo === 'tecnologia' ? 'Tecnologías' : 'Competencias'} emergentes
                </p>
                <p className="text-3xl font-bold" style={{ color: 'var(--trend-up)' }}>
                  {evolucion.kpis.emergentes?.total ?? 0}
                </p>
                <p className="text-xs text-zinc-500 mt-1">
                  de {evolucion.kpis.analizadas} analizadas destacan al alza
                </p>
                {!!evolucion.kpis.emergentes?.top.length && (
                  <p className="text-xs mt-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {evolucion.kpis.emergentes.top.map((m) => m.nombre).join(' · ')}
                  </p>
                )}
              </div>

              <div
                className="rounded-lg p-5 bg-white dark:bg-zinc-800 shadow border-l-4"
                style={{ borderColor: 'var(--trend-down)' }}
              >
                <p className="text-sm font-bold mb-1 flex items-center gap-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                  <span style={{ color: 'var(--trend-down)' }}>▼</span>{' '}
                  {tipo === 'tecnologia' ? 'Tecnologías' : 'Competencias'} en decrecimiento
                </p>
                <p className="text-3xl font-bold" style={{ color: 'var(--trend-down)' }}>
                  {evolucion.kpis.en_declive?.total ?? 0}
                </p>
                <p className="text-xs text-zinc-500 mt-1">
                  de {evolucion.kpis.analizadas} analizadas destacan a la baja
                </p>
                {!!evolucion.kpis.en_declive?.top.length && (
                  <p className="text-xs mt-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {evolucion.kpis.en_declive.top.map((m) => m.nombre).join(' · ')}
                  </p>
                )}
              </div>
            </div>

            <p className="text-xs text-zinc-400 -mt-4 mb-6">
              ⓘ Solo se destacan las que <strong>se mueven de forma apreciable</strong> frente al
              resto del mercado; las demás ({evolucion.kpis.estables}) se consideran estables. Es un
              comparativo dentro del periodo, no una afirmación de crecimiento absoluto.
              {programa !== TODOS
                ? ` Se listan solo las que usa ${programa}, pero su movimiento se mide en el mercado completo.`
                : ' El movimiento refleja qué carreras están concentrando la demanda.'}
            </p>
          </>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <p className="text-lg text-zinc-600 font-bold">⏳ Cargando ranking...</p>
          </div>
        )}

        {!loading && error && (
          <div className="bg-red-100 rounded-lg p-6">
            <p className="text-red-700">❌ {error}</p>
            <button
              onClick={() => cargar(tipo, programa, seniority, paisesSel)}
              className="mt-4 px-4 py-2 rounded-lg font-semibold"
              style={{ backgroundColor: 'var(--sabana-light-blue)', color: 'white' }}
            >
              Reintentar
            </button>
          </div>
        )}

        {!loading && !error && datosRanking && (datosRanking.sin_datos || datosRanking.items.length === 0) && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-8 shadow text-center">
            <p className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
              Sin datos para esta combinación.
            </p>
            <p className="text-sm text-zinc-500 mt-2">
              Puede que O*NET no tenga esta ocupación mapeada, o que no haya demanda registrada.
            </p>
          </div>
        )}

        {!loading && !error && datosRanking && !datosRanking.sin_datos && datosRanking.items.length > 0 && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              {TIPO_LABEL[tipo]} más demandadas
            </h3>
            <p className="text-sm text-zinc-500 mb-4">
              Índice de demanda relativo (0-100). Haz clic en una barra para ver qué es.
              {tipo === 'competencia' && (
                <>
                  {' '}Las que están en <b>negrilla</b> se homologan a una de las 13 competencias
                  generales del estudio de Alumni Sabana (pasa el cursor sobre la barra para ver cuál).
                </>
              )}
            </p>
            <ResponsiveContainer width="100%" height={Math.max(320, datosRanking.items.length * 26)}>
              <BarChart
                data={datosRanking.items}
                layout="vertical"
                margin={{ top: 5, right: 40, left: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--sabana-black-70)' }} />
                <YAxis
                  dataKey="nombre"
                  type="category"
                  width={230}
                  interval={0}
                  tick={<TickHomologada items={datosRanking.items} />}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={{ color: 'var(--white-background)' }}
                  labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
                  formatter={(value, _n, props) => [
                    `índice ${value} · en ${props.payload.n_programas} programa(s)` +
                      (props.payload.homologada
                        ? ` · homologable a "${props.payload.homologada}"`
                        : ''),
                    'Demanda',
                  ]}
                />
                <Bar
                  dataKey="indice"
                  radius={[0, 4, 4, 0]}
                  barSize={16}
                  cursor="pointer"
                  onClick={(_d, index) => setSeleccion(datosRanking.items[index])}
                >
                  {datosRanking.items.map((it) => (
                    <Cell key={it.nombre} fill={BAR_COLOR} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {seleccion && (
              <div
                className="mt-4 rounded-lg p-4 border-l-4 flex items-start gap-3"
                style={{ borderColor: 'var(--sabana-navy)', backgroundColor: 'var(--sabana-sky-blue)' }}
              >
                <div className="flex-1">
                  <p className="font-bold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {seleccion.nombre}
                  </p>
                  <p className="text-sm" style={{ color: 'var(--sabana-dark-navy)' }}>
                    {seleccion.descripcion}
                  </p>
                  <p className="text-xs mt-2 text-zinc-500">
                    Índice de demanda {seleccion.indice}/100 · presente en {seleccion.n_programas} programa(s).
                  </p>
                </div>
                <button
                  onClick={() => setSeleccion(null)}
                  className="text-sm font-bold px-2"
                  style={{ color: 'var(--sabana-navy)' }}
                  aria-label="Cerrar"
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        )}

        {/* ---------------- Requisito oficial: CNO 2025 (SENA) ----------------
            Como los informes, acompaña al ranking sin alterarlo. La diferencia es
            de naturaleza: el ranking mide qué PIDE el mercado hoy; el CNO declara
            qué EXIGE la ocupación según la norma colombiana. */}
        {senaActivo && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow mt-8">
            <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              🇨🇴 Requisito oficial — CNO 2025 (SENA)
            </h3>
            {programa === TODOS ? (
              <p className="text-sm text-zinc-500">
                El CNO describe requisitos <strong>por ocupación</strong>, así que necesita un programa
                concreto. Elige uno en el filtro <strong>Programa académico</strong> para ver qué exige
                oficialmente en Colombia.
              </p>
            ) : !dataSena ? (
              <p className="text-sm text-zinc-500">Sin datos del CNO para {programa}.</p>
            ) : (
              <>
                <p className="text-sm text-zinc-500 mb-3">
                  {tipo === 'competencia' ? 'Habilidades' : 'Conocimientos'} que la{' '}
                  <strong>Clasificación Nacional de Ocupaciones</strong> exige para{' '}
                  <strong>{dataSena.ocupacion?.nombre ?? programa}</strong>
                  {dataSena.ocupacion?.codigo && ` (código ${dataSena.ocupacion.codigo})`}. Es la norma
                  del país, <strong>no una medición de demanda</strong>: por eso no lleva índice ni
                  posición. Lo que aparezca aquí y no en el ranking es una exigencia formal que el
                  mercado no está pidiendo de forma explícita.
                </p>
                <div className="flex flex-wrap gap-2">
                  {dataSena.items.map((it) => (
                    <span
                      key={it.nombre}
                      title={it.descripcion ?? undefined}
                      className="text-sm rounded-lg px-3 py-1.5"
                      style={{
                        backgroundColor: it.especifica ? 'var(--sabana-sky-blue)' : 'transparent',
                        border: it.especifica ? 'none' : '1px dashed var(--sabana-light-blue)',
                        color: 'var(--sabana-dark-navy)',
                      }}
                    >
                      {it.nombre}
                      {!it.especifica && <span className="opacity-60 text-xs"> · del grupo</span>}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-zinc-400 mt-3">
                  Las marcadas <em>del grupo</em> se heredan del grupo ocupacional superior: aplican,
                  pero no son exclusivas de esta ocupación.
                </p>
              </>
            )}
          </div>
        )}

        {/* ---------------- Contraste con informes de terceros ----------------
            El informe NUNCA reordena el ranking ni entra en el índice: se pone al
            lado, comparando POSICIÓN contra POSICIÓN. Por eso las skills que solo
            aparecen en el informe van al final, sin número de índice. */}
        {contraste && contraste.informes.length > 0 && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow mt-8">
            <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              📑 Contraste con informes
            </h3>
            <p className="text-sm text-zinc-500 mb-3">
              Qué dicen los informes seleccionados frente a nuestro ranking. Son cifras{' '}
              <strong>declaradas por su editor</strong>, no medidas por el Observatorio: se comparan
              posiciones, nunca se promedian con la demanda de vacantes.
            </p>

            {/* Ficha de cada informe: editor, año y aviso de antigüedad. */}
            <div className="flex flex-wrap gap-2 mb-4">
              {contraste.informes.map((inf) => (
                <span
                  key={inf.id}
                  className="text-xs rounded-lg px-3 py-1.5"
                  style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}
                >
                  <b>{inf.label}</b>
                  {` · ${inf.anio_referencia}`}
                  {inf.antiguo && (
                    <span style={{ color: 'var(--trend-down)' }}> · ⚠ datos de {inf.anio_referencia}</span>
                  )}
                </span>
              ))}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                    <th className="text-left px-3 py-2 font-semibold">Skill</th>
                    <th className="text-right px-3 py-2 font-semibold">Nuestro índice</th>
                    {contraste.informes.map((inf) => (
                      <th key={inf.id} className="text-right px-3 py-2 font-semibold">
                        {inf.label.split('—')[0].trim()} (#)
                      </th>
                    ))}
                    <th className="text-left px-3 py-2 font-semibold">Coherencia</th>
                  </tr>
                </thead>
                <tbody>
                  {contraste.terminos.map((t, i) => {
                    // Posición en NUESTRO ranking (por orden del índice), si está.
                    const idxNuestro = data?.items.findIndex(
                      (it) => it.nombre.toLowerCase() === t.termino.toLowerCase(),
                    ) ?? -1;
                    const enNuestro = idxNuestro >= 0;
                    const posInforme = Object.values(t.por_informe)[0]?.posicion ?? null;
                    const diferencia =
                      enNuestro && posInforme ? idxNuestro + 1 - posInforme : null;
                    return (
                      <tr key={t.termino} style={{ backgroundColor: i % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                        <td className="px-3 py-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                          {t.termino}
                          {t.termino_original.toLowerCase() !== t.termino.toLowerCase() && (
                            <span className="text-xs text-zinc-400"> ({t.termino_original})</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>
                          {enNuestro ? `${data!.items[idxNuestro].indice} (#${idxNuestro + 1})` : '—'}
                        </td>
                        {contraste.informes.map((inf) => (
                          <td key={inf.id} className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>
                            {t.por_informe[inf.id]?.posicion != null ? `#${t.por_informe[inf.id].posicion}` : '—'}
                          </td>
                        ))}
                        <td className="px-3 py-2 text-xs">
                          {!enNuestro ? (
                            // Ojo: solo se compara contra el top que se está mostrando.
                            // Que no aparezca aquí no prueba que no exista en nuestros
                            // datos, únicamente que no entró en este top.
                            <span style={{ color: 'var(--sabana-black-50)' }}>
                              fuera de nuestro top {data?.items.length ?? 0}
                            </span>
                          ) : diferencia === null ? (
                            '—'
                          ) : Math.abs(diferencia) <= 1 ? (
                            <span style={{ color: 'var(--trend-up)' }}>✓ coinciden</span>
                          ) : (
                            <span style={{ color: 'var(--trend-flat)' }}>
                              {diferencia > 0 ? '▲' : '▼'} {Math.abs(diferencia)} posiciones
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {contraste.no_mapeados.length > 0 && (
              <p className="text-xs mt-3" style={{ color: 'var(--sabana-black-50)' }}>
                <b>Sin equivalente en nuestra taxonomía:</b>{' '}
                {contraste.no_mapeados.map((n) => n.termino_original).join(' · ')}. Aparecen en el
                informe pero no en el diccionario del Observatorio, así que no se pueden comparar.
              </p>
            )}
          </div>
        )}

        {/* ---------------- Evolución temporal ---------------- */}
        {!loading && !error && mostrarEvolucion && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow mt-8">
            <h3 className="text-xl font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              📈 Evolución de la demanda
            </h3>
            <p className="text-sm text-zinc-500 mb-2">
              Cómo se ha movido el índice de demanda a lo largo del tiempo. Elige hasta{' '}
              {EVOL_VISIBLES} {tipo === 'tecnologia' ? 'tecnologías' : 'competencias'} para comparar.
            </p>
            <p className="text-xs text-zinc-400 mb-4">
              ⓘ Índice de demanda de mercado de cada skill (mix de todas las carreras), suavizado con
              media móvil de 3 meses.{' '}
              {programa !== TODOS
                ? `Se muestran solo las skills que usa ${programa}, con su demanda en el mercado completo.`
                : 'Refleja cambios en qué carreras concentran la demanda, no una tendencia observada en el texto.'}
            </p>

            {/* Selector de skills a mostrar */}
            <div className="flex flex-wrap gap-2 mb-5">
              {(evolucion?.series ?? []).map((s) => {
                const activa = skillsVisibles.includes(s.nombre);
                const lleno = !activa && skillsVisibles.length >= EVOL_VISIBLES;
                return (
                  <button
                    key={s.nombre}
                    onClick={() => alternarSkill(s.nombre)}
                    disabled={lleno}
                    className="px-3 py-1 rounded-full text-xs font-semibold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    style={{
                      backgroundColor: activa ? colorDeSkill(s.nombre) : 'transparent',
                      color: activa ? 'white' : 'var(--sabana-dark-navy)',
                      borderColor: activa ? colorDeSkill(s.nombre) : 'var(--sabana-light-blue)',
                    }}
                  >
                    {s.nombre}
                  </button>
                );
              })}
            </div>

            {skillsVisibles.length === 0 ? (
              <p className="text-center text-zinc-500 py-8">
                Selecciona al menos una {tipo === 'tecnologia' ? 'tecnología' : 'competencia'}.
              </p>
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
                  label={{
                    value: 'Índice de demanda',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 11, fill: 'var(--sabana-black-70)' },
                  }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={{ color: 'var(--white-background)' }}
                  labelStyle={{ color: 'var(--sabana-light-blue)', fontWeight: 'bold' }}
                />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                {skillsVisibles.map((nombre) => (
                  <Line
                    key={nombre}
                    type="monotone"
                    dataKey={nombre}
                    stroke={colorDeSkill(nombre)}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            )}
          </div>
        )}

      </PageLayout>

      <FloatingChat pageTitle="Competencias" pageContent={chatContext} />
    </>
  );
}
