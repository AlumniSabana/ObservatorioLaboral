-- ============================================================================
-- Migración 012 — Insights generados (individuales y conjuntos) como registro
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 006 (informes). Es
-- independiente de 011 (Equipo 2): el orden entre ambas no importa.
--
-- QUÉ RESUELVE
-- Hasta ahora el "Informe de insights" (Gemini) se devolvía al navegador y se
-- perdía al recargar. Con la vista de Usuario (solo lectura) hace falta que los
-- insights que genera el Administrador QUEDEN GUARDADOS, para que el Usuario
-- que subió un PDF pueda leer después el análisis que se hizo sobre él, y para
-- que los "Insights Conjuntos" (síntesis de varios informes afines) se puedan
-- consultar sin volver a pagar la llamada al modelo.
--
-- POR QUÉ `informe_ids` ES UN ARRAY Y NO UNA FK
-- Un insight puede cubrir 1..N informes. Se guarda la lista de ids tal cual y,
-- además, un snapshot mínimo de los metadatos (`informes`, jsonb) para que el
-- insight siga siendo legible aunque el informe se retire o se reactive con
-- otro título: el insight describe lo que decían esos documentos EN ESE
-- MOMENTO, y no debe cambiar retroactivamente.
--
-- Sin FK tampoco hay borrado en cascada: eliminar un informe en borrador no se
-- lleva los insights (un borrador nunca tuvo insights, porque solo se generan
-- sobre validados).
--
-- DEGRADACIÓN: el backend detecta si esta tabla existe
-- (Informes/insights_repo.py::tabla_disponible). Si no, los endpoints siguen
-- generando el texto y responden `persistido: false`; la UI lo avisa.
-- ============================================================================

create table if not exists insights_generados (
    id            bigserial primary key,

    -- 'individual': el botón "Generar informe de insights" (1+ informes marcados).
    -- 'conjunto'  : síntesis de un grupo de informes afines (Insights Conjuntos).
    tipo          text not null check (tipo in ('individual', 'conjunto')),

    informe_ids   text[] not null,          -- ids de `informes` que alimentaron el insight
    informes      jsonb,                    -- snapshot [{id,titulo,editor,anio_referencia}]

    titulo        text not null,
    contenido     text not null,            -- Markdown tal como lo devolvió el modelo
    modelo        text,                     -- p. ej. 'gemini-3.6-flash'
    motivo_grupo  text,                     -- solo 'conjunto': por qué la IA los agrupó

    creado_en     timestamptz not null default now(),
    creado_por    text                      -- correo del Admin, si la sesión lo aporta
);

-- Listado por tipo, más reciente primero (vista de Usuario y panel de Admin).
create index if not exists idx_insights_tipo_fecha
    on insights_generados (tipo, creado_en desc);

-- "¿Qué insights mencionan ESTE informe?" -> `informe_ids @> '{id}'`.
create index if not exists idx_insights_informe_ids
    on insights_generados using gin (informe_ids);
