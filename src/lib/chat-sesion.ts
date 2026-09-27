/**
 * Sesión anónima del chat y lectura del "tráiler de uso" que añade /api/chat.
 *
 * Lo comparten los dos clientes del asistente: la burbuja contextual
 * (src/lib/floating-chat.tsx) y el chat de Empresas (src/app/asistente/page.tsx).
 *
 * SESIÓN. Para poder contar "costo por sesión" hace falta agrupar preguntas,
 * y no se quiere identificar a nadie (Ley 1581): el id es un texto aleatorio
 * que se genera en el navegador la primera vez que se pregunta y vive en
 * `sessionStorage`, es decir, muere al cerrar la pestaña. No es una cookie,
 * no viaja a terceros y no se cruza con ningún dato del usuario.
 *
 * TRÁILER DE USO. La ruta /api/chat responde texto plano en streaming, y ese
 * contrato no se quiere romper (cambiarlo a SSE obligaría a reescribir los dos
 * clientes y el lector de documentos). En vez de eso, al terminar el stream la
 * ruta añade una última pieza: un carácter NUL seguido de `uso:` y un JSON con
 * los tokens y el costo estimado. NUL no aparece jamás en texto Markdown
 * normal, así que `separarUso` puede partir el acumulado sin ambigüedad. Si un
 * cliente viejo no lo quitara, vería un pie de una línea al final; nunca se
 * pierde texto.
 */

export const MARCADOR_USO = '\u0000uso:';
const CLAVE_SESION = 'observatorio_chat_sesion';

export interface UsoRespuesta {
  modelo: string;
  tokens_entrada: number | null;
  tokens_salida: number | null;
  /** USD, calculado con los precios de las variables de entorno del servidor. */
  costo_usd_estimado: number | null;
  /** Siempre true: es una estimación con precios configurados, no la factura. */
  estimado: true;
  /** Si el backend pudo guardar la pregunta (false sin migración 011). */
  registrada?: boolean;
}

/** Id opaco de la pestaña (se crea una vez; sin `sessionStorage` dura lo que dure la página). */
let sesionEnMemoria: string | null = null;

function aleatorio(): string {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  } catch {
    /* navegadores sin crypto.randomUUID */
  }
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function obtenerSesionId(): string {
  if (sesionEnMemoria) return sesionEnMemoria;
  try {
    const guardado = window.sessionStorage.getItem(CLAVE_SESION);
    if (guardado) {
      sesionEnMemoria = guardado;
      return guardado;
    }
    const nuevo = aleatorio();
    window.sessionStorage.setItem(CLAVE_SESION, nuevo);
    sesionEnMemoria = nuevo;
    return nuevo;
  } catch {
    sesionEnMemoria = aleatorio();
    return sesionEnMemoria;
  }
}

/** Parte el texto acumulado del stream en (texto visible, uso) — `uso` es null hasta que llega el tráiler. */
export function separarUso(acumulado: string): { texto: string; uso: UsoRespuesta | null } {
  const i = acumulado.indexOf(MARCADOR_USO);
  if (i < 0) return { texto: acumulado, uso: null };
  const texto = acumulado.slice(0, i);
  try {
    const uso = JSON.parse(acumulado.slice(i + MARCADOR_USO.length)) as UsoRespuesta;
    return { texto, uso };
  } catch {
    // El JSON del tráiler puede llegar partido en dos fragmentos: se espera al siguiente.
    return { texto, uso: null };
  }
}

export function formatearUsd(v: number | null | undefined, decimales = 4): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `US$ ${v.toFixed(decimales)}`;
}

export function formatearTokens(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return v.toLocaleString('es-CO');
}
