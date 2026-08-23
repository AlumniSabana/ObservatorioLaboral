-- ============================================================================
-- Migración 006 — Informes PDF como fuente de datos de skills
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 005.
--
-- QUÉ RESUELVE
-- Permite ingerir informes de terceros (ej. "Coursera Job Skills Report 2024",
-- "WEF Future of Jobs") y usarlos como una FUENTE más junto a Adzuna, Google Jobs
-- y O*NET.
--
-- POR QUÉ TABLAS PROPIAS Y NO `vacantes_historicas` / `tendencias_observaciones`
-- Un informe NO es una muestra de vacantes, es un agregado ANUAL publicado por un
-- tercero. Meterlo en las tablas de vacantes rompería tres cosas:
--   1. `share = menciones / n_vacantes` no tiene denominador en un informe.
--   2. El backfill de tendencias vacía `tendencias_observaciones` en cada corrida
--      y se llevaría los informes por delante.
--   3. El filtro MIN_PERIODOS (3 meses) descartaría siempre un dato de un solo año.
-- Por eso viven aparte y se muestran como CONTRASTE, nunca promediados con vacantes.
--
-- PRIVACIDAD: solo se guardan cifras agregadas publicadas por el informe. Ningún
-- dato personal.
-- ============================================================================

-- ── Catálogo de informes ingeridos ─────────────────────────────────────────
create table if not exists informes (
    id                text primary key,          -- slug: 'coursera-job-skills-2024'
    titulo            text not null,
    editor            text not null,             -- quién lo publica (Coursera, WEF…)
    anio_referencia   int  not null,             -- año al que se refieren los datos
    publicado_en      date,
    url               text,

    -- Metadatos que hacen el dato INTERPRETABLE. `universo` es obligatorio: sin
    -- saber a quién midió el informe, su ranking no es comparable con nada.
    cobertura         text not null default 'global',
    universo          text not null,             -- 'matriculados en la plataforma'
    metodologia       text,
    tamano_muestra    int,
    sesgos_conocidos  text,
    licencia          text,

    -- Trazabilidad del archivo.
    hash_pdf          text,                      -- sha256: evita ingerir dos veces
    paginas           int,
    idioma            text default 'en',

    -- Flujo de revisión: nada entra al selector hasta que un humano lo valida.
    estado            text not null default 'borrador',   -- borrador | validado | retirado
    ingestado_en      timestamptz default now(),
    validado_por      text,
    validado_en       timestamptz
);

create index if not exists idx_informes_estado
    on informes (estado, anio_referencia desc);

create unique index if not exists idx_informes_hash
    on informes (hash_pdf) where hash_pdf is not null;


-- ── Observaciones extraídas de cada informe ────────────────────────────────
create table if not exists informes_observaciones (
    id                bigserial primary key,
    informe_id        text not null references informes(id) on delete cascade,
    dimension         text not null default 'skill',   -- skill | cargo | sector

    termino_original  text not null,   -- LITERAL del PDF, sin traducir ('Generative AI')
    termino           text,            -- canónico en español, o NULL si no mapea
    categoria         text,            -- técnica | blanda | conocimiento | destreza

    -- La métrica NO se convierte nunca: un ranking es un ranking y un porcentaje
    -- es un porcentaje. Mezclarlas produciría cifras inventadas.
    metrica           text not null,   -- posicion_ranking | pct_universo_propio |
                                       -- pct_crecimiento | conteo | indice_propietario
    valor             double precision,
    posicion          int,

    -- AUDITORÍA ANTI-ALUCINACIÓN: cada fila debe poder rastrearse al PDF.
    pagina            int,
    cita              text,            -- fragmento literal copiado del informe
    verificada        boolean not null default false,  -- la cita se halló en esa página
    confianza         double precision,

    constraint uq_inf_obs unique (informe_id, dimension, termino_original, metrica)
);

create index if not exists idx_inf_obs_informe
    on informes_observaciones (informe_id, dimension, posicion);

create index if not exists idx_inf_obs_termino
    on informes_observaciones (termino) where termino is not null;
