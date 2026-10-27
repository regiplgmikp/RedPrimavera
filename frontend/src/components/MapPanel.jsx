import React, { useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { WebMercatorViewport } from '@deck.gl/core';
import { BitmapLayer, LineLayer, PolygonLayer, ScatterplotLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import { ATRIBUCION_MAPA } from '../config.js';
import { hexARgb } from '../colors.js';
import { CAMPOS_COLOR, centroPoligono, colorCelda, htmlCelda, limitesDeCeldas, poligonoDeCelda, radioPoblacion, rangoDe } from '../mapData.js';
import Leyenda from './Leyenda.jsx';
import Cargando from './Cargando.jsx';

const TILES = {
  claro: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  oscuro: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
};
const VISTA_INICIAL = { longitude: -103.55, latitude: 20.65, zoom: 10.5, pitch: 0, bearing: 0 };
const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ESTILO_TOOLTIP = { backgroundColor: 'rgba(255,255,255,.96)', color: '#1d2421', fontSize: '12px', borderRadius: '6px', padding: '6px 9px', maxWidth: '280px' };

function usarTemaOscuro() {
  const [oscuro, setOscuro] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return undefined;
    const h = (e) => setOscuro(e.matches);
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, []);
  return oscuro;
}

export default function MapPanel({ celdas, poblacion, vista, sobreposicion, grafoTipo, observaciones, seleccion, onSelect, onEncuadre }) {
  const contenedor = useRef(null);
  const [tam, setTam] = useState({ width: 800, height: 600 });
  const [tip, setTip] = useState(null); // información bajo el cursor: { x, y, html }
  const [viewState, setViewState] = useState(VISTA_INICIAL);
  const [ajusteTick, setAjusteTick] = useState(0);
  const yaAjustado = useRef(false);
  const oscuro = usarTemaOscuro();

  useEffect(() => {
    const el = contenedor.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([e]) => setTam({ width: Math.max(1, e.contentRect.width), height: Math.max(1, e.contentRect.height) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const datos = celdas.datos;
  const celdasMapa = useMemo(() => (datos ? datos.nodos.map((c) => ({ id: c.h3_id, poligono: poligonoDeCelda(c), celda: c })) : []), [datos]);
  const rango = useMemo(() => (datos && datos.nodos.length ? rangoDe(datos.nodos, vista.colorMapa) : [0, 1]), [datos, vista.colorMapa]);

  // Encuadre: la primera vez que llegan datos y cada vez que se pulsa "Encuadrar". Con datos
  // nuevos por filtros o por carga dinámica NO se reencuadra (sería un bucle: mover -> cargar -> saltar).
  const tickAtendido = useRef(0);
  useEffect(() => {
    if (!datos || !datos.nodos.length) return;
    const pidioUsuario = ajusteTick !== tickAtendido.current;
    if (yaAjustado.current && !pidioUsuario) return;
    const lim = limitesDeCeldas(datos.nodos);
    if (!lim) return;
    try {
      const vp = new WebMercatorViewport({ width: tam.width, height: tam.height });
      const { longitude, latitude, zoom } = vp.fitBounds(lim, { padding: 40 });
      setViewState((v) => ({ ...v, longitude, latitude, zoom: Math.min(zoom, 15) }));
      yaAjustado.current = true;
      tickAtendido.current = ajusteTick;
    } catch { /* tamaño aún no medido */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos, ajusteTick]);

  // Reporta al App el encuadre (bbox y zoom) con retraso, para la carga dinámica
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        const bounds = new WebMercatorViewport({ ...viewState, width: tam.width, height: tam.height }).getBounds();
        onEncuadre({ bbox: bounds, zoom: viewState.zoom });
      } catch { /* sin tamaño */ }
    }, 700);
    return () => clearTimeout(t);
  }, [viewState, tam, onEncuadre]);

  const puntosPoblacion = useMemo(() => {
    if (!poblacion.datos) return [];
    const max = Math.max(1, ...poblacion.datos.celdas.map((c) => c.poblacion));
    return poblacion.datos.celdas
      .map((c) => ({ id: c.h3_id, position: centroPoligono(c.boundary.map(([la, lo]) => [lo, la])), pob: c.poblacion, radio: radioPoblacion(c.poblacion, max) }))
      .filter((p) => p.radio > 0);
  }, [poblacion.datos]);

  const celdasObservadas = useMemo(() => {
    const cs = observaciones?.datos?.celdas || [];
    const max = Math.max(1, ...cs.map((c) => c.n_observaciones));
    return cs.map((c) => ({ id: c.h3_id, poligono: poligonoDeCelda(c), n: c.n_observaciones, t: Math.sqrt(c.n_observaciones / max) }));
  }, [observaciones?.datos]);

  const idCeldaSel = seleccion?.tipo === 'celda' ? seleccion.id : null;
  const celdaSel = idCeldaSel && datos ? datos.nodos.find((c) => c.h3_id === idCeldaSel) : null;
  const idNodoSel = seleccion && sobreposicion ? seleccion.id : null;

  const capas = [
    new TileLayer({
      id: 'base', data: oscuro ? TILES.oscuro : TILES.claro, minZoom: 0, maxZoom: 16, tileSize: 256,
      renderSubLayers: (props) => {
        const { boundingBox } = props.tile;
        return new BitmapLayer(props, { data: null, image: props.data, bounds: [boundingBox[0][0], boundingBox[0][1], boundingBox[1][0], boundingBox[1][1]] });
      },
    }),
    new PolygonLayer({
      id: 'celdas', data: celdasMapa, pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 90],
      stroked: true, filled: true, lineWidthUnits: 'pixels',
      getPolygon: (d) => d.poligono,
      getFillColor: (d) => colorCelda(d.celda, vista.colorMapa, rango),
      getLineColor: (d) => (d.id === idCeldaSel ? [15, 15, 15, 255] : [255, 255, 255, 120]),
      getLineWidth: (d) => (d.id === idCeldaSel ? 3 : 0.6),
      updateTriggers: { getFillColor: [vista.colorMapa, rango[0], rango[1]], getLineColor: [idCeldaSel], getLineWidth: [idCeldaSel] },
    }),
    celdasObservadas.length > 0 && new PolygonLayer({
      id: 'observaciones', data: celdasObservadas, pickable: true, stroked: true, filled: true, lineWidthUnits: 'pixels',
      getPolygon: (d) => d.poligono,
      getFillColor: (d) => [0, 200, 255, Math.round(90 + 150 * d.t)],
      getLineColor: [255, 255, 255, 255], getLineWidth: 2,
    }),
    vista.verPoblacion && puntosPoblacion.length && new ScatterplotLayer({
      id: 'poblacion', data: puntosPoblacion, pickable: true, radiusUnits: 'meters', stroked: true, lineWidthUnits: 'pixels',
      getPosition: (d) => d.position, getRadius: (d) => d.radio,
      getFillColor: [30, 90, 200, 90], getLineColor: [30, 90, 200, 230], getLineWidth: 1.2,
    }),
    sobreposicion && new LineLayer({
      id: 'grafo-aristas', data: sobreposicion.lineas, widthUnits: 'pixels', widthMinPixels: 0.6,
      getSourcePosition: (d) => d.from, getTargetPosition: (d) => d.to,
      getColor: oscuro ? [255, 255, 255, 70] : [20, 20, 20, 80], getWidth: (d) => d.ancho,
    }),
    sobreposicion && new ScatterplotLayer({
      id: 'grafo-nodos', data: sobreposicion.puntos, pickable: true, radiusUnits: 'meters', stroked: true, lineWidthUnits: 'pixels',
      getPosition: (d) => d.position, getRadius: (d) => d.radio,
      getFillColor: (d) => hexARgb(d.color, 235),
      getLineColor: (d) => (d.id === idNodoSel ? [15, 15, 15, 255] : [255, 255, 255, 200]),
      getLineWidth: (d) => (d.id === idNodoSel ? 3 : 1),
      updateTriggers: { getLineColor: [idNodoSel], getLineWidth: [idNodoSel] },
    }),
  ].filter(Boolean);

  const alClic = (info) => {
    if (!info?.object) return;
    const id = info.layer?.id;
    if (id === 'celdas') onSelect({ tipo: 'celda', id: info.object.id });
    else if (id === 'observaciones') onSelect({ tipo: 'celda', id: info.object.id });
    else if (id === 'grafo-nodos') onSelect({ tipo: grafoTipo === 'especies' ? 'especie' : 'celda', id: info.object.id });
  };
  const tooltip = ({ object, layer }) => {
    if (!object) return null;
    if (layer.id === 'celdas') return { html: htmlCelda(object.celda), style: ESTILO_TOOLTIP };
    if (layer.id === 'grafo-nodos') return { html: `<b>${esc(object.label)}</b>`, style: ESTILO_TOOLTIP };
    if (layer.id === 'observaciones') return { html: `${object.n} observaci${object.n === 1 ? 'ón' : 'ones'} de ${esc(observaciones.id)}`, style: ESTILO_TOOLTIP };
    if (layer.id === 'poblacion') return { html: `Población estimada: ${Math.round(object.pob).toLocaleString('es-MX')}`, style: ESTILO_TOOLTIP };
    return null;
  };

  return (
    <section className="panel" ref={contenedor}>
      <h3>Mapa · celdas H3</h3>
      <button className="flotante" onClick={() => setAjusteTick((t) => t + 1)}>Encuadrar</button>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: v }) => setViewState(v)}
        controller
        layers={capas}
        onHover={(info) => { const t = info?.object ? tooltip(info) : null; setTip(t ? { x: info.x, y: info.y, html: t.html } : null); }}
        onClick={alClic}
        style={{ position: 'absolute', inset: 0 }}
      />
      {tip && (
        <div className="tip-mapa" style={{ position: 'absolute', zIndex: 4, pointerEvents: 'none', left: Math.max(8, Math.min(tip.x + 14, tam.width - 300)), top: Math.max(8, Math.min(tip.y + 14, tam.height - 210)), maxWidth: 290, fontSize: 12, lineHeight: 1.5, padding: '6px 9px', background: 'var(--panel)', color: 'var(--ink)', border: '1px solid var(--line)', borderRadius: 6, boxShadow: '0 2px 8px rgba(0,0,0,.35)' }}
          dangerouslySetInnerHTML={{ __html: tip.html }} />
      )}
      {celdaSel && (
        <div className="detalle-celda" role="status" style={{ position: 'absolute', top: 44, left: 12, zIndex: 3, maxWidth: 300, fontSize: 12, lineHeight: 1.5, padding: '8px 28px 8px 10px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 6 }}>
          <button aria-label="Cerrar detalle" onClick={() => onSelect(null)} style={{ position: 'absolute', top: 2, right: 4, padding: '0 6px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit', fontSize: 14 }}>×</button>
          <div dangerouslySetInnerHTML={{ __html: htmlCelda(celdaSel) }} />
        </div>
      )}
      <Leyenda
        modo="mapa" campo={vista.colorMapa} def={CAMPOS_COLOR[vista.colorMapa]} rango={rango}
        poblacion={vista.verPoblacion ? poblacion : null} sobreponer={Boolean(sobreposicion)} observaciones={observaciones}
      />
      <div className="atribucion">{ATRIBUCION_MAPA}{vista.verPoblacion && poblacion.datos ? ' · Población: Kontur (CC BY 4.0)' : ''}</div>
      {celdas.error && <div className="msg">{celdas.error}</div>}
      {!celdas.error && !celdas.cargando && datos && !datos.nodos.length && <div className="msg">Ninguna celda cumple los filtros.</div>}
        {celdas.cargando && (
    <div className={datos ? 'espera-flotante' : 'msg'}>
      <Cargando texto="Cargando el mapa…" tamano={datos ? 56 : 96} />
    </div>
  )}
      {vista.verPoblacion && poblacion.error && <div className="aviso-flotante">Capa demográfica: {poblacion.error}</div>}
      {vista.verPoblacion && poblacion.datos && poblacion.datos.n_celdas === 0 && (
        <div className="aviso-flotante">No hay población cargada: corre etls/etl_poblacion_kontur.py</div>
      )}
    </section>
  );
}
