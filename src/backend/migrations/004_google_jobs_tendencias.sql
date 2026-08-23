-- ============================================================================
-- Migración 004 — Google Jobs como fuente de tendencias y skills
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 002 y 003.
--
-- Conecta Google Jobs (Colombia) con el módulo de Tendencias/Skills, que hasta
-- ahora solo se alimentaba de Adzuna. Añade dos columnas a `vacantes_historicas`:
--
--   skills        Skills OBSERVADAS en el texto de la vacante (array JSON).
--                 Es la gran ventaja de Google Jobs frente a Adzuna: entrega la
--                 descripción COMPLETA (~2.100 caracteres de media, frente a los
--                 500 truncados de Adzuna), así que las skills sí se pueden
--                 extraer del texto real en vez de derivarlas de O*NET.
--                 Queda NULL en las filas de Adzuna (no hay texto suficiente).
--
--   ref_externa   Id original de la vacante en su fuente. `id` es bigint (era el
--                 id numérico de Adzuna), pero Google Jobs usa un job_id de texto
--                 largo, así que ahí se guarda un hash estable del job_id y el
--                 valor original queda aquí para trazabilidad.
--
-- No se toca nada de Adzuna: ambas columnas son opcionales.
-- ============================================================================

alter table vacantes_historicas
    add column if not exists skills      jsonb,
    add column if not exists ref_externa text;

-- Las consultas de tendencias filtran por (fuente, pais) además de la fecha.
create index if not exists idx_vac_hist_fuente_pais_fecha
    on vacantes_historicas (fuente, pais, created_at);

-- Evita reinsertar la misma vacante de una fuente con id de texto.
create unique index if not exists idx_vac_hist_ref_externa
    on vacantes_historicas (fuente, ref_externa)
    where ref_externa is not null;
