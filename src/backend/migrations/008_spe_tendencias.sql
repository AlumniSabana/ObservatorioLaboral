-- ============================================================================
-- Migración 008 — Serie temporal del SPE (Anexo_tendencias)
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 007.
--
-- QUÉ APORTA
-- El anexo de ocupaciones y competencias (migración 007) es una FOTO del periodo
-- cargado. Este otro anexo trae la SERIE MENSUAL nacional: cómo se movieron mes a
-- mes las ocupaciones más demandadas y las competencias pedidas.
--
-- Es la primera tendencia OBSERVADA en Colombia del Observatorio: hasta ahora las
-- series venían de Adzuna (mercados extranjeros) o eran derivadas de O*NET.
--
-- Se guarda aparte de `spe_competencias` porque tiene otra granularidad: aquí NO
-- hay CIUO ni departamento, son totales nacionales por mes. Mezclarlas llevaría a
-- sumar un agregado nacional con sus propios desgloses y contar doble.
-- ============================================================================

create table if not exists spe_tendencias (
    id            bigserial primary key,
    periodo       date not null,        -- primer día del mes
    anio          int  not null,
    mes           int  not null,

    -- 'ocupacion'   -> demanda de esa ocupación (nº de vacantes)
    -- 'transversal' -> menciones de esa competencia blanda
    -- 'digital'     -> menciones de esa categoría digital
    dimension     text not null,
    termino       text not null,
    valor         double precision not null default 0,

    fuente_anexo  text,
    constraint uq_spe_tend unique (periodo, dimension, termino)
);

create index if not exists idx_spe_tend_dim on spe_tendencias (dimension, periodo);
create index if not exists idx_spe_tend_ter on spe_tendencias (termino);
