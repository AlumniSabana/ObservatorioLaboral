'use client';

/**
 * Página "Sobre el observatorio" (ruta '/sobre').
 *
 * Es la única página sin datos ni filtros: explica QUÉ es la plataforma, PARA
 * QUÉ sirve y DE DÓNDE salen los números que ve el usuario en el resto de
 * secciones. Vive al final del menú lateral a propósito — es la puerta de
 * entrada para quien llega por primera vez, pero no compite por atención con
 * las páginas de análisis.
 *
 * Contenido estático (sin llamadas al backend): es una página de referencia,
 * no un dashboard.
 */

import { PageLayout } from '@/lib/sidebar';
import {
  Target,
  Database,
  GraduationCap,
  AlertTriangle,
  Code2,
} from 'lucide-react';

const PROGRAMAS = [
  'Administración de Empresas', 'Administración & Servicio',
  'Administración de Mercadeo y Logística Internacionales',
  'Administración de Negocios Internacionales',
  'Economía y Finanzas Internacionales', 'Economía y Finanzas Internacionales Virtual',
  'Gastronomía', 'Comportamiento Organizacional', 'Psicología',
  'Comunicación Audiovisual y Multimedios', 'Comunicación Corporativa',
  'Comunicación Social y Periodismo', 'Licenciatura en Educación Infantil',
  'Enfermería', 'Fisioterapia', 'Ciencias Políticas', 'Derecho',
  'Relaciones Internacionales', 'Filosofía', 'Medicina', 'Ciencia de Datos',
  'Ingeniería Civil', 'Ingeniería de Bioproducción',
  'Ingeniería de Diseño e Innovación', 'Ingeniería Industrial',
  'Ingeniería Informática', 'Ingeniería Mecánica', 'Ingeniería Química',
  'Ingeniería en Inteligencia Artificial',
];

