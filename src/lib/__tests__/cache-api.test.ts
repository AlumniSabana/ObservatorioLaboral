import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cachedFetch, limpiarCache } from '@/lib/cache-api';

const respuesta = (cuerpo: unknown, status = 200) => new Response(JSON.stringify(cuerpo), { status });

describe('cachedFetch', () => {
  const red = vi.fn();
  beforeEach(() => {
    limpiarCache();
    red.mockReset();
    vi.stubGlobal('fetch', red);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('repite la misma URL sin volver a la red y deja leer el cuerpo cada vez', async () => {
    red.mockImplementation(async () => respuesta({ a: 1 }));
    expect(await (await cachedFetch('/x')).json()).toEqual({ a: 1 });
    expect(await (await cachedFetch('/x')).json()).toEqual({ a: 1 });
    expect(red).toHaveBeenCalledTimes(1);
  });

  it('comparte una sola llamada entre peticiones simultáneas', async () => {
    red.mockImplementation(async () => respuesta({ a: 1 }));
    await Promise.all([cachedFetch('/y'), cachedFetch(new URL('http://h/y2')), cachedFetch('/y')]);
    expect(red).toHaveBeenCalledTimes(2);
  });

  it('no guarda errores HTTP: el siguiente intento reintenta', async () => {
    red.mockImplementationOnce(async () => respuesta({}, 500)).mockImplementation(async () => respuesta({ ok: true }));
    expect((await cachedFetch('/z')).status).toBe(500);
    expect((await cachedFetch('/z')).status).toBe(200);
    expect(red).toHaveBeenCalledTimes(2);
  });

  it('limpiarCache obliga a pedir de nuevo', async () => {
    red.mockImplementation(async () => respuesta({}));
    await cachedFetch('/w');
    limpiarCache();
    await cachedFetch('/w');
    expect(red).toHaveBeenCalledTimes(2);
  });

  it('un signal abortado rechaza con AbortError sin afectar a otros', async () => {
    red.mockImplementation(async () => respuesta({ a: 1 }));
    const c = new AbortController();
    const abortada = cachedFetch('/v', { signal: c.signal });
    c.abort();
    await expect(abortada).rejects.toMatchObject({ name: 'AbortError' });
    expect((await cachedFetch('/v')).status).toBe(200);
  });
});
