'use client';

/**
 * Página "Informes" (ruta '/informes').
 *
 * Permite subir un informe PDF de un tercero (ej. "Coursera Job Skills Report
 * 2024") y convertirlo en una FUENTE de skills del Observatorio.
 *
 * Flujo, en tres pasos deliberados:
 *   1. SUBIR    -> POST /informes/extraer lee el PDF (OCR) y propone los datos.
 *                  No guarda nada todavía.
 *   2. REVISAR  -> el usuario confirma o corrige los metadatos que se detectaron
 *                  del propio PDF (título, editor y año) y ve cada skill con su
 *                  página y su cita, para poder rastrearla hasta el documento.
 *   3. VALIDAR  -> solo entonces el informe aparece como fuente seleccionable.
 *
 * Ese paso humano es intencional: un informe mal leído contaminaría el dashboard.
 */

import { PageLayout } from '@/lib/sidebar';
import { useEffect, useRef, useState } from 'react';
import { Upload, FileText, Check, Trash2, AlertTriangle, BarChart3 } from 'lucide-react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--sabana-dark-navy)',
  color: 'var(--white-background)',
  borderColor: 'var(--sabana-dark-navy)',
  borderRadius: '8px',
};
const COLORES_CAT = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

interface DetalleItem {
  termino: string;
  categoria: string;
  valor: number | null;
  posicion: number | null;
  pagina: number | null;
}
interface Detalle {
  informe: {
    id: string; titulo: string; editor: string; anio_referencia: number;
    cobertura: string | null; paginas: number | null; idioma: string | null;
    estado: string; total_skills: number;
  } | null;
  items: DetalleItem[];
  por_categoria: { categoria: string; n: number }[];
}
interface Comparativa {
  informes: { id: string; label: string }[];
  terminos: { termino: string; posiciones: Record<string, number | null> }[];
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Item {
  termino_original: string;
  metrica: string;
  valor: number | null;
  posicion: number | null;
  pagina: number | null;
  cita: string | null;
  verificada: boolean;
}

interface Borrador {
  hash_pdf: string;
  paginas: number;
  metodo_extraccion: string;
  idioma_detectado: string;
  metadatos_sugeridos: {
    titulo: string | null;
    editor: string | null;
    anio_referencia: number | null;
    cobertura: string | null;
  };
  extraidos: number;
  items: Item[];
}

interface InformeGuardado {
  id: string;
  titulo: string;
  editor: string;
  anio_referencia: number;
  estado: string;
  n_observaciones: number;
}

export default function InformesPage() {
  const [informes, setInformes] = useState<InformeGuardado[]>([]);
  const [borrador, setBorrador] = useState<Borrador | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  // Informe cuyas gráficas propias se están viendo, y la comparativa entre todos.
  const [abierto, setAbierto] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [comparativa, setComparativa] = useState<Comparativa | null>(null);

  // Metadatos editables del formulario de revisión.
  const [titulo, setTitulo] = useState('');
  const [editor, setEditor] = useState('');
  const [anio, setAnio] = useState('');
  const [cobertura, setCobertura] = useState('global');

  const cargarInformes = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/informes`);
      if (!r.ok) return;
      const d = await r.json();
      setInformes(d.informes ?? []);
    } catch {
      /* el backend puede estar caído; la página sigue usable para subir */
    }
  };

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    cargarInformes();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

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
      setTitulo(m.titulo ?? '');
      setEditor(m.editor ?? '');
      setAnio(m.anio_referencia ? String(m.anio_referencia) : '');
      setCobertura(m.cobertura ?? 'global');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo procesar el PDF');
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
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      setAviso(`Guardado como borrador (${d.observaciones} skills). Valídalo para usarlo como fuente.`);
      setBorrador(null);
      await cargarInformes();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
    } finally {
      setCargando(false);
    }
  };

  // Gráficas propias de un informe. Se piden al abrirlo (no al listar) para no
  // traer datos de todos los informes de golpe.
  const abrirGraficas = async (id: string) => {
    if (abierto === id) {
      setAbierto(null);
      return;
    }
    setAbierto(id);
    setDetalle(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/${encodeURIComponent(id)}/detalle`);
      setDetalle(r.ok ? await r.json() : null);
    } catch {
      setDetalle(null);
    }
  };

  // Comparativa entre informes: solo tiene sentido con dos o más validados.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (informes.filter((i) => i.estado === 'validado').length < 2) {
      setComparativa(null);
      return;
    }
    fetch(`${BACKEND_URL}/informes/comparativa`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setComparativa)
      .catch(() => setComparativa(null));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [informes]);

  const accion = async (id: string, ruta: string, metodo = 'POST') => {
    setError(null);
    try {
      const r = await fetch(`${BACKEND_URL}/informes/${encodeURIComponent(id)}${ruta}`, { method: metodo });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      await cargarInformes();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La acción falló');
    }
  };

  const etiqueta = 'block text-xs font-bold uppercase tracking-wide mb-1';
  const campo = 'w-full rounded-lg border px-3 py-2 text-sm';
  const estiloCampo = { borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)' };

  return (
    <PageLayout title="Informes">
      <div className="space-y-6">
        <div>
          <p className="text-lg" style={{ color: 'var(--sabana-dark-navy)' }}>
            Sube informes de terceros (por ejemplo, un <i>Job Skills Report</i>) para usarlos como
            fuente de skills junto a las vacantes y O*NET.
          </p>
          <p className="text-sm mt-1" style={{ color: 'var(--sabana-black-50)' }}>
            Las cifras de un informe son <b>declaradas por su editor</b>, no medidas por el
            Observatorio: se muestran como contraste, nunca promediadas con las vacantes.
          </p>
        </div>

        {error && <div className="rounded-lg p-3 bg-red-50 text-red-700 text-sm">{error}</div>}
        {aviso && (
          <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--sabana-sky-blue)', color: 'var(--sabana-dark-navy)' }}>
            {aviso}
          </div>
        )}

        {/* ---------- Paso 1: subir ---------- */}
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
          <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--sabana-dark-navy)' }}>
            1. Subir informe
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
          </p>
        </div>

        {/* ---------- Paso 2: revisar ---------- */}
        {borrador && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              2. Revisar antes de guardar
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
              {borrador.extraidos} skills · {borrador.paginas} páginas · leído con{' '}
              <b>{borrador.metodo_extraccion === 'document_ai' ? 'Google Document AI' : 'pypdf'}</b>.
              Corrige los datos del informe si hace falta.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className={etiqueta} style={{ color: 'var(--sabana-navy)' }}>Título *</label>
                <input className={campo} style={estiloCampo} value={titulo} onChange={(e) => setTitulo(e.target.value)} />
              </div>
              <div>
                <label className={etiqueta} style={{ color: 'var(--sabana-navy)' }}>Editor *</label>
                <input className={campo} style={estiloCampo} value={editor} onChange={(e) => setEditor(e.target.value)}
                  placeholder="Coursera, WEF, McKinsey…" />
              </div>
              <div>
                <label className={etiqueta} style={{ color: 'var(--sabana-navy)' }}>Año de referencia *</label>
                <input className={campo} style={estiloCampo} value={anio} onChange={(e) => setAnio(e.target.value)} inputMode="numeric" />
              </div>
              <div>
                <label className={etiqueta} style={{ color: 'var(--sabana-navy)' }}>Cobertura</label>
                <input className={campo} style={estiloCampo} value={cobertura} onChange={(e) => setCobertura(e.target.value)}
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
                Guardar como borrador
              </button>
              <button onClick={() => setBorrador(null)}
                className="px-5 py-2 rounded-lg font-semibold border"
                style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
                Descartar
              </button>
            </div>
          </div>
        )}

        {/* ---------- Paso 3: catálogo y validación ---------- */}
        <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
          <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
            3. Informes ingeridos
          </h3>
          <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
            Un informe solo aparece como fuente seleccionable cuando está <b>validado</b>.
          </p>

          {informes.length === 0 ? (
            <p className="text-sm text-center py-6" style={{ color: 'var(--sabana-black-50)' }}>
              Todavía no hay informes. Sube un PDF para empezar.
            </p>
          ) : (
            <div className="space-y-2">
              {informes.map((inf) => (
                <div key={inf.id}>
                <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3"
                  style={{ borderColor: 'var(--sabana-sky-blue)' }}>
                  <FileText size={18} style={{ color: 'var(--sabana-navy)' }} />
                  <div className="flex-1 min-w-[14rem]">
                    <p className="text-sm font-semibold" style={{ color: 'var(--sabana-dark-navy)' }}>
                      {inf.editor} — {inf.titulo} ({inf.anio_referencia})
                    </p>
                    <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>
                      {inf.n_observaciones} skills · {inf.anio_referencia}
                    </p>
                  </div>
                  <span className="text-xs font-semibold px-2 py-1 rounded"
                    style={{
                      backgroundColor: inf.estado === 'validado' ? 'var(--trend-up)' : 'var(--sabana-cream)',
                      color: inf.estado === 'validado' ? 'white' : 'var(--sabana-dark-navy)',
                    }}>
                    {inf.estado}
                  </span>

                  {inf.estado === 'borrador' && (
                    <>
                      <button onClick={() => accion(inf.id, '/validar')}
                        className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded text-white"
                        style={{ backgroundColor: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
                        <Check size={13} /> Validar
                      </button>
                      <button onClick={() => accion(inf.id, '', 'DELETE')}
                        className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
                        style={{ borderColor: 'var(--trend-down)', color: 'var(--trend-down)', cursor: 'pointer' }}>
                        <Trash2 size={13} /> Eliminar
                      </button>
                    </>
                  )}
                  {inf.estado === 'validado' && (
                    <button onClick={() => accion(inf.id, '/retirar')}
                      className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
                      style={{ borderColor: 'var(--sabana-light-blue)', color: 'var(--sabana-dark-navy)', cursor: 'pointer' }}>
                      <AlertTriangle size={13} /> Retirar
                    </button>
                  )}

                  <button onClick={() => abrirGraficas(inf.id)}
                    className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded border"
                    style={{ borderColor: 'var(--sabana-navy)', color: 'var(--sabana-navy)', cursor: 'pointer' }}>
                    <BarChart3 size={13} /> {abierto === inf.id ? 'Ocultar' : 'Ver gráficas'}
                  </button>
                </div>

                {/* Gráficas propias del informe: qué dice ESE documento, sin cruzarlo
                    con las vacantes (para eso está el contraste en Skills). */}
                {abierto === inf.id && (
                  <div className="mt-2 rounded-lg border p-4" style={{ borderColor: 'var(--sabana-light-blue)' }}>
                    {!detalle ? (
                      <p className="text-sm text-center py-4" style={{ color: 'var(--sabana-black-50)' }}>Cargando…</p>
                    ) : (
                      <>
                        <p className="text-xs mb-4" style={{ color: 'var(--sabana-black-50)' }}>
                          {detalle.informe?.total_skills} skills · {detalle.informe?.paginas} páginas ·
                          cobertura {detalle.informe?.cobertura} · idioma {detalle.informe?.idioma}
                        </p>

                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                          {/* Top skills del informe */}
                          <div className="lg:col-span-2">
                            <h4 className="text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                              Skills más citadas en el informe
                            </h4>
                            <ResponsiveContainer width="100%" height={Math.max(240, detalle.items.length * 24)}>
                              <BarChart data={detalle.items} layout="vertical" margin={{ left: 8, right: 30 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--sabana-dark-navy)' }} />
                                <YAxis dataKey="termino" type="category" width={165} interval={0}
                                  tick={{ fontSize: 10, fill: 'var(--sabana-dark-navy)' }} />
                                <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }}
                                  labelStyle={{ color: 'var(--sabana-light-blue)' }}
                                  formatter={(v, _n, it) => [`${v} menciones · pág. ${it?.payload?.pagina ?? '—'}`, 'En el informe']} />
                                <Bar dataKey="valor" fill="var(--sabana-navy)" radius={[0, 4, 4, 0]} barSize={12} />
                              </BarChart>
                            </ResponsiveContainer>
                            <p className="text-xs mt-1" style={{ color: 'var(--sabana-black-50)' }}>
                              El nº de menciones ordena dentro de ESTE informe; no es comparable con otro
                              documento, porque depende de su extensión.
                            </p>
                          </div>

                          {/* Reparto por categoría */}
                          <div>
                            <h4 className="text-sm font-bold mb-2" style={{ color: 'var(--sabana-dark-navy)' }}>
                              Por categoría
                            </h4>
                            {detalle.por_categoria.length === 0 ? (
                              <p className="text-xs" style={{ color: 'var(--sabana-black-50)' }}>Sin categorías.</p>
                            ) : (
                              <ResponsiveContainer width="100%" height={240}>
                                <PieChart>
                                  <Pie data={detalle.por_categoria} dataKey="n" nameKey="categoria"
                                    innerRadius={45} outerRadius={80} paddingAngle={2}>
                                    {detalle.por_categoria.map((c, i) => (
                                      <Cell key={c.categoria} fill={COLORES_CAT[i % COLORES_CAT.length]} />
                                    ))}
                                  </Pie>
                                  <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: 'var(--white-background)' }} />
                                  <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
                                </PieChart>
                              </ResponsiveContainer>
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ---------- Comparativa entre informes (desde 2 validados) ---------- */}
        {comparativa && comparativa.terminos.length > 0 && (
          <div className="bg-white dark:bg-zinc-800 rounded-lg p-6 shadow">
            <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--sabana-dark-navy)' }}>
              Comparativa entre informes
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--sabana-black-50)' }}>
              Qué posición ocupa cada skill en cada informe. Se comparan <b>posiciones</b>, no
              menciones: el conteo depende de la extensión de cada documento.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundColor: 'var(--sabana-dark-navy)', color: 'white' }}>
                    <th className="text-left px-3 py-2 font-semibold">Skill</th>
                    {comparativa.informes.map((i) => (
                      <th key={i.id} className="text-right px-3 py-2 font-semibold">{i.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparativa.terminos.map((t, idx) => (
                    <tr key={t.termino} style={{ backgroundColor: idx % 2 ? 'var(--sabana-sky-blue)' : 'transparent' }}>
                      <td className="px-3 py-2" style={{ color: 'var(--sabana-dark-navy)' }}>{t.termino}</td>
                      {comparativa.informes.map((i) => (
                        <td key={i.id} className="px-3 py-2 text-right" style={{ color: 'var(--sabana-dark-navy)' }}>
                          {t.posiciones[i.id] != null ? `#${t.posiciones[i.id]}` : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
