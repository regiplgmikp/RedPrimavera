import React, { useEffect, useMemo, useRef, useState } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import Leyenda from './Leyenda.jsx';
import Cargando from './Cargando.jsx';

const FADED = '#d5dad7';
const MUCHAS_ARISTAS = 3000; // por encima, las aristas solo se dibujan al elegir o pasar por un nodo

function posicionesIniciales(grafo) {
  const n = grafo.nodos.length;
  return grafo.nodos.map((nodo, i) => {
    if (grafo.tipo === 'celdas' && nodo.lat != null) {
      // distribución geográfica como punto de partida: el layout conserva la forma del bosque
      return [nodo.lon * 120 * Math.cos((nodo.lat * Math.PI) / 180), nodo.lat * 120];
    }
    const a = (i / Math.max(n, 1)) * 2 * Math.PI;
    return [Math.cos(a) * 10, Math.sin(a) * 10];
  });
}

export function construirGrafo(spec) {
  const g = new Graph({ type: 'undirected', multi: false });
  const pos = posicionesIniciales(spec);
  spec.nodos.forEach((n, i) => g.addNode(n.id, { label: n.label, size: n.size, color: n.color, x: pos[i][0], y: pos[i][1] }));
  for (const e of spec.aristas) {
    if (g.hasNode(e.source) && g.hasNode(e.target) && e.source !== e.target && !g.hasEdge(e.source, e.target)) {
      g.addEdge(e.source, e.target, { size: e.size, color: 'rgba(154,167,160,0.28)' });
    }
  }
  //if (spec.tipo === 'especies') {
    // las especies sin ninguna arista no aportan a la red y se apilan en un anillo: no se dibujan
  //  g.nodes().forEach((id) => { if (g.degree(id) === 0) g.dropNode(id); });
  //}
  if (g.order > 1 && g.size > 0) {
    forceAtlas2.assign(g, {
      iterations: g.order > 800 ? 80 : 200,
      settings: { ...forceAtlas2.inferSettings(g), barnesHutOptimize: g.order > 300, strongGravityMode: true, gravity: 1, slowDown: 3 },
    });
  }
  return g;
}

export default function GraphPanel({ grafo, estado, seleccion, onSelect }) {
  const contenedor = useRef(null);
  const sigmaRef = useRef(null);
  const graphRef = useRef(null);
  const hoverRef = useRef(null);
  const activoRef = useRef(null);
  const [hover, setHover] = useState(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const tipoSel = grafo?.tipo === 'especies' ? 'especie' : 'celda';
  const idSel = seleccion && seleccion.tipo === tipoSel ? seleccion.id : null;
  activoRef.current = idSel;

  const porId = useMemo(() => new Map((grafo?.nodos || []).map((n) => [n.id, n])), [grafo]);

  const tipoRef = useRef(tipoSel);
  tipoRef.current = tipoSel;

  // 1) Una sola instancia de Sigma durante toda la vida del panel (un solo contexto WebGL)
  useEffect(() => {
    if (!contenedor.current) return undefined;
    const oscuro = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const r = new Sigma(new Graph(), contenedor.current, {
      renderLabels: true, labelDensity: 0.5, labelGridCellSize: 170, labelRenderedSizeThreshold: 4, labelSize: 12,
      labelColor: { color: oscuro ? '#e8ece9' : '#1d2421' }, defaultEdgeColor: 'rgba(154,167,160,0.28)',
      minCameraRatio: 0.03, maxCameraRatio: 20,
      nodeReducer: (nodo, attrs) => {
        const g = graphRef.current;
        const activo = hoverRef.current || activoRef.current;
        if (!g || !activo) return attrs;
        if (nodo === activo) return { ...attrs, highlighted: true, zIndex: 2 };
        if (g.hasNode(activo) && g.areNeighbors(nodo, activo)) return attrs;
        return { ...attrs, color: FADED, label: null };
      },
      edgeReducer: (arista, attrs) => {
        const g = graphRef.current;
        const activo = hoverRef.current || activoRef.current;
        if (!g) return attrs;
        if (!activo || !g.hasNode(activo)) return g.size > MUCHAS_ARISTAS ? { ...attrs, hidden: true } : attrs;
        return g.hasExtremity(arista, activo) ? { ...attrs, color: '#5d6a64' } : { ...attrs, hidden: true };
      },
    });
    r.on('enterNode', ({ node }) => { hoverRef.current = node; setHover(node); r.refresh(); });
    r.on('leaveNode', () => { hoverRef.current = null; setHover(null); r.refresh(); });
    r.on('clickNode', ({ node }) => onSelectRef.current({ tipo: tipoRef.current, id: node }));
    r.on('clickStage', () => onSelectRef.current(null));
    sigmaRef.current = r;

    let ro;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => { try { r.refresh(); } catch { /* destruido */ } });
      ro.observe(contenedor.current);
    }
    return () => {
      ro?.disconnect();
      try {
        Object.values(r.getCanvases?.() || {}).forEach((c) => {
          const gl = c.getContext?.('webgl2') || c.getContext?.('webgl');
          gl?.getExtension?.('WEBGL_lose_context')?.loseContext();
        });
      } catch { /* sin WebGL o ya liberado */ }
      r.kill();
      sigmaRef.current = null; graphRef.current = null;
    };
  }, []);

  // 2) Cuando cambian los datos, solo se cambia el grafo dentro de la misma instancia
  useEffect(() => {
    const r = sigmaRef.current;
    if (!r) return;
    hoverRef.current = null; setHover(null);
    const g = grafo && grafo.nodos.length ? construirGrafo(grafo) : new Graph();
    graphRef.current = g;
    r.setGraph(g);
    r.getCamera().animatedReset({ duration: 0 });
    r.refresh();
  }, [grafo]);

  // La selección cambió desde fuera (p. ej. clic en el mapa): redibuja con el resalte
  useEffect(() => { sigmaRef.current?.refresh(); }, [idSel]);

  const info = porId.get(hover || idSel);

  return (
    <section className="panel">
      <h3>Grafo · {grafo?.titulo || '—'}</h3>
      <div ref={contenedor} className="sigma" aria-label="Grafo de relaciones" />
      {grafo && grafo.nodos.length > 0 && <Leyenda modo="grafo" leyenda={grafo.leyenda} />}
      {info && (
        <div className="info" role="status">
          <b>{info.label}</b><br />{info.grupo}
          {info.detalle.intermediacion != null && <> · intermediación {info.detalle.intermediacion.toFixed(3)}</>}
          {info.detalle.grado != null && <> · vínculos {info.detalle.grado}</>}
          {info.detalle.ivc != null && <> · IVC {info.detalle.ivc.toFixed(2)}</>}
        </div>
      )}
      {estado.error && <div className="msg">{estado.error}</div>}
      {estado.cargando && (
    <div className={grafo ? 'espera-flotante' : 'msg'}>
      <Cargando texto="Armando la red de especies…" tamano={grafo ? 56 : 96} />
    </div>
  )}
      {!estado.error && !estado.cargando && grafo && !grafo.nodos.length && <div className="msg">Sin nodos con las condiciones elegidas.</div>}
    </section>
  );
}
