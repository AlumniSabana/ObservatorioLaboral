-- ============================================================================
-- Migración 005 — LinkedIn (ofertas públicas) como fuente de vacantes
--
-- Ejecutar en el SQL Editor de Supabase.
--
-- ⚠️ ESTA TABLA NACE VACÍA Y PUEDE QUEDARSE ASÍ.
-- La recolección de LinkedIn está DESACTIVADA por defecto (config.LINKEDIN_HABILITADO).
-- Crear la tabla no recolecta nada: solo deja la infraestructura lista para
-- cuando la Universidad apruebe el uso. Ver LinkedIn/linkedin_service.py.
--
-- ALCANCE DEL DATO (importante para privacidad):
--   Se guardan ÚNICAMENTE ofertas de empleo publicadas por empresas. NO se
--   almacena ningún dato de personas (ni candidatos, ni reclutadores, ni
--   perfiles), por lo que esta tabla NO contiene datos personales sujetos a la
--   Ley 1581 de 2012 (habeas data).
--
-- Sigue el mismo patrón que `vacantes_google` (migración 004): tabla propia por
-- fuente, porque cada plataforma entrega campos distintos. La unificación para
-- Tendencias se hace después hacia `vacantes_historicas`.
-- ============================================================================

create table if not exists vacantes_linkedin (
    -- Id de la oferta en LinkedIn (numérico largo, se guarda como texto).
    job_id                text primary key,

    -- Datos públicos de la OFERTA (nada de personas).
    title                 text,
    company               text,          -- empresa que publica (persona jurídica)
    location              text,
    city                  text,
    posted_at             text,          -- fecha relativa tal como la entrega LinkedIn
    fecha_publicacion     date,          -- posted_at ya convertido a fecha absoluta
    apply_link            text,
    description           text,          -- descripción completa (si se pidió el detalle)

    -- Metadatos que LinkedIn expone en el detalle de la oferta. `seniority` es la
    -- ventaja frente a Adzuna/Google: viene DECLARADO, no inferido del título.
    seniority             text,
    employment_type       text,
    job_function          text,
    industries            text,

    -- Trazabilidad de la recolección.
    keyword               text,          -- término de búsqueda que la encontró
    programa_relacionado  text,          -- programa académico asociado
    pais                  text default 'co',
    recolectado_en        timestamptz default now()
);

-- Consultas típicas: por programa y por fecha de publicación.
create index if not exists idx_vac_linkedin_programa
    on vacantes_linkedin (programa_relacionado);

create index if not exists idx_vac_linkedin_fecha
    on vacantes_linkedin (fecha_publicacion);
