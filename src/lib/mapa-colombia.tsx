'use client';

/**
 * <MapaColombia /> — mapa de los 32 departamentos + Bogotá D.C., coloreado por
 * volumen de vacantes y con cada departamento seleccionable.
 *
 * Se dibuja con SVG plano a partir del GeoJSON de `public/geo/`, sin librería de
 * mapas: el proyecto ya carga Recharts y añadir react-simple-maps/d3-geo por un
 * único mapa estático no se justificaba.
 *
 * Decisiones que importan:
 *  - La llave de unión con el backend es el CÓDIGO DANE, no el nombre: el
 *    GeoJSON original trae los nombres sin tildes y en forma larga ("SANTAFE DE
 *    BOGOTA D.C"), así que cruzar por texto sería frágil.
 *  - El GeoJSON se pide por fetch desde /public en vez de importarlo: son 111 KB
 *    que así no entran al bundle de JS y los cachea el navegador.
 *  - La escala de color es por RANGO (quantiles), no lineal: Bogotá tiene ~8x
 *    las vacantes de Antioquia y ~300x las de un departamento pequeño, y en una
 *    escala lineal todo el país saldría del mismo tono claro menos Bogotá.
 */

import { useEffect, useMemo, useRef, useState } from 'react';

/** Un departamento tal como lo entrega el GeoJSON ya simplificado. */
interface Feature {
  type: 'Feature';
  properties: { codigo: string; nombre: string };
  geometry:
    | { type: 'Polygon'; coordinates: number[][][] }
    | { type: 'MultiPolygon'; coordinates: number[][][][] };
}

const ANCHO = 520;
const ALTO = 620;
const MARGEN = 8;

/** Tonos de menor a mayor volumen (azules institucionales). */
const ESCALA = ['#e8eef7', '#c5d5e9', '#93aac9', '#5b7fae', '#2f5a8f', '#002058'];
const SIN_DATOS = '#f1f1f1';

/** Convierte una geometría GeoJSON en la cadena `d` de un <path>. */
function aPath(
  geom: Feature['geometry'],
  proyectar: (lon: number, lat: number) => [number, number],
): string {
  const anillos: number[][][] =
    geom.type === 'Polygon' ? geom.coordinates : geom.coordinates.flat();
  return anillos
    .map((anillo) => {
      const pts = anillo.map(([lon, lat]) => {
        const [x, y] = proyectar(lon, lat);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      });
      return `M${pts.join('L')}Z`;
    })
    .join('');
}

export interface DatoDepartamento {
  codigo: string;
  nombre: string;
  vacantes: number;
}

