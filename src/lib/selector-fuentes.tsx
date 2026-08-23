'use client';

/**
 * <SelectorFuentes /> — desplegable con checkboxes para elegir de qué fuentes
 * salen los datos. Se usa en Tendencias y en Skills más demandadas.
 *
 * Sustituye a las hileras de botones que había antes: al sumar informes PDF a los
 * mercados de vacantes, la lista dejó de caber y hacía falta agrupar.
 *
 * Tres cosas que el componente hace a propósito:
 *  - AGRUPA por naturaleza del dato (vacantes / normativo / informes), porque
 *    mezclarlas sin distinguir invita a leerlas como si fueran lo mismo.
 *  - DESHABILITA con motivo visible las fuentes que no aplican a la vista (p. ej.
 *    un informe anual no puede dibujar una serie mensual), en vez de ocultarlas:
 *    así el usuario entiende por qué no está, en lugar de creer que falta.
 *  - RESUME en el botón qué fuentes están activas, que es lo que pidió el usuario.
 */

import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Check, Info } from 'lucide-react';

export interface FuenteOpcion {
  /** Identificador estable: 'adzuna:us', 'onet', 'informe:coursera-2024'. */
  id: string;
  label: string;
  sublabel?: string;
  /** Agrupa en el desplegable. */
  tipo?: 'vacantes' | 'normativo' | 'informe';
  /** 'observado' (vacantes reales) | 'normativo' (O*NET) | 'declarado' (informes). */
  naturaleza?: string;
  /** Dimensiones que soporta: cargo, sector, skill. */
  dimensiones?: string[];
  /** Nota informativa (sesgos, universo medido…). */
  nota?: string;
  /**
   * Código de mercado ('co', 'co_li', 'us', 'gb'…). Solo lo traen las fuentes de
   * vacantes. Si al menos una es colombiana y al menos una no lo es, el
   * componente ofrece el atajo Colombia / Todas.
   */
  pais?: string;
}

/** Colombia agrupa 'co' (Google Jobs) y 'co_li' (LinkedIn), que van separados
 *  a propósito para no mezclarse en la combinación de mercados. */
const esColombiana = (f: FuenteOpcion) => (f.pais ?? '').toLowerCase().startsWith('co');

const GRUPOS: { clave: string; titulo: string; ayuda: string }[] = [
  { clave: 'vacantes', titulo: 'Vacantes publicadas', ayuda: 'Ofertas reales recolectadas del mercado' },
  { clave: 'normativo', titulo: 'Referencia ocupacional', ayuda: 'Qué requiere cada ocupación, no qué se demanda hoy' },
  { clave: 'informe', titulo: 'Informes de terceros', ayuda: 'Cifras declaradas por su editor, no medidas por el Observatorio' },
];

