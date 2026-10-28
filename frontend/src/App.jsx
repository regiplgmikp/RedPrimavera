import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getCeldas, getEspecies, getEspeciesDeCelda, getObservaciones, getPoblacion } from './api.js';
import { ZOOM_PARA_RES_9 } from './config.js';
import { bboxTexto } from './mapData.js';
import { datosSobreposicion, grafoCeldas, grafoEspecies, subgrafoDeEspecies } from './graphData.js';
import FilterPanel from './components/FilterPanel.jsx';
import MapPanel from './components/MapPanel.jsx';
import GraphPanel from './components/GraphPanel.jsx';
import Bienvenida from './components/Bienvenida.jsx';
import { iniciarRecorrido } from './recorrido.js';
import Logo from './components/Logo.jsx';

export const FILTROS_VACIOS = {
  ivc_min: '', ivc_max: '', frecuencia_min: '', distancia_camino_max: '', en_predio: '',
  zona: '', min_celdas_compartidas: 2,
};
const VISTA_INICIAL = {
  resolucion: 8, colorMapa: 'ivc', disposicion: 'lado', sobreponer: false, verPoblacion: false,
  dinamico: false, autoRes: false, grafo: 'especies', colorGrafo: 'taxonomia', tamanoGrafo: 'intermediacion_norm',
};
const esAbort = (e) => e?.name === 'AbortError';

const CLAVE_BIENVENIDA = 'redprimavera.bienvenida.vista';
const yaVioBienvenida = () => {
  try { return localStorage.getItem(CLAVE_BIENVENIDA) === '1'; } catch { return false; }
};
const ANCHO_MIN = 260;
const ANCHO_MAX = 560;
const ANCHO_INICIAL = 300;
const CLAVE_ANCHO = 'redprimavera.ancho.panel';
const anchoGuardado = () => {
  try {
    const n = Number(localStorage.getItem(CLAVE_ANCHO));
    return n >= ANCHO_MIN && n <= ANCHO_MAX ? n : ANCHO_INICIAL;
  } catch { return ANCHO_INICIAL; }
};

