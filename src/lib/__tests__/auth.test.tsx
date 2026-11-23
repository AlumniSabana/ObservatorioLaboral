import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { SoloAdmin, TOKEN_KEY, authHeaders } from '../auth';

// El módulo guarda una verificación por carga de página: cada prueba lo
// reimporta limpio para no arrastrar estado entre casos.
beforeEach(() => {
  window.localStorage.clear();
  vi.resetModules();
});
afterEach(() => cleanup());

describe('authHeaders', () => {
  it('sin sesión no manda cabecera', () => {
    expect(authHeaders()).toEqual({});
  });

  it('con token manda Authorization: Bearer', () => {
    window.localStorage.setItem(TOKEN_KEY, 'abc.def');
    expect(authHeaders()).toEqual({ Authorization: 'Bearer abc.def' });
  });
});

describe('SoloAdmin', () => {
  it('un usuario sin sesión no ve el contenido de Admin y sí el fallback', async () => {
    render(
      <SoloAdmin fallback={<p>solo lectura</p>}>
        <button>Actualizar histórico</button>
      </SoloAdmin>,
    );
    await waitFor(() => expect(screen.getByText('solo lectura')).toBeTruthy());
    expect(screen.queryByText('Actualizar histórico')).toBeNull();
  });

  it('un token guardado que el servidor no reconoce como admin se descarta', async () => {
    window.localStorage.setItem(TOKEN_KEY, 'caducado.token');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ rol: 'usuario' }), { status: 200 })));
    const { SoloAdmin: Fresco } = await import('../auth');
    render(
      <Fresco fallback={<p>solo lectura</p>}>
        <button>Actualizar histórico</button>
      </Fresco>,
    );
    await waitFor(() => expect(screen.getByText('solo lectura')).toBeTruthy());
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
    vi.unstubAllGlobals();
  });
});
