import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getCeldas, getEspecies, getObservaciones, getPoblacion } from './api.js';
import { ZOOM_PARA_RES_9 } from './config.js';
import { bboxTexto } from './mapData.js';
import { datosSobreposicion, grafoCeldas, grafoEspecies } from './graphData.js';
import FilterPanel from './components/FilterPanel.jsx';
import MapPanel from './components/MapPanel.jsx';
import GraphPanel from './components/GraphPanel.jsx';

export const FILTROS_VACIOS = {
  ivc_min: '', ivc_max: '', frecuencia_min: '', distancia_camino_max: '', en_predio: '',
  zona: '', min_celdas_compartidas: 2,
};
const VISTA_INICIAL = {
  resolucion: 8, colorMapa: 'ivc', disposicion: 'lado', sobreponer: false, verPoblacion: false,
  dinamico: false, autoRes: false, grafo: 'especies', colorGrafo: 'taxonomia', tamanoGrafo: 'intermediacion_norm',
};
const esAbort = (e) => e?.name === 'AbortError';

export default function App() {
  const [form, setForm] = useState(FILTROS_VACIOS);        // lo que se está editando
  const [aplicados, setAplicados] = useState(FILTROS_VACIOS); // lo que se envió a la API
  const [vista, setVista] = useState(VISTA_INICIAL);
  const [encuadre, setEncuadre] = useState(null);           // { bbox: [w,s,e,n], zoom } reportado por el mapa
  const [celdas, setCeldas] = useState({ datos: null, cargando: true, error: null });
  const [especies, setEspecies] = useState({ datos: null, cargando: true, error: null });
  const [poblacion, setPoblacion] = useState({ datos: null, error: null });
  const [seleccion, setSeleccion] = useState(null);         // { tipo: 'celda' | 'especie', id }
  const [observaciones, setObservaciones] = useState({ id: null, datos: null, cargando: false, error: null });

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

  const grafo = useMemo(() => {
    if (vista.grafo === 'especies') {
      const color = vista.colorGrafo === 'comunidad' ? 'comunidad' : 'taxonomia';
      return especies.datos ? grafoEspecies(especies.datos, { colorPor: color, tamanoPor: vista.tamanoGrafo }) : null;
    }
    const color = ['institucion', 'ivc', 'bloque'].includes(vista.colorGrafo) ? vista.colorGrafo : 'institucion';
    return celdas.datos ? grafoCeldas(celdas.datos, { colorPor: color, tamanoPor: vista.tamanoGrafo === 'fuerza_norm' ? 'intermediacion_norm' : vista.tamanoGrafo }) : null;
  }, [vista.grafo, vista.colorGrafo, vista.tamanoGrafo, especies.datos, celdas.datos]);

  const sobreposicion = useMemo(() => (vista.sobreponer && grafo?.tipo === 'celdas' ? datosSobreposicion(grafo) : null), [vista.sobreponer, grafo]);

  const cambiarVista = useCallback((cambios) => {
    // la selección de un tipo de grafo no tiene sentido en el otro
    if (cambios.grafo) setSeleccion((sel) => (sel && sel.tipo !== (cambios.grafo === 'especies' ? 'especie' : 'celda') ? null : sel));
    setVista((v) => {
      const nuevo = { ...v, ...cambios };
      // al cambiar de tipo de grafo, el criterio de color anterior deja de existir
      if (cambios.grafo && cambios.grafo !== v.grafo) nuevo.colorGrafo = cambios.grafo === 'especies' ? 'taxonomia' : 'institucion';
      return nuevo;
    });
  }, []);

  return (
    <div className="app">
      <header>
        <h1>RedPrimavera</h1>
        <span className="sub">Vulnerabilidad y biodiversidad · Bosque La Primavera</span>
        <span className="estado" role="status" aria-live="polite">
          {celdas.cargando ? 'Cargando…' : celdas.datos ? `${celdas.datos.nodos.length} celdas · resolución ${resolucion}` : 'Sin datos'}
        </span>
      </header>
      <FilterPanel
        form={form} setForm={setForm} vista={vista} cambiarVista={cambiarVista}
        resolucionEfectiva={resolucion}
        aplicar={() => {
          const mc = Math.min(50, Math.max(1, Number(form.min_celdas_compartidas) || 1));
          const f = { ...form, min_celdas_compartidas: mc };
          setForm(f); setSeleccion(null); setAplicados(f);
        }}
        limpiar={() => { setForm(FILTROS_VACIOS); setSeleccion(null); setAplicados(FILTROS_VACIOS); }}
        metaCeldas={celdas.datos?.meta} metaEspecies={especies.datos?.meta}
        omitidos={sobreposicion?.omitidos}
      />
      <main className="paneles" data-disposicion={vista.disposicion}>
        <MapPanel
          celdas={celdas} poblacion={poblacion} vista={vista} sobreposicion={sobreposicion}
          grafoTipo={grafo?.tipo} observaciones={observaciones} seleccion={seleccion} onSelect={setSeleccion} onEncuadre={setEncuadre}
        />
        <GraphPanel
          grafo={grafo} estado={vista.grafo === 'especies' ? especies : celdas}
          seleccion={seleccion} onSelect={setSeleccion}
        />
      </main>
    </div>
  );
}