export function SelectorFuentes({
  fuentes,
  seleccionadas,
  onChange,
  dimensionActiva,
  etiqueta = 'Fuentes de datos',
}: {
  fuentes: FuenteOpcion[];
  seleccionadas: string[];
  onChange: (ids: string[]) => void;
  /** Si se indica, las fuentes que no la soportan salen deshabilitadas con motivo. */
  dimensionActiva?: string;
  etiqueta?: string;
}) {
  const [abierto, setAbierto] = useState(false);
  const cajaRef = useRef<HTMLDivElement>(null);

  // Cerrar al hacer clic fuera o con Escape.
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (cajaRef.current && !cajaRef.current.contains(e.target as Node)) setAbierto(false);
    };
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false);
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', fuera);
      document.removeEventListener('keydown', escape);
    };
  }, [abierto]);

  const noAplica = (f: FuenteOpcion): string | null => {
    const tipo = f.tipo ?? 'vacantes';
    // Las fuentes de VACANTES siempre se pueden elegir aunque no tengan serie de
    // esta dimensión: siguen alimentando el resto de la vista (p. ej. Google Jobs
    // no produce tendencias de cargo, pero sí cuenta en "Demanda actual").
    if (tipo === 'vacantes') return null;
    if (!dimensionActiva || !f.dimensiones) return null;
    if (f.dimensiones.includes(dimensionActiva)) return null;
    return tipo === 'informe' ? 'sin serie temporal' : `no aporta ${dimensionActiva}`;
  };

  const alternar = (f: FuenteOpcion) => {
    if (noAplica(f)) return;
    const activa = seleccionadas.includes(f.id);
    // Nunca se permite quedarse sin ninguna fuente: no habría nada que mostrar.
    if (activa && seleccionadas.length === 1) return;
    onChange(activa ? seleccionadas.filter((x) => x !== f.id) : [...seleccionadas, f.id]);
  };

  const activas = fuentes.filter((f) => seleccionadas.includes(f.id));
  const resumen =
    activas.length === 0 ? 'Ninguna'
      : activas.length <= 2 ? activas.map((f) => f.label).join(' · ')
        : `${activas[0].label} y ${activas.length - 1} más`;

  const disponibles = fuentes.filter((f) => !noAplica(f));
  const todasMarcadas = disponibles.length > 0 && disponibles.every((f) => seleccionadas.includes(f.id));

  // Atajo Colombia / Todas. Actúa SOLO sobre las fuentes de vacantes: O*NET y
  // los informes no son un mercado geográfico, así que desmarcarlos al pedir
  // "Colombia" sería un efecto colateral que nadie pidió.
  const mercados = disponibles.filter((f) => (f.tipo ?? 'vacantes') === 'vacantes');
  const otras = disponibles.filter((f) => (f.tipo ?? 'vacantes') !== 'vacantes');
  const nacionales = mercados.filter(esColombiana);
  const hayMezcla = nacionales.length > 0 && nacionales.length < mercados.length;
  const conservarOtras = otras.filter((f) => seleccionadas.includes(f.id)).map((f) => f.id);
  const soloNacionales =
    nacionales.length > 0 &&
    nacionales.every((f) => seleccionadas.includes(f.id)) &&
    mercados.filter((f) => !esColombiana(f)).every((f) => !seleccionadas.includes(f.id));

  const claseAtajo = (activo: boolean) =>
    'px-2.5 py-1 text-[0.7rem] font-semibold rounded-md border cursor-pointer transition-colors ' +
    (activo ? 'shadow-sm' : 'opacity-60 hover:opacity-100');
  const estiloAtajo = (activo: boolean) => ({
    backgroundColor: activo ? 'var(--sabana-dark-navy)' : 'transparent',
    color: activo ? 'white' : 'var(--sabana-navy)',
    borderColor: 'var(--sabana-light-blue)',
  });

  return (
    <div ref={cajaRef} className="relative">
      <div className="flex items-end justify-between gap-2 mb-1">
        <label
          className="flex items-end min-h-[2.1rem] text-xs font-bold uppercase tracking-wide leading-tight"
          style={{ color: 'var(--sabana-navy)' }}
        >
          {etiqueta}
        </label>

        {hayMezcla && (
          <div className="flex items-center gap-1 shrink-0 pb-0.5">
            <button
              type="button"
              onClick={() => onChange([...nacionales.map((f) => f.id), ...conservarOtras])}
              className={claseAtajo(soloNacionales)}
              style={estiloAtajo(soloNacionales)}
              title="Usar solo las fuentes del mercado colombiano"
            >
              🇨🇴 Colombia
            </button>
            <button
              type="button"
              onClick={() => onChange(disponibles.map((f) => f.id))}
              className={claseAtajo(todasMarcadas)}
              style={estiloAtajo(todasMarcadas)}
              title="Usar todas las fuentes, nacionales e internacionales"
            >
              Todas
            </button>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="w-full flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm font-semibold border cursor-pointer"
        style={{
          backgroundColor: 'var(--sabana-sky-blue)',
          color: 'var(--sabana-dark-navy)',
          borderColor: 'var(--sabana-light-blue)',
        }}
      >
        <span className="truncate text-left">
          {resumen}
          <span className="font-normal opacity-70"> ({activas.length})</span>
        </span>
        <ChevronDown size={16} className={abierto ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>

      {abierto && (
        <div
          className="absolute z-50 mt-1 w-full min-w-[19rem] max-h-[24rem] overflow-y-auto rounded-lg border shadow-lg p-2"
          style={{ backgroundColor: 'var(--white-background)', borderColor: 'var(--sabana-light-blue)' }}
        >
          <button
            type="button"
            onClick={() => onChange(todasMarcadas ? [disponibles[0].id] : disponibles.map((f) => f.id))}
            className="w-full text-left text-xs font-semibold px-2 py-1.5 rounded cursor-pointer"
            style={{ color: 'var(--sabana-navy)' }}
          >
            {todasMarcadas ? 'Dejar solo la primera' : 'Seleccionar todas'}
          </button>

          {GRUPOS.map((g) => {
            const delGrupo = fuentes.filter((f) => (f.tipo ?? 'vacantes') === g.clave);
            if (delGrupo.length === 0) return null;
            return (
              <div key={g.clave} className="mt-2">
                <p className="px-2 text-[0.68rem] font-bold uppercase tracking-wide" style={{ color: 'var(--sabana-navy)' }}>
                  {g.titulo}
                </p>
                <p className="px-2 mb-1 text-[0.68rem]" style={{ color: 'var(--sabana-black-50)' }}>
                  {g.ayuda}
                </p>

                {delGrupo.map((f) => {
                  const motivo = noAplica(f);
                  const activa = seleccionadas.includes(f.id);
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => alternar(f)}
                      disabled={!!motivo}
                      title={f.nota || motivo || undefined}
                      className="w-full flex items-start gap-2 px-2 py-1.5 rounded text-left text-sm disabled:opacity-45 disabled:cursor-not-allowed hover:bg-black/5 cursor-pointer"
                      style={{ color: 'var(--sabana-dark-navy)' }}
                    >
                      <span
                        className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border"
                        style={{
                          borderColor: 'var(--sabana-light-blue)',
                          backgroundColor: activa ? 'var(--sabana-dark-navy)' : 'transparent',
                        }}
                      >
                        {activa && <Check size={12} color="white" />}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block truncate">{f.label}</span>
                        {(f.sublabel || motivo) && (
                          <span className="block text-[0.7rem] truncate" style={{ color: 'var(--sabana-black-50)' }}>
                            {motivo ? `No aplica aquí: ${motivo}` : f.sublabel}
                          </span>
                        )}
                      </span>
                      {f.naturaleza === 'declarado' && !motivo && (
                        <Info size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--sabana-black-50)' }} />
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {/* Qué se está usando, siempre visible (sin abrir el desplegable). */}
      {activas.length > 0 && (
        <p className="mt-1.5 text-[0.7rem] leading-snug" style={{ color: 'var(--sabana-black-50)' }}>
          Usando: {activas.map((f) => f.label).join(' · ')}
        </p>
      )}
    </div>
  );
}
