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
  BarChart3,
} from 'lucide-react';

const navigationItems = [
  { href: '/', label: 'Inicio', icon: Home },
  { href: '/analytics', label: 'Análisis de mercado (Adzuna)', icon: BarChart3 },
  { href: '/trends', label: 'Tendencias en formación', icon: TrendingUp },
  {
    href: '/skills',
    label: 'Competencias y habilidades',
    icon: Briefcase,
  },
  { href: '/salaries', label: 'Análisis salarial', icon: DollarSign },
  { href: '/sectors', label: 'Sectores y empresas', icon: Building2 },
  {
    href: '/conditions',
    label: 'Condiciones laborales',
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
    <aside className="w-80 text-white h-screen overflow-y-auto border-r fixed left-0 top-0 z-50" style={{backgroundColor: 'var(--sabana-dark-navy)', borderColor: 'var(--sabana-navy)'}}>
      <div className="p-6">
        <h1 className="text-2xl font-bold tracking-tight">Alumni Sabana</h1>
        <p className="text-sm mt-1" style={{color: 'var(--sabana-sky-blue)'}}>Observatorio laboral</p>
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
                  ? 'text-white'
                  : 'text-gray-300 hover:bg-opacity-20'
              }`}
              style={active ? {backgroundColor: 'var(--sabana-navy)'} : {}}
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
    <div className="flex min-h-screen bg-zinc-50 dark:bg-black" style={{backgroundColor: 'var(--white-background)'}}>
      <Sidebar />
      <main className="ml-80 flex-1 p-8">
        <div className="max-w-4xl mx-auto">
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
