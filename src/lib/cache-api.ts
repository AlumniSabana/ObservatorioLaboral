/**
 * Caché en memoria para las lecturas (GET) del backend.
 *
 * Los datos del Observatorio cambian solo cuando el Administrador recolecta o
 * sube algo, pero el backend tarda en responder (Supabase + cálculos). Al
 * volver a una página ya visitada —Tendencias → Competencias → Tendencias—
 * se reutiliza la respuesta en vez de pedirla otra vez.
 *
 *   const r = await cachedFetch(url);   // mismo contrato que fetch(url)
 *
 * - Devuelve un `Response` nuevo en cada llamada, así que `r.json()` se puede
 *   leer varias veces sin consumir el cuerpo guardado.
 * - Peticiones idénticas en vuelo comparten una sola llamada de red.
 * - Los errores (HTTP no 2xx o de red) no se guardan: el siguiente intento reintenta.
 * - `limpiarCache()` descarta todo; se llama tras cualquier escritura del Administrador.
 * - Vive en la memoria de la pestaña: al recargar con F5 se vuelve a pedir.
 *
 * shortcut: solo GET sin cabeceras de sesión y sin invalidación parcial; si
 * hiciera falta cachear datos por usuario o un TTL por ruta, usar SWR/React Query.
 */

const TTL_MS = 10 * 60 * 1000;

type Guardada = { body: string; status: number };
const cache = new Map<string, { t: number; p: Promise<Guardada> }>();

export function limpiarCache() {
  cache.clear();
}

function abortada(): DOMException {
  return new DOMException('The operation was aborted.', 'AbortError');
}

export function cachedFetch(entrada: string | URL, init?: { signal?: AbortSignal | null }): Promise<Response> {
  const url = String(entrada);
  const signal = init?.signal;
  const hit = cache.get(url);
  let p = hit && Date.now() - hit.t < TTL_MS ? hit.p : undefined;
  if (!p) {
    // La red NO recibe el `signal` del llamador: si una página lo aborta (cambió
    // de filtro), otra que espera lo mismo no debe quedarse sin respuesta.
    const nueva: Promise<Guardada> = fetch(url).then(async (r) => {
      const body = await r.text();
      if (!r.ok && cache.get(url)?.p === nueva) cache.delete(url);
      return { body, status: r.status };
    });
    nueva.catch(() => {
      if (cache.get(url)?.p === nueva) cache.delete(url);
    });
    cache.set(url, { t: Date.now(), p: nueva });
    p = nueva;
  }
  return new Promise<Response>((resolve, reject) => {
    if (signal?.aborted) return reject(abortada());
    signal?.addEventListener('abort', () => reject(abortada()), { once: true });
    p.then(
      ({ body, status }) => resolve(new Response(status === 204 || status === 205 ? null : body, { status })),
      reject,
    );
  });
}
