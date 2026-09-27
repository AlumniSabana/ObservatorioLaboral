'use client';

/**
 * Ruta '/login': inicio de sesión del Administrador.
 *
 * Solo existe un rol con sesión (el equipo de la Dirección de Alumni); el
 * visitante común no necesita entrar, así que la página lo dice de frente en
 * vez de parecer un muro. Las credenciales se validan en el backend
 * (POST /auth/login, ver src/backend/auth.py): aquí solo se recogen, se
 * muestran los errores y, al entrar, se redirige a Tendencias.
 *
 * Si ya hay sesión no se muestra el formulario: se ofrece volver o cerrarla
 * (llegar aquí con sesión suele ser por el botón "atrás" del navegador).
 */

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, Lock, LogIn, LogOut, Mail, ShieldCheck } from 'lucide-react';
import { PageLayout } from '@/lib/sidebar';
import { useAuth } from '@/lib/auth';

// Mismo estilo de campo que los formularios de Informes, para que la app se
// sienta una sola. `pl-10` deja sitio al ícono que va dentro del campo.
const campo = 'w-full rounded-lg border px-3 py-2 pl-10 text-sm outline-none focus:ring-2';
const estiloCampo = { borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' };
const tarjeta = 'bg-white dark:bg-zinc-800 rounded-lg p-6 shadow border-l-4 space-y-4';

export default function LoginPage() {
  const router = useRouter();
  const { esAdmin, cargando, login, logout } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [verPassword, setVerPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError('Escribe el correo y la contraseña.');
      return;
    }
    setEnviando(true);
    try {
      await login(email.trim(), password);
      // replace, no push: que "atrás" no devuelva al formulario ya resuelto.
      router.replace('/');
    } catch (err) {
      // fetch lanza TypeError cuando ni siquiera hay conexión con el backend;
      // el resto son mensajes del propio backend (401 "Correo o contraseña…").
      setError(
        err instanceof TypeError
          ? 'No se pudo contactar al servidor. Verifica que el backend esté en línea.'
          : err instanceof Error
            ? err.message
            : 'No se pudo iniciar sesión.',
      );
      setEnviando(false);
    }
  };

  return (
    <PageLayout title="Iniciar sesión">
      <div className="max-w-md space-y-6">
        <p className="text-base leading-relaxed" style={{ color: 'var(--sabana-black-70)' }}>
          Este acceso es para el equipo de la Dirección de Alumni. Como visitante no
          necesitas iniciar sesión: todos los análisis del Observatorio son de libre consulta.
        </p>

        {cargando ? (
          <p className="text-sm" style={{ color: 'var(--sabana-black-50)' }}>Comprobando sesión…</p>
        ) : esAdmin ? (
          <div className={tarjeta} style={{ borderColor: 'var(--sabana-light-blue)' }}>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5" style={{ color: 'var(--sabana-navy)' }} />
              <h2 className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
                Sesión de Administrador activa
              </h2>
            </div>
            <p className="text-sm" style={{ color: 'var(--sabana-black-70)' }}>
              Ya iniciaste sesión. Puedes volver a los análisis o cerrar la sesión en este equipo.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/"
                className="px-5 py-2 rounded-lg font-semibold text-white"
                style={{ backgroundColor: 'var(--sabana-dark-navy)' }}
              >
                Ir a Tendencias
              </Link>
              <button
                type="button"
                onClick={logout}
                className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold border cursor-pointer"
                style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' }}
              >
                <LogOut size={18} />
                Cerrar sesión
              </button>
            </div>
          </div>
        ) : (
          // noValidate: la validación la hacemos nosotros para mostrar los
          // errores con el mismo estilo que el resto de la app, no el globo
          // nativo del navegador.
          <form onSubmit={enviar} noValidate className={tarjeta} style={{ borderColor: 'var(--sabana-light-blue)' }}>
            <div>
              <label htmlFor="login-email" className="block text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                Correo
              </label>
              <div className="relative">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--sabana-navy)' }} />
                <input
                  id="login-email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="correo@unisabana.edu.co"
                  disabled={enviando}
                  className={campo}
                  style={estiloCampo}
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-password" className="block text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                Contraseña
              </label>
              <div className="relative">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--sabana-navy)' }} />
                <input
                  id="login-password"
                  type={verPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={enviando}
                  className={`${campo} pr-10`}
                  style={estiloCampo}
                />
                <button
                  type="button"
                  onClick={() => setVerPassword((v) => !v)}
                  aria-label={verPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer"
                  style={{ color: 'var(--sabana-black-50)' }}
                >
                  {verPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div role="alert" className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-lg font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: enviando ? 'wait' : 'pointer' }}
            >
              <LogIn size={18} />
              {enviando ? 'Entrando…' : 'Iniciar sesión'}
            </button>
          </form>
        )}
      </div>
    </PageLayout>
  );
}
