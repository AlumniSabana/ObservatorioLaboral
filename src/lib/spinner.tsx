'use client';

/**
 * <Spinner /> — indicador de carga visual, para no depender solo de texto
 * ("Cargando…") que pasa desapercibido. Se usa en Tendencias, Competencias y
 * Perfil ocupacional: en las tres, cambiar un filtro dispara un fetch que
 * puede tardar varios segundos (Perfil ocupacional llega a ~10s al cambiar de
 * programa), y sin una señal visual clara el usuario puede pensar que lo que
 * ve en pantalla ya es el resultado nuevo cuando en realidad sigue cargando.
 */
export function Spinner({
  label,
  size = 'md',
  /** Para usar dentro de tarjetas u otros espacios chicos: menos padding y
   *  texto más discreto que el uso de página completa. */
  compact = false,
}: {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  compact?: boolean;
}) {
  const px = size === 'sm' ? 16 : size === 'lg' ? 40 : 24;
  return (
    <div className={`flex items-center justify-center gap-3 ${compact ? 'py-2' : 'py-12'}`}>
      <div
        className="rounded-full animate-spin"
        style={{
          width: px,
          height: px,
          border: `${Math.max(2, px / 8)}px solid var(--sabana-sky-blue)`,
          borderTopColor: 'var(--sabana-dark-navy)',
        }}
        role="status"
        aria-label={label ?? 'Cargando'}
      />
      {label && (
        <p
          className={compact ? 'text-sm text-zinc-500' : 'text-lg font-bold'}
          style={compact ? undefined : { color: 'var(--sabana-dark-navy)' }}
        >
          {label}
        </p>
      )}
    </div>
  );
}
