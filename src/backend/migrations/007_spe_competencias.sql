-- ============================================================================
-- Migración 007 — Anexos del SPE: ocupaciones y competencias en Colombia
--
-- Ejecutar en el SQL Editor de Supabase, DESPUÉS de 006.
--
-- QUÉ APORTA (y por qué importa tanto)
-- El Servicio Público de Empleo publica anexos con las vacantes registradas en
-- Colombia, clasificadas por ocupación (CIUO) y con las COMPETENCIAS que piden.
-- Es la pieza que le faltaba al Observatorio:
--
--   - Hoy las skills son DERIVADAS: O*NET (normativo, EE.UU.) cruzado con la
--     demanda por programa. Esto son competencias OBSERVADAS en vacantes reales
--     colombianas, y además en español.
--   - El CIUO de 2 dígitos del SPE es la MISMA taxonomía que el CNO que ya usa
--     `Salarios/salarios_service.PROGRAMA_CNO`, así que enchufa directo a los
--     programas sin inventar ningún mapeo nuevo.
--   - Cubre ~1,8 millones de ofertas, frente a las ~61k de nuestra muestra.
--
-- CADENCIA: descarga manual de los anexos del SPE (públicos, mensuales). Igual
-- que GEIH: conviene actualizar cada 3-6 meses, no cada mes.
--
-- PRIVACIDAD: solo cifras agregadas por ocupación y territorio. Sin datos personales.
-- ============================================================================

-- ── Ofertas por ocupación, mes y territorio ────────────────────────────────
create table if not exists spe_ocupaciones (
    id             bigserial primary key,
    periodo        date not null,          -- primer día del mes (comparable con el resto)
    anio           int  not null,
    mes            int  not null,
    departamento   text,
    municipio      text,
    divipola       text,                   -- código DANE del municipio
    ciuo2          text not null,          -- CIUO 2 dígitos == CNO 2 dígitos
    ocupacion      text,
    ofertas        int  not null default 0,
    fuente_anexo   text,                   -- de qué archivo/periodo salió
    constraint uq_spe_ocup unique (periodo, divipola, ciuo2)
);

create index if not exists idx_spe_ocup_ciuo    on spe_ocupaciones (ciuo2, periodo);
create index if not exists idx_spe_ocup_periodo on spe_ocupaciones (periodo);


-- ── Competencias pedidas, por ocupación y mes ──────────────────────────────
-- Los anexos vienen en formato ANCHO (una columna por competencia); aquí se
-- guardan en formato LARGO, que es lo que permite consultarlas y compararlas.
create table if not exists spe_competencias (
    id             bigserial primary key,
    periodo        date not null,
    anio           int  not null,
    mes            int  not null,
    departamento   text,
    ciuo2          text not null,
    ocupacion      text,

    -- De qué hoja del anexo viene: 'transversal', 'digital', 'ofimatica',
    -- 'programa', 'lenguaje', 'practica', 'habilidad_digital', 'digital_basico'.
    -- Permite separar competencias blandas de herramientas concretas.
    categoria      text not null,
    competencia    text not null,          -- 'Cooperación', 'Python', 'SAP'…
    menciones      int  not null default 0,
    fuente_anexo   text,
    constraint uq_spe_comp unique (periodo, departamento, ciuo2, categoria, competencia)
);

create index if not exists idx_spe_comp_ciuo on spe_competencias (ciuo2, categoria);
create index if not exists idx_spe_comp_comp on spe_competencias (competencia);
create index if not exists idx_spe_comp_per  on spe_competencias (periodo);
