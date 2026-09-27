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
 * ESTADO: esqueleto del Tech Lead. Funciona de punta a punta contra el backend
 * real cuando el Equipo 1 implemente /auth/login; mientras tanto, para
 * desarrollar como Admin basta con guardar cualquier texto en localStorage:
 *   localStorage.setItem('observatorio_token', 'dev')
 * El Equipo 1 (feature/auth-roles) completa este archivo: verificación del
 * token con /auth/yo al cargar, expiración, y la pantalla de login.
 */

import { useCallback, useEffect, useState } from 'react';

export type Rol = 'admin' | 'usuario';

export const TOKEN_KEY = 'observatorio_token';
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Pequeño bus de eventos para que TODOS los useAuth() de la página se enteren
// del login/logout a la vez (localStorage no dispara 'storage' en la misma
// pestaña que lo modifica).
const EVENTO = 'observatorio:auth';

function leerToken(): string | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function escribirToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* modo privado o storage bloqueado: la sesión dura lo que dure la página */
  }
  window.dispatchEvent(new Event(EVENTO));
}

/** Cabeceras a añadir a cualquier fetch que llame un endpoint protegido. */
export function authHeaders(): Record<string, string> {
  const token = leerToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  // `cargando` evita el parpadeo "usuario → admin" en el primer render del
  // cliente, cuando todavía no se ha leído localStorage.
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const sincronizar = () => setToken(leerToken());
    sincronizar();
    setCargando(false);
    window.addEventListener(EVENTO, sincronizar);
    window.addEventListener('storage', sincronizar);
    return () => {
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
