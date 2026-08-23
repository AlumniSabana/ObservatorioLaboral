-- ============================================================================
-- Migración 010 — OLE (MinEducación): ingreso de graduados por programa
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 009.
--
-- QUÉ RESUELVE
-- Hoy `/salaries` estima el salario de un programa por VÍA INDIRECTA: mapea el
-- programa a un código de ocupación (PROGRAMA_CNO) y lee la GEIH, que mide el
-- ingreso de quien EJERCE esa ocupación, venga de donde venga. El OLE mide otra
-- cosa, y es exactamente la que le importa a Alumni: cuánto cotizan los
-- GRADUADOS de un programa concreto — incluidos los 28.402 de La Sabana.
--
-- NO SUSTITUYE A LA GEIH, la acompaña. Miden universos distintos:
--   GEIH  → ingreso declarado en encuesta, por ocupación, cualquier formación.
--   OLE   → Ingreso Base de Cotización en seguridad social, por programa e IES.
-- El IBC además tiende a SUBESTIMAR el ingreso real de los independientes, que
-- cotizan sobre el 40% de sus honorarios. Hay que decirlo en la UI.
--
-- ⚠️ EL INGRESO VIENE EN RANGOS DE SMMLV, NO EN PESOS
-- El OLE publica 7 bandas ('1 SMMLV', 'Entre 1 y 1,5 SMMLV', … 'Más de 9
-- SMMLV') con el CONTEO de graduados en cada una. No hay valor puntual. Por eso
-- se guarda la distribución completa y la mediana se estima por interpolación
-- (ver `ole_service._mediana_interpolada`). Guardar una media aquí sería
-- inventarse un dato que la fuente no da.
--
-- DOS TABLAS, DOS GRANOS, A PROPÓSITO
-- De La Sabana se guarda el detalle completo (son 8.645 filas, es gratis).
-- Del resto del país solo el agregado por nombre de programa, que es lo único
-- que se usa: el contraste "nuestro Ingeniería Industrial vs. el del país".
-- ============================================================================

-- ── Detalle de La Sabana ────────────────────────────────────────────────────
create table if not exists ole_ibc_sabana (
    id              bigserial primary key,
    codigo_snies    int  not null,
    programa        text not null,        -- nombre tal cual lo publica el OLE
    nivel_formacion text not null,        -- Universitario, Especialización, Maestría…
    sexo            text,
    anio_grado      int  not null,
    rango           text not null,        -- banda de SMMLV, literal de la fuente
    graduados       int  not null,
    anio_corte      int  not null default 2023,

    constraint uq_ole_sabana unique (codigo_snies, nivel_formacion, sexo, anio_grado, rango, anio_corte)
);

create index if not exists idx_ole_sabana_prog on ole_ibc_sabana (programa, nivel_formacion);
create index if not exists idx_ole_sabana_anio on ole_ibc_sabana (anio_grado);


-- ── Referencia nacional, agregada por nombre de programa ────────────────────
-- La llave es el NOMBRE normalizado y no el código SNIES a propósito: cada IES
-- registra su propio código para el mismo programa, así que el código no sirve
-- para comparar entre instituciones. El nombre sí (con sus imprecisiones).
create table if not exists ole_ibc_nacional (
    id              bigserial primary key,
    programa        text not null,
    nivel_formacion text not null,
    rango           text not null,
    graduados       int  not null,
    n_ies           int,                  -- cuántas instituciones lo ofrecen
    anio_corte      int  not null default 2023,

    constraint uq_ole_nacional unique (programa, nivel_formacion, rango, anio_corte)
);

create index if not exists idx_ole_nacional_prog on ole_ibc_nacional (programa, nivel_formacion);
