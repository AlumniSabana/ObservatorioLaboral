/**
 * Tipos, constantes y utilidades COMPARTIDAS por las dos vistas de /informes
 * (vista-admin.tsx y vista-usuario.tsx) y por sus piezas (subir-informe.tsx,
 * graficas-informe.tsx, insights-conjuntos.tsx).
 *
 * Vive aparte para que page.tsx sea solo el conmutador por rol y ninguna vista
 * tenga que redefinir las mismas interfaces del backend. Todo lo que hay aquí
 * refleja la forma de las respuestas de src/backend/main.py (región /informes).
 */

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// ── Extracción y catálogo ──────────────────────────────────────────────────

export interface Item {
  termino_original: string;
  metrica: string;
  valor: number | null;
  posicion: number | null;
  pagina: number | null;
  cita: string | null;
  verificada: boolean;
}

/** Ficha mínima del informe RETIRADO al que corresponde el PDF recién subido. */
export interface InformeReactivable {
  id: string;
  estado: string;
  titulo: string;
  editor: string;
  anio_referencia: number;
}

export interface Borrador {
  hash_pdf: string;
  paginas: number;
  metodo_extraccion: string;
  idioma_detectado: string;
  metadatos_sugeridos: {
    titulo: string | null;
    editor: string | null;
    anio_referencia: number | null;
    cobertura: string | null;
  };
  extraidos: number;
  items: Item[];
  // Presente solo cuando el PDF ya fue ingerido y ese informe está retirado:
  // al guardar se reactivará ese registro (mismo id) en vez de crear otro.
  reactiva?: InformeReactivable | null;
}

export interface InformeGuardado {
  id: string;
  titulo: string;
  editor: string;
  anio_referencia: number;
  estado: string;
  n_observaciones: number;
}

export interface ResultadoGuardado {
  id: string;
  estado: string;
  observaciones: number;
  reactivado: boolean;
}

// ── Detalle y comparativa ──────────────────────────────────────────────────

export interface DetalleItem {
  termino: string;
  categoria: string;
  valor: number | null;
  posicion: number | null;
  pagina: number | null;
}

export interface Detalle {
  informe: {
    id: string; titulo: string; editor: string; anio_referencia: number;
    cobertura: string | null; paginas: number | null; idioma: string | null;
    estado: string; total_skills: number;
  } | null;
  items: DetalleItem[];
  por_categoria: { categoria: string; n: number }[];
}

export interface Comparativa {
  informes: { id: string; label: string }[];
  terminos: { termino: string; posiciones: Record<string, number | null> }[];
}

// ── Insights (individuales y conjuntos) ────────────────────────────────────

export interface InformeCitado {
  id: string;
  titulo: string;
  editor: string;
  anio_referencia: number;
  antiguo?: boolean;
}

export interface InsightsResp {
  texto: string;
  informes: InformeCitado[];
  omitidos: string[];
  // false cuando falta la migración 012: el texto llegó pero no quedó guardado.
  persistido: boolean;
  insight_id: number | null;
  aviso: string | null;
}

export interface InsightConjuntoResp extends InsightsResp {
  titulo: string;
  motivo_grupo: string | null;
}

/** Fila de la tabla `insights_generados` (migración 012). */
export interface InsightGenerado {
  id: number;
  tipo: 'individual' | 'conjunto';
  informe_ids: string[];
  informes: InformeCitado[] | null;
  titulo: string;
  contenido: string;
  modelo: string | null;
  motivo_grupo: string | null;
  creado_en: string;
}

export interface InsightsGeneradosResp {
  disponible: boolean;
  insights: InsightGenerado[];
  aviso: string | null;
}

export interface GrupoCandidato {
  informe_ids: string[];
  titulo_grupo: string;
  motivo: string;
  afinidad: number;
}

export interface CandidatosResp {
  grupos: GrupoCandidato[];
  informes: InformeCitado[];
  metodo: 'gemini' | 'heuristico' | null;
  modelo: string | null;
  aviso: string | null;
}

