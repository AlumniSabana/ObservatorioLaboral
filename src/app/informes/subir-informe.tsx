'use client';

/**
 * <SubirInforme /> — pasos 1 (subir) y 2 (revisar) del flujo de Informes.
 *
 *   1. SUBIR   -> POST /informes/extraer lee el PDF y propone los datos. No
 *                 guarda nada todavía.
 *   2. REVISAR -> el usuario confirma o corrige título, editor y año, y ve cada
 *                 skill con su página y su cita, para poder rastrearla hasta el
 *                 documento. Al guardar (POST /informes) queda en 'borrador'.
 *
 * Es el MISMO componente para el Admin y para el Usuario (ambos endpoints están
 * abiertos a propósito: cualquiera puede subir un PDF). Lo que cambia con
 * `modo` es el texto: al Usuario se le dice que el informe queda pendiente de
 * validación por el Administrador; al Admin, que lo valide él.
 *
 * REACTIVACIÓN: si el backend devuelve `reactiva`, el PDF corresponde a un
 * informe RETIRADO. Se muestra un aviso y al guardar ese registro se reactiva
 * (mismo id, datos nuevos, vuelve a borrador). Antes ese caso se rechazaba con
 * "ya fue ingerido" y no había forma de volver a subirlo.
 */

import { useRef, useState } from 'react';
import { Upload, RefreshCw } from 'lucide-react';
import type { Borrador, ResultadoGuardado } from './comun';
import {
  BACKEND_URL,
  CLASE_CAMPO,
  CLASE_ETIQUETA,
  ESTILO_CAMPO,
  etiquetaInforme,
} from './comun';

