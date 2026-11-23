'use client';

/**
 * Botón claro/oscuro. La fuente de verdad es el atributo data-theme de <html>
 * (lo fija el script de layout.tsx antes de pintar); aquí solo se lee y se cambia.
 * La elección se guarda en localStorage ('tema') y gana sobre la del sistema.
 */

import { useSyncExternalStore } from 'react';
import { Moon, Sun } from 'lucide-react';

type Tema = 'light' | 'dark';

function suscribir(avisar: () => void) {
  const o = new MutationObserver(avisar);
  o.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  return () => o.disconnect();
}

const leer = (): Tema => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');

export function BotonTema() {
  const tema = useSyncExternalStore(suscribir, leer, () => 'light' as Tema);
  const alternar = () => {
    const nuevo: Tema = tema === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = nuevo;
    try {
      localStorage.setItem('tema', nuevo);
    } catch {
      /* sin almacenamiento: el cambio vale solo para esta visita */
    }
  };
  const etiqueta = tema === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
  return (
    <button
      type="button"
      onClick={alternar}
      aria-label={etiqueta}
      title={etiqueta}
      className="flex-shrink-0 p-2 rounded-lg text-gray-300 hover:bg-white/10 transition-colors cursor-pointer"
    >
      {tema === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
    </button>
  );
}
