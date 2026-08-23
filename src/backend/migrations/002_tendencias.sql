-- ============================================================================
-- Migración 002 — Tendencias temporales
--
-- Ejecutar en el SQL Editor de Supabase (el cliente de Python no corre DDL).
--
-- Crea dos tablas:
--
--   vacantes_historicas    Muestra histórica de vacantes recolectada con el
--                          backfill (Adzuna: max_days_old + sort_direction=up).
--                          Vive aparte de `vacantes` para que el scrape normal
--                          (POST /scrape?borrar=true) NUNCA borre la historia.
--
--   tendencias_observaciones  Serie temporal ya agregada: para cada término
--                          (cargo o sector) y cada mes, cuántas vacantes lo
--                          mencionan y qué proporción del total de ese mes
--                          representan (`share`).
--
-- Por qué `share` y no menciones absolutas: cada mes se muestrea con un número
-- distinto de vacantes, así que los conteos crudos no son comparables entre
-- meses. El share (menciones / vacantes del mes) sí lo es.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Muestra histórica cruda
-- ---------------------------------------------------------------------------
create table if not exists vacantes_historicas (
    id                   bigint primary key,          -- id real de Adzuna
    title                text,
    company              text,
    category             text,                        -- sector
    contract_time        text,
    salary_min           double precision,
    salary_max           double precision,
    created_at           timestamptz,                 -- FECHA DE PUBLICACIÓN real
    fuente               text not null default 'adzuna',
    pais                 text not null default 'us',
    keyword              text,                        -- trazabilidad
    programa_relacionado text,
    recolectado_en       timestamptz not null default now()
);

-- El grueso de las consultas filtra/agrupa por fecha de publicación.
create index if not exists idx_vac_hist_created  on vacantes_historicas (created_at);
create index if not exists idx_vac_hist_fuente   on vacantes_historicas (fuente, pais);


-- ---------------------------------------------------------------------------
-- 1b. Volumen real por keyword y mes (para ponderar la muestra)
--
-- La muestra de `vacantes_historicas` está BALANCEADA por construcción: se piden
-- ~50 vacantes por keyword y por mes, así que 'software engineer' y 'chef'
-- aportan lo mismo aunque el mercado publique 100x más de uno que del otro.
-- Sin corregir eso, todos los sectores salen "estables".
--
-- La API de Adzuna devuelve, gratis en la misma respuesta, un campo `count` con
-- el total real de vacantes que coinciden en la ventana. Restando ventanas
-- consecutivas se obtiene el volumen real publicado en cada mes, que se usa
-- para dar a cada vacante muestreada el peso que le corresponde.
-- ---------------------------------------------------------------------------
create table if not exists muestreo_volumen (
    id             bigserial primary key,
    keyword        text not null,
    periodo        date not null,          -- primer día del mes
    fuente         text not null default 'adzuna',
    pais           text not null default 'us',
    volumen        integer not null,       -- vacantes REALES publicadas ese mes (count diferenciado)
    n_muestreadas  integer not null,       -- cuántas de esas guardamos realmente
    actualizado_en timestamptz not null default now(),

    constraint muestreo_volumen_unico unique (keyword, periodo, fuente, pais)
);


-- ---------------------------------------------------------------------------
-- 2. Serie temporal agregada
-- ---------------------------------------------------------------------------
create table if not exists tendencias_observaciones (
    id             bigserial primary key,
    dimension      text not null,          -- 'cargo' | 'sector' | (futuro) 'skill'
    termino        text not null,          -- ej. 'software engineer' | 'IT Jobs'
    periodo        date not null,          -- primer día del mes (2026-06-01)
    fuente         text not null default 'adzuna',
    pais           text not null default 'us',
    -- `menciones` y `n_vacantes` son estimaciones PONDERADAS del mercado
    -- (la muestra se reescala por el volumen real de cada keyword), no conteos
    -- de la muestra. `muestra` sí es el conteo crudo, y es lo que se usa para
    -- descartar términos con soporte insuficiente: sin él, una sola vacante
    -- multiplicada por un peso alto parecería una tendencia enorme.
    menciones      integer not null,       -- vacantes estimadas del mes con ese término
    n_vacantes     integer not null,       -- vacantes estimadas del mes en total
    muestra        integer not null default 0,  -- vacantes REALES muestreadas con ese término
    share          double precision not null,   -- menciones / n_vacantes
    actualizado_en timestamptz not null default now(),

    -- Permite reejecutar el backfill sin duplicar: se hace upsert sobre esta clave.
    constraint tendencias_obs_unica
        unique (dimension, termino, periodo, fuente, pais)
);

create index if not exists idx_tend_dim_periodo
    on tendencias_observaciones (dimension, fuente, pais, periodo);
