-- ============================================================================
-- Migración 011 — Registro de preguntas al asistente (chat)
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 010.
--
-- QUÉ RESUELVE
-- La Dirección de Alumni quiere saber QUÉ preguntan los usuarios al asistente,
-- desglosado por la sección desde la que preguntan (Perfil ocupacional,
-- Análisis salarial, Cursos, Competencias, Empresas), y cuánto cuesta cada
-- pregunta/sesión en tokens del modelo. Hoy las preguntas nacen en el
-- navegador (burbuja de chat de cada página y chat de /asistente), viajan a la
-- ruta /api/chat de Next.js y se pierden: nada queda registrado.
--
-- Esta tabla la llena `POST /asistente/preguntas` (lo llama /api/chat desde el
-- servidor de Next, una fila por pregunta) y la lee
-- `GET /asistente/preguntas/resumen` (solo Admin). Ver Asistente/preguntas_service.py.
--
-- PRIVACIDAD (Ley 1581 de 2012, habeas data) — LEER ANTES DE APLICAR
--   * NO se guarda IP, correo, nombre, cookie ni ningún identificador de la
--     persona. `sesion_id` es un texto aleatorio que genera el navegador al
--     abrir el chat (sessionStorage) y muere al cerrar la pestaña: solo sirve
--     para agrupar las preguntas de una misma conversación. No es rastreable
--     a nadie.
--   * `pregunta` es TEXTO LIBRE escrito por el usuario. Aunque el asistente
--     no lo pida, alguien puede escribir su nombre, su cédula o datos de un
--     tercero. Por eso: (1) se recorta a 500 caracteres, (2) la Universidad
--     debe decidir la RETENCIÓN de esta tabla (p. ej. borrar filas de más de
--     90 días con un job programado) y (3) el acceso al resumen es solo Admin.
--     Esta migración NO crea la política de retención: es una decisión
--     institucional, no técnica.
--
-- El backend degrada con gracia si esta tabla no existe: el registro se
-- descarta en silencio y el resumen responde `disponible=false` con el aviso
-- "pendiente de aplicar migración 011" (patrón `tablas_disponibles()` de
-- Informes/informes_service.py).
-- ============================================================================

create table if not exists preguntas_asistente (
    id                    bigserial primary key,

    -- Sección desde la que se preguntó. Derivada del título de la página en
    -- /api/chat: perfil_ocupacional | analisis_salarial | cursos | competencias
    -- | empresas | otras. Es lo que desglosa el dashboard.
    categoria             text not null default 'otras',
    pagina                text,                       -- título de la página, tal cual

    pregunta              text not null,              -- texto libre, recortado a 500 caracteres
    -- Forma agrupable de la pregunta (minúsculas, sin signos, espacios
    -- colapsados): "¿Qué empresas contratan?" y "que empresas contratan" son
    -- la misma pregunta para el ranking de "más realizadas".
    pregunta_normalizada  text,

    sesion_id             text,                       -- aleatorio del navegador; NO identifica personas
    modelo                text,                       -- 'gemini-3.6-flash', 'claude-sonnet-4-5'…
    tokens_entrada        integer,                    -- usageMetadata / usage del modelo, si lo devolvió
    tokens_salida         integer,
    -- Estimado con precios configurables por variable de entorno
    -- (GEMINI_USD_POR_1M_ENTRADA / _SALIDA, CLAUDE_USD_POR_1M_ENTRADA / _SALIDA).
    -- Es una ESTIMACIÓN, no la factura: los precios cambian y no incluye caché.
    costo_usd_estimado    double precision,

    creado_en             timestamptz not null default now()
);

-- El dashboard agrupa por categoría y ordena por fecha; el ranking agrupa por
-- la forma normalizada dentro de cada categoría.
create index if not exists idx_preguntas_asistente_categoria
    on preguntas_asistente (categoria, creado_en desc);

create index if not exists idx_preguntas_asistente_normalizada
    on preguntas_asistente (categoria, pregunta_normalizada);

create index if not exists idx_preguntas_asistente_sesion
    on preguntas_asistente (sesion_id);
