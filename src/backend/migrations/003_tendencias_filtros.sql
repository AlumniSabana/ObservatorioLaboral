-- ============================================================================
-- Migración 003 — Filtros precalculados en tendencias
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 002_tendencias.sql.
--
-- Añade dos columnas de segmentación a `tendencias_observaciones`:
--
--   programa   Programa académico de La Sabana asociado a la vacante.
--   seniority  Nivel de experiencia inferido del título crudo
--              ('senior' | 'junior' | 'graduado' | 'no_especificado').
--
-- Cada combinación (dimension × programa × seniority × término × mes) se
-- precalcula y se guarda como una fila. El valor centinela 'TODOS' representa
-- el agregado sin filtrar; así el frontend pide siempre la misma tabla:
--
--   sin filtros            -> programa='TODOS'  seniority='TODOS'
--   solo Derecho           -> programa='Derecho' seniority='TODOS'
--   solo Derecho + senior  -> programa='Derecho' seniority='senior'
--
-- La contrapartida (asumida a propósito) es que añadir un filtro nuevo obliga a
-- recalcular toda la tabla, y que el número de filas crece con el producto de
-- las combinaciones.
-- ============================================================================

alter table tendencias_observaciones
    add column if not exists programa  text not null default 'TODOS',
    add column if not exists seniority text not null default 'TODOS';

-- La clave única vieja (sin programa/seniority) colisionaría: una misma
-- (dimension, término, periodo) existe ahora una vez por cada combinación.
alter table tendencias_observaciones
    drop constraint if exists tendencias_obs_unica;

alter table tendencias_observaciones
    add constraint tendencias_obs_unica
    unique (dimension, termino, periodo, fuente, pais, programa, seniority);

-- El frontend siempre filtra por (dimension, programa, seniority) y ordena por
-- periodo: este índice cubre exactamente ese acceso.
drop index if exists idx_tend_dim_periodo;
create index if not exists idx_tend_filtros
    on tendencias_observaciones (dimension, programa, seniority, fuente, pais, periodo);