// ── Similares ──────────────────────────────────────────────────────────────

export interface Similar {
  id: string;
  titulo: string;
  editor: string;
  anio_referencia: number;
  cobertura: string | null;
  afinidad: number;
  n_compartidas: number;
  compartidas: string[];
}

export interface SimilaresResp {
  informe_id: string;
  similares: Similar[];
  n_candidatos: number;
}

// ── "Mis informes" del Usuario ─────────────────────────────────────────────
//
// El Usuario no tiene login (decisión del Tech Lead), así que "sus" informes
// son los que se registraron desde ESTE navegador: al guardar uno se anota su
// id en localStorage. Limitación asumida: otro navegador u otro equipo no los
// verá, y borrar los datos del sitio los olvida (los informes siguen en el
// catálogo del Observatorio; solo se pierde el vínculo local).

export const MIS_INFORMES_KEY = 'observatorio_mis_informes';

export function leerMisInformes(): string[] {
  try {
    if (typeof window === 'undefined') return [];
    const crudo = window.localStorage.getItem(MIS_INFORMES_KEY);
    const lista = crudo ? JSON.parse(crudo) : [];
    return Array.isArray(lista) ? lista.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function escribirMisInformes(ids: string[]) {
  try {
    window.localStorage.setItem(MIS_INFORMES_KEY, JSON.stringify(ids));
  } catch {
    /* modo privado o storage bloqueado: el vínculo dura lo que dure la página */
  }
}

export function recordarMiInforme(id: string) {
  const actuales = leerMisInformes();
  // El más reciente primero; sin duplicados (re-subir un retirado conserva el id).
  escribirMisInformes([id, ...actuales.filter((x) => x !== id)]);
}

export function olvidarMiInforme(id: string) {
  escribirMisInformes(leerMisInformes().filter((x) => x !== id));
}

// ── Errores de endpoints protegidos ────────────────────────────────────────

export const MENSAJE_SESION_EXPIRADA = 'La sesión de Administrador expiró, vuelve a iniciar sesión.';

/**
 * Mensaje a mostrar cuando un fetch a un endpoint PROTEGIDO no fue 2xx.
 *
 * Con 401 además cierra la sesión local (`logout` de useAuth): si el backend se
 * reinicia sin AUTH_SECRET fijo, el token deja de valer pero el navegador
 * seguiría creyéndose Admin y todos los botones fallarían con un error
 * genérico. El guard responde `{detail}` (HTTPException) y los handlers
 * `{error}`: se leen ambos.
 */
export async function errorDeRespuesta(r: Response, logout: () => void): Promise<string> {
  if (r.status === 401) {
    logout();
    return MENSAJE_SESION_EXPIRADA;
  }
  const d = await r.json().catch(() => ({}));
  if (r.status === 403) return d.detail || 'Esta acción es solo para el Administrador.';
  return d.error || d.detail || `HTTP ${r.status}`;
}

// ── Presentación ───────────────────────────────────────────────────────────

/** Cómo se le explica cada estado al Usuario (el Admin ve el estado crudo). */
export const ETIQUETA_ESTADO: Record<string, string> = {
  borrador: 'Pendiente de validación por el Administrador',
  validado: 'Validado por el Administrador',
  retirado: 'Retirado por el Administrador',
};

export function etiquetaInforme(i: { editor: string; titulo: string; anio_referencia: number }) {
  return `${i.editor} — ${i.titulo} (${i.anio_referencia})`;
}

export function formatearFecha(iso: string): string {
  try {
    return new Date(iso).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

export const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};
export const COLORES_CAT = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

/** Clases/estilos de formulario compartidos entre el paso "Revisar" y el resto. */
export const CLASE_ETIQUETA = 'block text-xs font-bold uppercase tracking-wide mb-1';
export const CLASE_CAMPO = 'w-full rounded-lg border px-3 py-2 text-sm';
export const ESTILO_CAMPO = { borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' };