export function MapaColombia({
  datos,
  seleccionado,
  onSelect,
}: {
  datos: DatoDepartamento[];
  seleccionado: string | null;
  onSelect: (codigo: string | null) => void;
}) {
  const [features, setFeatures] = useState<Feature[] | null>(null);
  const [error, setError] = useState(false);
  const [hover, setHover] = useState<{ codigo: string; x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    let vivo = true;
    fetch('/geo/colombia-departamentos.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => vivo && setFeatures(d.features))
      .catch(() => vivo && setError(true));
    return () => {
      vivo = false;
    };
  }, []);

  const porCodigo = useMemo(
    () => new Map(datos.map((d) => [d.codigo, d])),
    [datos],
  );

  /** Umbrales por quantiles sobre los departamentos QUE TIENEN datos. */
  const cortes = useMemo(() => {
    const vals = datos.map((d) => d.vacantes).filter((v) => v > 0).sort((a, b) => a - b);
    if (!vals.length) return [];
    return [0.16, 0.33, 0.5, 0.68, 0.85].map(
      (q) => vals[Math.min(vals.length - 1, Math.floor(q * vals.length))],
    );
  }, [datos]);

  const color = (codigo: string) => {
    const d = porCodigo.get(codigo);
    if (!d || !d.vacantes) return SIN_DATOS;
    let i = 0;
    while (i < cortes.length && d.vacantes > cortes[i]) i++;
    return ESCALA[Math.min(i, ESCALA.length - 1)];
  };

  const paths = useMemo(() => {
    if (!features) return null;
    // Caja envolvente de todo el país, para encajarlo en el viewBox.
    let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
    for (const f of features) {
      const anillos: number[][][] =
        f.geometry.type === 'Polygon' ? f.geometry.coordinates : f.geometry.coordinates.flat();
      for (const anillo of anillos) {
        for (const [lon, lat] of anillo) {
          if (lon < minLon) minLon = lon;
          if (lon > maxLon) maxLon = lon;
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
        }
      }
    }
    // Proyección lineal: a la latitud de Colombia (~4°N) la distorsión de no
    // usar Mercator es inapreciable, y mantiene el código trivial.
    const escala = Math.min(
      (ANCHO - MARGEN * 2) / (maxLon - minLon),
      (ALTO - MARGEN * 2) / (maxLat - minLat),
    );
    const despX = (ANCHO - (maxLon - minLon) * escala) / 2;
    const despY = (ALTO - (maxLat - minLat) * escala) / 2;
    const proyectar = (lon: number, lat: number): [number, number] => [
      despX + (lon - minLon) * escala,
      despY + (maxLat - lat) * escala, // el eje Y del SVG crece hacia abajo
    ];

    return features.map((f) => ({
      codigo: f.properties.codigo,
      nombre: f.properties.nombre,
      d: aPath(f.geometry, proyectar),
    }));
  }, [features]);

  if (error) {
    return (
      <div
        className="flex items-center justify-center rounded-lg text-sm p-8"
        style={{ backgroundColor: 'var(--sabana-sky-blue)', color: 'var(--sabana-navy)', minHeight: 300 }}
      >
        No se pudo cargar el mapa. La información por departamento sigue disponible en la lista.
      </div>
    );
  }

  if (!paths) {
    return (
      <div
        className="animate-pulse rounded-lg"
        style={{ backgroundColor: 'var(--sabana-sky-blue)', height: 420 }}
      />
    );
  }

  const datoHover = hover ? porCodigo.get(hover.codigo) : null;
  const nombreHover = hover ? paths.find((p) => p.codigo === hover.codigo)?.nombre : null;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        className="w-full h-auto"
        style={{ maxHeight: 520 }}
        role="img"
        aria-label="Mapa de Colombia por departamentos. Seleccione un departamento para ver su detalle."
      >
        {paths.map((p) => {
          const activo = seleccionado === p.codigo;
          const dato = porCodigo.get(p.codigo);
          const conDatos = Boolean(dato?.vacantes);
          return (
            <path
              key={p.codigo}
              d={p.d}
              fill={color(p.codigo)}
              stroke={activo ? 'var(--sabana-dark-navy)' : '#ffffff'}
              strokeWidth={activo ? 2.5 : 0.7}
              style={{ cursor: conDatos ? 'pointer' : 'default', transition: 'fill .15s' }}
              opacity={hover && hover.codigo !== p.codigo ? 0.82 : 1}
              onMouseMove={(e) => {
                const caja = svgRef.current?.getBoundingClientRect();
                if (!caja) return;
                setHover({ codigo: p.codigo, x: e.clientX - caja.left, y: e.clientY - caja.top });
              }}
              onMouseLeave={() => setHover(null)}
              onClick={() => conDatos && onSelect(activo ? null : p.codigo)}
            >
              <title>{`${p.nombre}: ${dato?.vacantes ?? 0} vacantes`}</title>
            </path>
          );
        })}
      </svg>

      {/* Etiqueta flotante al pasar el cursor. */}
      {hover && nombreHover && (
        <div
          className="pointer-events-none absolute z-10 rounded px-2 py-1 text-xs shadow-lg"
          style={{
            left: Math.min(hover.x + 12, ANCHO - 120),
            top: hover.y + 12,
            backgroundColor: 'var(--sabana-dark-navy)',
            color: '#fff',
          }}
        >
          <span className="font-semibold">{nombreHover}</span>
          <br />
          {datoHover?.vacantes
            ? `${datoHover.vacantes.toLocaleString('es-CO')} vacante${datoHover.vacantes === 1 ? '' : 's'}`
            : 'Sin vacantes recolectadas'}
        </div>
      )}

      {/* Leyenda de la escala. */}
      <div className="flex items-center gap-2 mt-3 justify-center flex-wrap">
        <span className="text-xs" style={{ color: 'var(--sabana-black-70)' }}>
          Menos vacantes
        </span>
        {ESCALA.map((c) => (
          <span key={c} className="inline-block rounded-sm" style={{ backgroundColor: c, width: 26, height: 12 }} />
        ))}
        <span className="text-xs" style={{ color: 'var(--sabana-black-70)' }}>
          Más
        </span>
        <span className="inline-flex items-center gap-1 ml-3">
          <span className="inline-block rounded-sm" style={{ backgroundColor: SIN_DATOS, width: 26, height: 12, border: '1px solid #ddd' }} />
          <span className="text-xs" style={{ color: 'var(--sabana-black-70)' }}>Sin vacantes</span>
        </span>
      </div>
    </div>
  );
}
