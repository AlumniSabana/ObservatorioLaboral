'use client';

/**
 * Componentes de navegación compartidos por todas las páginas:
 *
 *  - <Sidebar />    : la barra lateral fija con los enlaces a cada sección.
 *  - <PageLayout /> : envoltura estándar de página (sidebar + título + contenido).
 *
 * Casi todas las páginas usan <PageLayout> para mantener una estructura visual
 * consistente. Los íconos vienen de la librería lucide-react.
 */

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import {
  GraduationCap,
  DollarSign,
  TrendingUp,
  Sparkles,
  ClipboardList,
  MessagesSquare,
  FileText,
  LogIn,
  LogOut,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';

// Lista única de enlaces de la barra lateral. Para agregar/quitar una sección,
// edita este arreglo (href = ruta, label = texto visible, icon = ícono).
const navigationItems = [
  { href: '/', label: 'Tendencias', icon: TrendingUp },
  { href: '/skills-demandadas', label: 'Competencias', icon: Sparkles },
  { href: '/cursos', label: 'Cursos y formación', icon: GraduationCap },
  { href: '/salaries', label: 'Análisis salarial', icon: DollarSign },
  { href: '/perfil-ocupacional', label: 'Perfil ocupacional', icon: ClipboardList },
  { href: '/asistente', label: 'Empresas', icon: MessagesSquare },
  { href: '/informes', label: 'Informes', icon: FileText },
];

// Aparte del arreglo de arriba: no es una sección de datos sino el acceso de
// sesión del Administrador, así que va separado visualmente al fondo del menú.
// Ocupa el sitio que antes tenía "Sobre el observatorio" (ese texto vive ahora
// al pie de Informes). Solo se muestra cuando NO hay sesión; con sesión, en su
// lugar aparece "Administrador" + "Cerrar sesión" (ver el <nav> de abajo).
const iniciarSesion = { href: '/login', label: 'Iniciar sesión', icon: LogIn };

// Un mismo botón de enlace para las secciones de datos y para "Iniciar
// sesión", así lucen igual y solo cambia dónde se colocan. Vive fuera de
// <Sidebar> para no recrearse en cada render (React lo trataría como un
// componente nuevo cada vez y perdería el estado/foco del enlace).
function Enlace({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-colors ${
        active ? 'text-white' : 'text-gray-300 hover:bg-opacity-20'
      }`}
      style={active ? { backgroundColor: 'var(--sabana-navy)' } : {}}
    >
      <Icon size={20} className="flex-shrink-0" />
      <span className="text-sm font-medium truncate">{label}</span>
    </Link>
  );
}

export function Sidebar() {
  // Ruta actual: sirve para resaltar el enlace activo.
  const pathname = usePathname();
  // Sesión: decide si el pie del menú ofrece entrar o muestra al Admin con su
  // botón de salir. `cargando` = aún no se sabe (leyendo/verificando el token).
  const { esAdmin, cargando, logout } = useAuth();

  // Un enlace está "activo" si coincide con la ruta actual. Para '/' exigimos
  // coincidencia exacta (si usáramos startsWith, '/' marcaría todo como activo).
  const isActive = (href: string) => {
    if (href === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(href);
  };

  return (
    // flex-col + el <nav> de abajo con mt-auto: el bloque de sesión queda
    // pegado al fondo del panel cuando el contenido no llena la pantalla, y
    // simplemente después del resto cuando sí (gracias a overflow-y-auto).
    <aside className="w-80 text-white h-screen overflow-y-auto border-r fixed left-0 top-0 z-50 flex flex-col" style={{backgroundColor: 'var(--sabana-dark-navy)', borderColor: 'var(--sabana-navy)'}}>
      <div className="px-6 pt-6 pb-2">
        <Image src="/logo-alumni.png" alt="Logo Alumni Sabana" className="w-32 mb-2 mx-auto" width={128} height={128} />
        <p className="text-sm text-center" style={{color: 'var(--sabana-sky-blue)'}}>Observatorio laboral</p>
      </div>

      <nav className="px-4 pt-2 pb-4 space-y-1">
        {navigationItems.map((item) => <Enlace key={item.href} {...item} active={isActive(item.href)} />)}
      </nav>

      <nav className="px-4 pt-2 pb-4 mt-auto border-t space-y-1" style={{ borderColor: 'var(--sabana-navy)' }}>
        {cargando ? (
          // Mismo alto que un enlace (py-2 + ícono de 20 px): reserva el sitio
          // para que el menú no "salte" cuando llegue el veredicto de la sesión.
          <div className="h-9" />
        ) : esAdmin ? (
          <>
            <div className="flex items-center gap-3 px-4 py-2">
              <ShieldCheck size={20} className="flex-shrink-0" style={{ color: 'var(--sabana-sky-blue)' }} />
              <span className="text-sm font-medium truncate text-white">Administrador</span>
            </div>
            <button
              type="button"
              onClick={logout}
              className="w-full flex items-center gap-3 px-4 py-2 rounded-lg transition-colors text-gray-300 hover:bg-white/10 cursor-pointer"
            >
              <LogOut size={20} className="flex-shrink-0" />
              <span className="text-sm font-medium truncate">Cerrar sesión</span>
            </button>
          </>
        ) : (
          <Enlace {...iniciarSesion} active={isActive(iniciarSesion.href)} />
        )}
      </nav>
    </aside>
  );
}

export function PageLayout({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black" style={{backgroundColor: 'var(--white-background)'}}>
      <Sidebar />
      <main className="ml-80 flex-1 p-8">
        {/* Contenido a todo el ancho disponible (uniforme en todas las páginas). */}
        <div className="w-full">
          <h1 className="text-4xl font-bold mb-2" style={{color: 'var(--sabana-dark-navy)'}}>
            {title}
          </h1>
          <div className="h-1 w-20 rounded mb-8" style={{backgroundColor: 'var(--sabana-navy)'}}></div>
          {children}
        </div>
      </main>
    </div>
  );
}
