-- ============================================================================
-- Migración 009 — CNO 2025 del SENA: habilidades y conocimientos en español
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 008.
--
-- QUÉ RESUELVE (es el hueco más viejo del proyecto)
-- Hasta ahora las skills salían de O*NET: taxonomía normativa de ESTADOS UNIDOS,
-- en inglés, que había que traducir a mano (ver `traducciones.py`). El SENA
-- publica el CNO 2025 con habilidades y conocimientos POR OCUPACIÓN, oficiales,
-- colombianos y en español:
--
--     Habilidades     3.122 pares ocupación↔habilidad
--     Conocimientos   3.022 pares
--     Denominaciones  9.618 sinónimos de cargos (diccionario para normalizar
--                     títulos de vacante, hoy resuelto a mano en traducciones.py)
--     Funciones       4.967
--
-- Y viene llaveado por CÓDIGO CNO, el mismo que ya usa `PROGRAMA_CNO` en
-- Salarios/salarios_service.py. Cruce directo, sin mapeos nuevos.
--
-- JERARQUÍA: el CNO es jerárquico y el archivo trae los tres niveles mezclados
-- (2 dígitos = gran grupo, 3 = subgrupo, 4 = ocupación). Se guarda `nivel` para
-- poder consultar por prefijo: un programa mapeado al gran grupo '25' puede
-- recoger también todo lo que cuelga de él (251, 2511, …).
-- ============================================================================

create table if not exists sena_cno_ocupaciones (
    codigo       text primary key,        -- '25', '251', '2511'
    nivel        int  not null,           -- nº de dígitos: 2, 3 o 4
    nombre       text not null,
    descripcion  text,
    version      text default 'CNO 2025'
);

create index if not exists idx_sena_cno_nivel on sena_cno_ocupaciones (nivel);


-- Atributos de cada ocupación. Una sola tabla para los cuatro tipos: comparten
-- forma (código + nombre + descripción) y así consultarlos es uniforme.
create table if not exists sena_cno_atributos (
    id                bigserial primary key,
    codigo_ocupacion  text not null,
    nivel             int  not null,

    -- 'habilidad' | 'conocimiento' | 'denominacion' | 'funcion'
    tipo              text not null,
    codigo            text,
    nombre            text not null,
    descripcion       text,
    version           text default 'CNO 2025',

    constraint uq_sena_atr unique (codigo_ocupacion, tipo, nombre)
);

create index if not exists idx_sena_atr_ocup on sena_cno_atributos (codigo_ocupacion, tipo);
create index if not exists idx_sena_atr_tipo on sena_cno_atributos (tipo);
-- Búsqueda por prefijo de código (para subir/bajar en la jerarquía del CNO).
create index if not exists idx_sena_atr_pref on sena_cno_atributos (tipo, codigo_ocupacion text_pattern_ops);
