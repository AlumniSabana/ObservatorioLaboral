'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Home,
  TrendingUp,
  Briefcase,
  DollarSign,
  Building2,
  Users,
  Zap,
  ChevronLeft,
} from 'lucide-react';

const navigationItems = [
  { href: '/', label: 'Inicio', icon: Home },
  { href: '/trends', label: 'Tendencias en', icon: TrendingUp },
  {
    href: '/skills',
    label: 'Competencias y Habilidades apetecidas',
    icon: Briefcase,
  },
  { href: '/salaries', label: 'Análisis Salarial', icon: DollarSign },
  { href: '/sectors', label: 'Sectores y Empresas', icon: Building2 },
  {
    href: '/conditions',
    label: 'Condiciones laborales actuales',
    icon: Users,
  },
  { href: '/demand', label: 'Mayor demanda actual', icon: Zap },
];

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(href);
  };

  return (
    <aside className="w-64 bg-zinc-900 text-white h-screen overflow-y-auto border-r border-zinc-800 fixed left-0 top-0 z-50">
      <div className="p-6">
        <h1 className="text-2xl font-bold tracking-tight">Alumni Sabana</h1>
        <p className="text-sm text-zinc-400 mt-1">Observatorio Laboral</p>
      </div>

      <nav className="px-4 py-6 space-y-2">
        {navigationItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                active
                  ? 'bg-blue-600 text-white'
                  : 'text-zinc-300 hover:bg-zinc-800'
              }`}
            >
              <Icon size={20} className="flex-shrink-0" />
              <span className="text-sm font-medium truncate">{label}</span>
            </Link>
          );
        })}
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
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black">
      <Sidebar />
      <main className="ml-64 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-black dark:text-white mb-2">
            {title}
          </h1>
          <div className="h-1 w-20 bg-blue-600 rounded mb-8"></div>
          {children}
        </div>
      </main>
    </div>
  );
}
