'use client';

/**
 * Sesión y roles en el frontend — CONTRATO compartido.
 *
 * Es la única fuente de verdad sobre "¿quién está usando la página?". Los
 * componentes lo consumen, no lo redefinen:
 *
 *   const { esAdmin, rol, login, logout } = useAuth();
 *   <SoloAdmin>…botón que solo ve el Admin…</SoloAdmin>
 *   fetch(url, { headers: authHeaders() })        // manda el token al backend
 *
 * Contrato con el backend (src/backend/auth.py):
 *   POST /auth/login {email,password} -> {token, rol, expira_en}
 *   GET  /auth/yo  (Bearer)           -> {rol}
 *   Endpoints protegidos: 401 sin token válido, 403 si el rol no alcanza.
 *
 * El token se guarda en localStorage bajo TOKEN_KEY. Ocultar un botón en el
 * frontend es cortesía de interfaz, no seguridad: la validación real la hace
 * el backend en cada endpoint protegido.
 *
 * Ciclo de vida de la sesión:
 *   1. Al cargar la página, si hay token guardado se pregunta UNA sola vez a
 *      GET /auth/yo. Si el backend responde "usuario" (token caducado, firmado
 *      con otro secreto, manipulado…) se borra, para no mostrar botones de
 *      Admin que fallarían con 401.
 *   2. El token lleva su expiración dentro: se programa un temporizador que lo
 *      borra al vencer, así el menú vuelve solo a "Iniciar sesión".
 *   3. login()/logout() escriben el token y avisan por el bus de eventos a
 *      todos los useAuth() montados.
 *
 * Si un endpoint protegido responde 401 a mitad de sesión (p. ej. el backend
 * se reinició sin AUTH_SECRET fijo), quien hizo ese fetch debe llamar a
 * logout(): este módulo no intercepta fetches ajenos.
 */

import { useCallback, useEffect, useState } from 'react';

export type Rol = 'admin' | 'usuario';

export const TOKEN_KEY = 'observatorio_token';
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Pequeño bus de eventos para que TODOS los useAuth() de la página se enteren
// del login/logout a la vez (localStorage no dispara 'storage' en la misma
// pestaña que lo modifica).
const EVENTO = 'observatorio:auth';

// Tiempo máximo que se espera a /auth/yo al cargar. Pasado este plazo se
// conserva el token (ver verificarTokenGuardado): un backend lento no debe
// dejar al Admin fuera.
const TIMEOUT_VERIFICACION_MS = 8000;

function leerToken(): string | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

// ─── Expiración ─────────────────────────────────────────────────────────────

/** Instante en que vence el token (ms desde epoch), o null si no se puede leer. */
function expiracionDelToken(token: string): number | null {
  try {
    // El token es `<payload_b64url>.<firma>`. Verificar la firma es cosa del
    // backend, pero el payload es legible y basta para saber CUÁNDO vence.
    const b64 = token.split('.')[0].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4)));
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

let temporizadorExpiracion: ReturnType<typeof setTimeout> | null = null;

/** Borra el token justo cuando venza, para que la interfaz no siga creyéndose Admin. */
function programarExpiracion(token: string | null) {
  if (temporizadorExpiracion) {
    clearTimeout(temporizadorExpiracion);
    temporizadorExpiracion = null;
  }
  if (!token) return;
  const vence = expiracionDelToken(token);
  if (vence === null) return;
  // setTimeout no admite más de ~24,8 días (2^31-1 ms). Si faltara más, al
  // despertar se reprograma en vez de cerrar la sesión antes de tiempo.
  const espera = Math.min(Math.max(vence - Date.now(), 0), 2_147_483_647);
  temporizadorExpiracion = setTimeout(() => {
    temporizadorExpiracion = null;
    if (Date.now() >= vence) escribirToken(null);
    else programarExpiracion(token);
  }, espera);
}

function escribirToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* modo privado o storage bloqueado: la sesión dura lo que dure la página */
  }
  programarExpiracion(token);
  window.dispatchEvent(new Event(EVENTO));
}

// ─── Verificación al cargar ─────────────────────────────────────────────────

// Una sola promesa por carga de página, compartida por todos los useAuth():
// con N componentes montados no queremos N peticiones a /auth/yo.
let verificacion: Promise<void> | null = null;

function verificarTokenGuardado(): Promise<void> {
  if (verificacion) return verificacion;
  verificacion = (async () => {
    const token = leerToken();
    if (!token) return;
    const controlador = new AbortController();
    const temporizador = setTimeout(() => controlador.abort(), TIMEOUT_VERIFICACION_MS);
    try {
      const r = await fetch(`${BACKEND_URL}/auth/yo`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controlador.signal,
      });
      // /auth/yo nunca responde 401: si no es 2xx es que el backend está mal
      // (500, proxy caído…), no que la sesión sea inválida.
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (d.rol !== 'admin') {
        escribirToken(null);
        return;
      }
    } catch {
      // Backend inalcanzable: NO castigamos al Admin borrándole la sesión. Si
      // el token de verdad caducó, la primera acción protegida devolverá 401.
    } finally {
      clearTimeout(temporizador);
    }
    programarExpiracion(token);
  })();
  return verificacion;
}

/** Cabeceras a añadir a cualquier fetch que llame un endpoint protegido. */
export function authHeaders(): Record<string, string> {
  const token = leerToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  // `cargando` evita el parpadeo "usuario → admin" en el primer render del
  // cliente, cuando todavía no se ha leído localStorage — y, si hay token
  // guardado, se mantiene hasta que /auth/yo confirme que sigue valiendo,
  // para no enseñar botones de Admin de una sesión ya caducada.
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let montado = true;
    const sincronizar = () => setToken(leerToken());
    window.addEventListener(EVENTO, sincronizar);
    window.addEventListener('storage', sincronizar);
    verificarTokenGuardado().finally(() => {
      if (!montado) return;
      sincronizar();
      setCargando(false);
    });
    return () => {
      montado = false;
      window.removeEventListener(EVENTO, sincronizar);
      window.removeEventListener('storage', sincronizar);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await fetch(`${BACKEND_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) {
      const cuerpo = await r.json().catch(() => ({}));
      throw new Error(cuerpo.detail || `Login rechazado (${r.status})`);
    }
    const d = await r.json();
    if (!d.token) throw new Error('El servidor no devolvió un token de sesión');
    escribirToken(d.token);
  }, []);

  const logout = useCallback(() => escribirToken(null), []);

  const rol: Rol = token ? 'admin' : 'usuario';
  return { rol, esAdmin: rol === 'admin', token, cargando, login, logout };
}

/** Renderiza a sus hijos solo para el Admin (y `fallback`, si se da, al resto). */
export function SoloAdmin({
  children,
  fallback = null,
}: {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { esAdmin, cargando } = useAuth();
  if (cargando) return null;
  return <>{esAdmin ? children : fallback}</>;
}