export function SubirInforme({
  modo,
  numerar = true,
  onGuardado,
  onDuplicado,
}: {
  modo: 'admin' | 'usuario';
  /** "1. Subir informe" / "2. Revisar…" (Admin) o sin numeración (Usuario). */
  numerar?: boolean;
  /** Se llama tras guardar con éxito (el padre recarga su lista / recuerda el id). */
  onGuardado: (r: ResultadoGuardado) => void | Promise<void>;
  /** El backend rechazó el PDF por estar ya ingerido: el padre puede refrescar su catálogo. */
  onDuplicado?: () => void | Promise<void>;
}) {
  const [borrador, setBorrador] = useState<Borrador | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Metadatos editables del formulario de revisión.
  const [titulo, setTitulo] = useState('');
  const [editor, setEditor] = useState('');
  const [anio, setAnio] = useState('');
  const [cobertura, setCobertura] = useState('global');

  const subir = async (archivo: File) => {
    setCargando(true);
    setError(null);
    setAviso(null);
    setBorrador(null);
    try {
      const fd = new FormData();
      fd.append('file', archivo);
      const r = await fetch(`${BACKEND_URL}/informes/extraer`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);

      setBorrador(d);
      const m = d.metadatos_sugeridos ?? {};
      // Si reactiva un retirado, se parte de los datos que ya tenía ese informe:
      // el Admin normalmente solo quiere re-extraer, no reescribir la ficha.
      setTitulo(d.reactiva?.titulo ?? m.titulo ?? '');
      setEditor(d.reactiva?.editor ?? m.editor ?? '');
      setAnio(String(d.reactiva?.anio_referencia ?? m.anio_referencia ?? ''));
      setCobertura(m.cobertura ?? 'global');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'No se pudo procesar el PDF';
      setError(msg);
      // "Ya fue ingerido" significa que el catálogo SÍ tiene ese informe aunque
      // la lista del padre se viera vacía (p. ej. porque su carga inicial falló).
      if (msg.includes('ya fue ingerido')) await onDuplicado?.();
    } finally {
      setCargando(false);
    }
  };

  const guardar = async () => {
    if (!borrador) return;
    if (!titulo.trim() || !editor.trim() || !anio.trim()) {
      setError('Título, editor y año son obligatorios.');
      return;
    }
    setCargando(true);
    setError(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          catalogo: {
            titulo: titulo.trim(),
            editor: editor.trim(),
            anio_referencia: Number(anio),
            cobertura: cobertura.trim() || 'global',
            hash_pdf: borrador.hash_pdf,
            paginas: borrador.paginas,
            idioma: borrador.idioma_detectado,
          },
          items: borrador.items,
        }),
      });
      const d: ResultadoGuardado & { error?: string } = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);

      const base = d.reactivado
        ? `Informe reactivado con ${d.observaciones} skills (vuelve a borrador).`
        : `Guardado como borrador (${d.observaciones} skills).`;
      setAviso(
        modo === 'admin'
          ? `${base} Valídalo para usarlo como fuente.`
          : `${base} Queda pendiente de validación por el Administrador; lo verás abajo en "Mis informes".`,
      );
      setBorrador(null);
      await onGuardado(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
    } finally {
      setCargando(false);
    }
  };

  const n = (i: number) => (numerar ? `${i}. ` : '');

  return (
    <>
      {error && <div className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">{error}</div>}
      {aviso && (
        <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}>
          {aviso}
        </div>
      )}

      {/* ---------- Paso 1: subir ---------- */}
      <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
        <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--sabana-dark-navy)' }}>
          {n(1)}Subir informe
        </h3>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) subir(f);
            e.target.value = '';
          }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={cargando}
          className="flex items-center gap-2 px-5 py-3 rounded-lg font-semibold text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: cargando ? 'wait' : 'pointer' }}
        >
          <Upload size={18} />
          {cargando ? 'Procesando…' : 'Seleccionar PDF'}
        </button>
        <p className="text-xs mt-2" style={{ color: 'var(--sabana-black-50)' }}>
          El PDF debe tener texto seleccionable. Para informes escaneados hay que configurar
          Google Document AI en el backend.
          {modo === 'usuario' && (
            <> Solo se guardan las skills detectadas y los metadatos del informe, no el archivo.</>
          )}
        </p>
      </div>

      {/* ---------- Paso 2: revisar ---------- */}
      {borrador && (
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
          <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
            {n(2)}Revisar antes de guardar
          </h3>
          <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
            {borrador.extraidos} skills · {borrador.paginas} páginas · leído con{' '}
            <b>{borrador.metodo_extraccion === 'document_ai' ? 'Google Document AI' : 'pypdf'}</b>.
            Corrige los datos del informe si hace falta.
          </p>

          {borrador.reactiva && (
            <div className="flex items-start gap-2 rounded-lg p-3 mb-4 text-sm"
              style={{ background: 'var(--sabana-cream)', color: 'var(--sabana-dark-navy)' }}>
              <RefreshCw size={16} className="mt-0.5 shrink-0" />
              <p>
                Este PDF corresponde al informe <b>retirado</b> «{etiquetaInforme(borrador.reactiva)}».
                Al guardarlo se <b>reactivará</b> ese mismo registro con las skills recién extraídas y
                volverá a borrador para pasar de nuevo por validación.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className={CLASE_ETIQUETA} style={{ color: 'var(--sabana-navy)' }}>Título *</label>
              <input className={CLASE_CAMPO} style={ESTILO_CAMPO} value={titulo} onChange={(e) => setTitulo(e.target.value)} />
            </div>
            <div>
              <label className={CLASE_ETIQUETA} style={{ color: 'var(--sabana-navy)' }}>Editor *</label>
              <input className={CLASE_CAMPO} style={ESTILO_CAMPO} value={editor} onChange={(e) => setEditor(e.target.value)}
                placeholder="Coursera, WEF, McKinsey…" />
            </div>
            <div>
              <label className={CLASE_ETIQUETA} style={{ color: 'var(--sabana-navy)' }}>Año de referencia *</label>
              <input className={CLASE_CAMPO} style={ESTILO_CAMPO} value={anio} onChange={(e) => setAnio(e.target.value)} inputMode="numeric" />
            </div>
            <div>
              <label className={CLASE_ETIQUETA} style={{ color: 'var(--sabana-navy)' }}>Cobertura</label>
              <input className={CLASE_CAMPO} style={ESTILO_CAMPO} value={cobertura} onChange={(e) => setCobertura(e.target.value)}
                placeholder="global, Colombia…" />
            </div>
          </div>

          {/* Cada skill, con su página y su cita: así cualquier cifra es rastreable al PDF. */}
          <div className="overflow-x-auto max-h-80 overflow-y-auto border rounded-lg" style={{ borderColor: 'var(--sabana-sky-blue)' }}>
            <table className="w-full text-sm">
              <thead className="sticky top-0">
                <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                  <th className="text-left px-3 py-2">#</th>
                  <th className="text-left px-3 py-2">Skill</th>
                  <th className="text-right px-3 py-2">Menciones</th>
                  <th className="text-right px-3 py-2">Pág.</th>
                  <th className="text-left px-3 py-2">Cita del informe</th>
                </tr>
              </thead>
              <tbody>
                {borrador.items.map((it, i) => (
                  <tr key={it.termino_original} style={{ backgroundColor: i % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                    <td className="px-3 py-2" style={{ color: 'var(--sabana-dark-navy)' }}>{it.posicion}</td>
                    <td className="px-3 py-2 font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>{it.termino_original}</td>
                    <td className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>{it.valor ?? '—'}</td>
                    <td className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>{it.pagina ?? '—'}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: 'var(--sabana-black-50)' }}>…{(it.cita || '').slice(0, 70)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-3 mt-4">
            <button onClick={guardar} disabled={cargando}
              className="px-5 py-2 rounded-lg font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
              {borrador.reactiva ? 'Reactivar informe' : 'Guardar como borrador'}
            </button>
            <button onClick={() => setBorrador(null)}
              className="px-5 py-2 rounded-lg font-semibold border"
              style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
              Descartar
            </button>
          </div>
        </div>
      )}
    </>
  );
}