function Tarjeta({
  icono: Icono,
  titulo,
  children,
}: {
  icono: React.ElementType;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-lg p-6 bg-white dark:bg-zinc-800 shadow border-l-4"
      style={{ borderColor: 'var(--sabana-light-blue)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icono className="w-5 h-5" style={{ color: 'var(--sabana-navy)' }} />
        <h2 className="text-lg font-bold" style={{ color: 'var(--sabana-dark-navy)' }}>
          {titulo}
        </h2>
      </div>
      <div className="text-sm leading-relaxed space-y-3" style={{ color: 'var(--sabana-black-70)' }}>
        {children}
      </div>
    </div>
  );
}

function Fuente({ nombre, tipo, detalle }: { nombre: string; tipo: string; detalle: string }) {
  return (
    <li className="flex flex-col gap-0.5 py-2 border-b last:border-b-0" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>{nombre}</span>
        <span
          className="text-[0.65rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full"
          style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-navy)' }}
        >
          {tipo}
        </span>
      </div>
      <span className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>{detalle}</span>
    </li>
  );
}

export default function SobrePage() {
  return (
    <PageLayout title="Sobre el Observatorio">
      <div className="max-w-4xl space-y-6">
        <p className="text-base leading-relaxed" style={{ color: 'var(--sabana-black-90)' }}>
          El <strong>Observatorio Laboral</strong> es una plataforma de análisis del mercado
          de trabajo construida para la <strong>Dirección de Egresados (Alumni) de la
          Universidad de La Sabana</strong>. Reúne vacantes reales, referencias ocupacionales
          y estudios oficiales, y los organiza por <strong>programa académico</strong> para
          responder una pregunta concreta: qué está pidiendo hoy el mercado a quien se gradúa
          de cada carrera.
        </p>

        <Tarjeta icono={Target} titulo="¿Para qué sirve?">
          <p>
            No reemplaza el criterio de un consejero de carrera ni de un coordinador
            académico: les da evidencia. Cada sección del menú responde una pregunta distinta
            sobre el mismo problema:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Tendencias</strong> — qué cargos crecen, se mantienen o decrecen en la demanda, y ahora también dónde en Colombia.</li>
            <li><strong>Competencias</strong> — qué skills piden las vacantes de cada programa.</li>
            <li><strong>Análisis salarial</strong> — rangos salariales oficiales (GEIH) y de las vacantes recolectadas.</li>
            <li><strong>Perfil ocupacional</strong> — un perfil compuesto por programa: seniority típico, intereses vocacionales (RIASEC), sectores que contratan.</li>
            <li><strong>Empresas</strong> e <strong>Informes</strong> — contexto cualitativo y de terceros que complementa las cifras.</li>
          </ul>
        </Tarjeta>

        <Tarjeta icono={Database} titulo="¿De dónde salen los datos?">
          <p>
            El Observatorio distingue a propósito TRES naturalezas de dato, porque no
            responden lo mismo y mezclarlas sin decirlo sería engañoso:
          </p>
          <ul className="space-y-1">
            <Fuente
              nombre="Vacantes observadas"
              tipo="Observado"
              detalle="Adzuna (EE.UU., Reino Unido, Canadá, México, España) · Google Jobs y LinkedIn (Colombia, y LinkedIn además en México, Argentina, Chile y Perú). Ofertas reales, recolectadas periódicamente — miden lo que el mercado publica, no lo que existe."
            />
            <Fuente
              nombre="Referencia ocupacional"
              tipo="Normativo"
              detalle="O*NET (EE.UU.) y la CUOC/SENA (Colombia). Describen lo que una ocupación típicamente requiere, no cuánto se demanda hoy."
            />
            <Fuente
              nombre="Estudios oficiales e informes"
              tipo="Declarado"
              detalle="GEIH y OLE del DANE/MEN, y reportes de terceros que el usuario puede cargar en 'Informes'. Cifras publicadas por su editor, no medidas por el Observatorio."
            />
          </ul>
        </Tarjeta>

        <Tarjeta icono={GraduationCap} titulo="Programas cubiertos">
          <p>29 programas académicos de la Universidad, cada uno con sus propias palabras clave de búsqueda:</p>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {PROGRAMAS.map((p) => (
              <span
                key={p}
                className="text-xs px-2 py-1 rounded-full"
                style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-navy)' }}
              >
                {p}
              </span>
            ))}
          </div>
        </Tarjeta>

        <Tarjeta icono={AlertTriangle} titulo="Cómo leer las cifras">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Las vacantes son una <strong>muestra recolectada periódicamente</strong>, no el
              universo completo del mercado: un cargo con pocas vacantes en la muestra no
              significa necesariamente poca demanda real.
            </li>
            <li>
              Cada fuente tiene su propia <strong>profundidad histórica</strong>: Adzuna acumula
              varios años de backfill; Google Jobs y LinkedIn Colombia son más recientes, así que
              sus tendencias mensuales necesitan más tiempo de recolección para madurar.
            </li>
            <li>
              Un programa con pocas vacantes asociadas no está &quot;mal&quot;: sus egresados
              suelen ocupar cargos con nombres muy variados, difíciles de capturar con
              palabras clave, o el mercado que las fuentes cubren no es donde se concentra ese
              programa.
            </li>
          </ul>
        </Tarjeta>

        <Tarjeta icono={Code2} titulo="Cómo está construido">
          <p>
            Frontend en Next.js y backend en FastAPI (Python), con Supabase como base de
            datos. La recolección de vacantes corre de forma periódica y manual — no en
            tiempo real — respetando los términos de uso de cada fuente (en particular, la
            de LinkedIn se limita a ofertas públicas, con una huella de consulta mínima y
            aprobación institucional previa).
          </p>
        </Tarjeta>

        <p className="text-xs text-center pt-2" style={{ color: 'var(--sabana-black-50)' }}>
          Un proyecto de la Dirección de Egresados (Alumni) — Universidad de La Sabana.
        </p>
      </div>
    </PageLayout>
  );
}