export default function App() {
  const [form, setForm] = useState(FILTROS_VACIOS);        // lo que se está editando
  const [aplicados, setAplicados] = useState(FILTROS_VACIOS); // lo que se envió a la API
  const [vista, setVista] = useState(VISTA_INICIAL);
  const [encuadre, setEncuadre] = useState(null);           // { bbox: [w,s,e,n], zoom } reportado por el mapa
  const [celdas, setCeldas] = useState({ datos: null, cargando: true, error: null });
  const [especies, setEspecies] = useState({ datos: null, cargando: true, error: null });
  const [poblacion, setPoblacion] = useState({ datos: null, error: null });
  const [seleccion, setSeleccion] = useState(null);         // { tipo: 'celda' | 'especie', id }
  const [celdaFoco, setCeldaFoco] = useState(null);         // celda cuyas especies se muestran en el grafo
  const [especiesCelda, setEspeciesCelda] = useState({ id: null, datos: null, cargando: false, error: null });
  const [observaciones, setObservaciones] = useState({ id: null, datos: null, cargando: false, error: null });
    const [bienvenida, setBienvenida] = useState(() => !yaVioBienvenida());
  const cerrarBienvenida = useCallback(() => {
    setBienvenida(false);
    try { localStorage.setItem(CLAVE_BIENVENIDA, '1'); } catch { /* sin almacenamiento: no pasa nada */ }
  }, []);
    const hacerRecorrido = useCallback(() => {
    cerrarBienvenida();
    setTimeout(iniciarRecorrido, 200); // espera a que la ventana de bienvenida desaparezca
  }, [cerrarBienvenida]);
  const [ancho, setAncho] = useState(anchoGuardado);
  const [arrastrando, setArrastrando] = useState(false);
  useEffect(() => {
    try { localStorage.setItem(CLAVE_ANCHO, String(ancho)); } catch { /* sin almacenamiento */ }
  }, [ancho]);

  const arrastrar = useCallback((e) => {
    e.preventDefault();
    setArrastrando(true);
    const mover = (ev) => setAncho(Math.min(ANCHO_MAX, Math.max(ANCHO_MIN, ev.clientX)));
    const soltar = () => {
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', soltar);
      document.body.style.userSelect = '';
      setArrastrando(false);
    };
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
  }, []);
  const teclado = (e) => {
    if (e.key === 'ArrowLeft') setAncho((a) => Math.max(ANCHO_MIN, a - 16));
    if (e.key === 'ArrowRight') setAncho((a) => Math.min(ANCHO_MAX, a + 16));
  };

  const resolucion = vista.autoRes && encuadre ? (encuadre.zoom >= ZOOM_PARA_RES_9 ? 9 : 8) : vista.resolucion;
  const bboxParam = vista.dinamico && encuadre ? bboxTexto(encuadre.bbox) : '';

  // Datos del grafo y del mapa: se piden juntos y se cancelan si cambian los filtros
  useEffect(() => {
    const ctl = new AbortController();
    setCeldas((p) => ({ ...p, cargando: true, error: null }));
    setEspecies((p) => ({ ...p, cargando: true, error: null }));
    const base = {
      resolucion, bbox: bboxParam,
      ivc_min: aplicados.ivc_min, ivc_max: aplicados.ivc_max, frecuencia_min: aplicados.frecuencia_min,
      distancia_camino_max: aplicados.distancia_camino_max, en_predio: aplicados.en_predio,
    };
    getCeldas(base, ctl.signal)
      .then((d) => setCeldas({ datos: d, cargando: false, error: null }))
      .catch((e) => { if (!esAbort(e)) setCeldas({ datos: null, cargando: false, error: e.message }); });
    getEspecies(base, { zona: aplicados.zona, min_celdas_compartidas: aplicados.min_celdas_compartidas }, ctl.signal)
      .then((d) => setEspecies({ datos: d, cargando: false, error: null }))
      .catch((e) => { if (!esAbort(e)) setEspecies({ datos: null, cargando: false, error: e.message }); });
    return () => ctl.abort();
  }, [aplicados, resolucion, bboxParam]);

  // La capa demográfica no depende de los filtros: se pide una sola vez, y solo si se activa
  useEffect(() => {
    if (!vista.verPoblacion || poblacion.datos || poblacion.error) return;
    const ctl = new AbortController();
    getPoblacion(ctl.signal)
      .then((d) => setPoblacion({ datos: d, error: null }))
      .catch((e) => { if (!esAbort(e)) setPoblacion({ datos: null, error: e.message }); });
    return () => ctl.abort();
  }, [vista.verPoblacion, poblacion.datos, poblacion.error]);

  // Al elegir una especie se piden las celdas donde fue observada, para iluminarlas en el mapa
  const especieSel = seleccion?.tipo === 'especie' ? seleccion.id : null;
  useEffect(() => {
    if (!especieSel) { setObservaciones({ id: null, datos: null, cargando: false, error: null }); return undefined; }
    const ctl = new AbortController();
    setObservaciones({ id: especieSel, datos: null, cargando: true, error: null });
    getObservaciones(especieSel, resolucion, aplicados.zona, ctl.signal)
      .then((d) => setObservaciones({ id: especieSel, datos: d, cargando: false, error: null }))
      .catch((e) => { if (!esAbort(e)) setObservaciones({ id: especieSel, datos: null, cargando: false, error: e.message }); });
    return () => ctl.abort();
  }, [especieSel, resolucion, aplicados.zona]);

  // Al hacer clic en una celda (con la red de especies activa) se piden sus especies y el grafo se recorta a ellas
  const focoActivo = vista.grafo === 'especies' ? celdaFoco : null;
  useEffect(() => {
    if (!focoActivo) { setEspeciesCelda({ id: null, datos: null, cargando: false, error: null }); return undefined; }
    const ctl = new AbortController();
    setEspeciesCelda({ id: focoActivo, datos: null, cargando: true, error: null });
    getEspeciesDeCelda(focoActivo, aplicados.zona, ctl.signal)
      .then((d) => setEspeciesCelda({ id: focoActivo, datos: d, cargando: false, error: null }))
      .catch((e) => { if (!esAbort(e)) setEspeciesCelda({ id: focoActivo, datos: null, cargando: false, error: e.message }); });
    return () => ctl.abort();
  }, [focoActivo, aplicados.zona]);

  const elegir = useCallback((sel) => {
    setSeleccion(sel);
    if (!sel) setCeldaFoco(null);                       // clic en el fondo o × : vuelve la red completa
    else if (sel.tipo === 'celda') setCeldaFoco(sel.id); // elegir una especie NO cambia la celda enfocada
  }, []);

  const grafo = useMemo(() => {
    if (vista.grafo === 'especies') {
      const color = vista.colorGrafo === 'comunidad' ? 'comunidad' : 'taxonomia';
      const completo = especies.datos ? grafoEspecies(especies.datos, { colorPor: color, tamanoPor: vista.tamanoGrafo }) : null;
      if (completo && focoActivo && especiesCelda.id === focoActivo && especiesCelda.datos) {
        const sub = subgrafoDeEspecies(completo, especiesCelda.datos.especies.map((e) => e.id));
        return { ...sub, titulo: `Especies de la celda ${focoActivo} (${sub.nodos.length})` };
      }
      return completo;
    }
    const color = ['institucion', 'ivc', 'bloque'].includes(vista.colorGrafo) ? vista.colorGrafo : 'institucion';
    return celdas.datos ? grafoCeldas(celdas.datos, { colorPor: color, tamanoPor: vista.tamanoGrafo === 'fuerza_norm' ? 'intermediacion_norm' : vista.tamanoGrafo }) : null;
  }, [vista.grafo, vista.colorGrafo, vista.tamanoGrafo, especies.datos, celdas.datos, focoActivo, especiesCelda]);

    // Especie elegida (desde el buscador o con clic en el grafo) y aviso si no sale dibujada en el grafo
  const especieSeleccionada = useMemo(() => {
    if (seleccion?.tipo !== 'especie') return null;
    const nodo = grafo?.nodos?.find((n) => n.id === seleccion.id);
    return { id: seleccion.id, etiqueta: nodo?.label || seleccion.id };
  }, [seleccion, grafo]);
  const avisoEspecie = useMemo(() => {
    if (!especieSeleccionada || grafo?.tipo !== 'especies') return null;
    const conectada = grafo.aristas.some((e) => e.source === especieSeleccionada.id || e.target === especieSeleccionada.id);
    return conectada ? null : 'Esta especie no tiene vínculos con el umbral actual, por eso no aparece en el grafo; el mapa sí ilumina sus celdas.';
  }, [especieSeleccionada, grafo]);

  const sobreposicion = useMemo(() => (vista.sobreponer && grafo?.tipo === 'celdas' ? datosSobreposicion(grafo) : null), [vista.sobreponer, grafo]);

  const cambiarVista = useCallback((cambios) => {
    // la selección de un tipo de grafo no tiene sentido en el otro
    if (cambios.grafo) setCeldaFoco(null);
    if (cambios.grafo) setSeleccion((sel) => (sel && sel.tipo !== (cambios.grafo === 'especies' ? 'especie' : 'celda') ? null : sel));
    setVista((v) => {
      const nuevo = { ...v, ...cambios };
      // al cambiar de tipo de grafo, el criterio de color anterior deja de existir
      if (cambios.grafo && cambios.grafo !== v.grafo) nuevo.colorGrafo = cambios.grafo === 'especies' ? 'taxonomia' : 'institucion';
      return nuevo;
    });
  }, []);

  return (
    <div className="app" style={{ '--ancho-panel': `${ancho}px` }}>
      <header>
        <h1 className="marca"><Logo tamano={34} /> RedPrimavera</h1>
        <span className="sub">Vulnerabilidad y biodiversidad · Bosque La Primavera</span>
        <span className="estado" role="status" aria-live="polite">
          {celdas.cargando ? 'Cargando…' : celdas.datos ? `${celdas.datos.nodos.length} celdas · resolución ${resolucion}` : 'Sin datos'}
          <button className="ayuda-btn" onClick={() => setBienvenida(true)}
                aria-label="Ver la bienvenida y la ayuda" title="¿Qué es esto?">?</button>
        </span>
      </header>
      <FilterPanel
        form={form} setForm={setForm} vista={vista} cambiarVista={cambiarVista}
        resolucionEfectiva={resolucion}
        aplicar={() => {
          const mc = Math.min(50, Math.max(1, Number(form.min_celdas_compartidas) || 1));
          const f = { ...form, min_celdas_compartidas: mc };
          setForm(f); setSeleccion(null); setCeldaFoco(null); setAplicados(f);
        }}
        limpiar={() => { setForm(FILTROS_VACIOS); setSeleccion(null); setCeldaFoco(null); setAplicados(FILTROS_VACIOS); }}
        metaCeldas={celdas.datos?.meta} metaEspecies={especies.datos?.meta}
        omitidos={sobreposicion?.omitidos}
        especieSel={especieSeleccionada} avisoEspecie={avisoEspecie}
        onElegirEspecie={(id) => elegir({ tipo: 'especie', id })} onQuitarEspecie={() => elegir(null)}
      />
      <div
        className={`divisor${arrastrando ? ' activo' : ''}`}
        role="separator" aria-orientation="vertical" aria-label="Ancho del panel de filtros"
        aria-valuenow={ancho} aria-valuemin={ANCHO_MIN} aria-valuemax={ANCHO_MAX}
        tabIndex={0} title="Arrastra para cambiar el ancho (doble clic para restablecer)"
        onPointerDown={arrastrar} onKeyDown={teclado} onDoubleClick={() => setAncho(ANCHO_INICIAL)}
      />
      <main className="paneles" data-disposicion={vista.disposicion}>
        <MapPanel
          celdas={celdas} poblacion={poblacion} vista={vista} sobreposicion={sobreposicion}
          grafoTipo={grafo?.tipo} observaciones={observaciones} seleccion={seleccion} onSelect={elegir} onEncuadre={setEncuadre}
        />
        <GraphPanel
          grafo={grafo} estado={vista.grafo === 'especies' ? especies : celdas}
          seleccion={seleccion} onSelect={elegir}
        />
      </main>
        {bienvenida && <Bienvenida onCerrar={cerrarBienvenida} onRecorrido={hacerRecorrido} />}
    </div>
  );
}
