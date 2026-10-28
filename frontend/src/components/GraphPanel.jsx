import React, { useEffect, useMemo, useRef, useState } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import Leyenda from './Leyenda.jsx';
import Cargando from './Cargando.jsx';

const FADED = '#d5dad7';
const MUCHAS_ARISTAS = 3000; // por encima, las aristas solo se dibujan al elegir o pasar por un nodo

const DURACION_TRANSICION = 800;     // milisegundos
const MAX_NODOS_ANIMADOS = 4000;     // tamaño del grafo NUEVO; con más, se cambia de golpe
const MAX_ARISTAS_VISIBLES = 400;   // en grafos más densos solo se dibujan las más fuertes
const MAX_ARISTAS_ANIMADAS = 30000;
const mezclaBBox = (a, b, k) => ({
  x: [a.x[0] + (b.x[0] - a.x[0]) * k, a.x[1] + (b.x[1] - a.x[1]) * k],
  y: [a.y[0] + (b.y[0] - a.y[0]) * k, a.y[1] + (b.y[1] - a.y[1]) * k],
});
function extension(puntos) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const p of puntos) {
    if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x;
    if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y;
  }
  if (!Number.isFinite(x0)) return null;
  if (x1 - x0 < 1e-6) { x0 -= 1; x1 += 1; }
  if (y1 - y0 < 1e-6) { y0 -= 1; y1 += 1; }
  return { x: [x0, x1], y: [y0, y1] };
}
const suave = (t) => 1 - Math.pow(1 - t, 3);
const prefiereMenosMovimiento = () => !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const bboxValido = (b) => !!b && [...b.x, ...b.y].every(Number.isFinite);



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
  const animRef = useRef(1);
  const umbralRef = useRef(0);
  const [notaAristas, setNotaAristas] = useState(null);
  const [notaVisible, setNotaVisible] = useState(false);
  const aristasRef = useRef(1);   // 0 a 1: qué tan visibles están las aristas
  const bboxRef = useRef(null);   // último encuadre que dibujamos
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
        if (!activo || !g.hasNode(activo)) {
          if (g.size > MUCHAS_ARISTAS || (attrs.size ?? 0) < umbralRef.current) return { ...attrs, hidden: true };
          return { ...attrs, color: `rgba(154,167,160,${(0.28 * aristasRef.current).toFixed(3)})` };
        }
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
  
  // 2) Cuando cambian los datos, se cambia el grafo dentro de la misma instancia, con transición
  useEffect(() => {
    const r = sigmaRef.current;
    if (!r) return undefined;
    cancelAnimationFrame(animRef.current);
    hoverRef.current = null; setHover(null);

    const anterior = graphRef.current;
    const g = grafo && grafo.nodos.length ? construirGrafo(grafo) : new Graph();

    // Encuadre de llegada: la extensión de las posiciones finales del grafo nuevo
    const puntos = [];
    g.forEachNode((id, a) => puntos.push({ x: a.x, y: a.y }));
    const bboxNuevo = extension(puntos);

    // Encuadre de partida: el último que dibujamos nosotros (no el que reporta Sigma)
    let bboxViejo = bboxRef.current;
    if (!bboxValido(bboxViejo) && anterior && anterior.order > 0) {
      const previos = [];
      anterior.forEachNode((id, a) => previos.push({ x: a.x, y: a.y }));
      bboxViejo = extension(previos);
    }

    const animar = !!anterior && anterior.order > 0 && g.order > 0
      && bboxValido(bboxViejo) && bboxValido(bboxNuevo) && !!r.setCustomBBox
      && g.order <= MAX_NODOS_ANIMADOS && g.size <= MAX_ARISTAS_ANIMADAS
      && !prefiereMenosMovimiento();

    const destino = new Map();
    const origen = new Map();
    if (animar) {
      const cx = (bboxViejo.x[0] + bboxViejo.x[1]) / 2;
      const cy = (bboxViejo.y[0] + bboxViejo.y[1]) / 2;
      g.forEachNode((id, a) => {
        destino.set(id, { x: a.x, y: a.y, size: a.size });
        if (anterior.hasNode(id)) {
          const p = anterior.getNodeAttributes(id);
          const ok = Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.size);
          origen.set(id, ok ? { x: p.x, y: p.y, size: p.size } : { x: cx, y: cy, size: 0 });
        } else {
          origen.set(id, { x: cx, y: cy, size: 0 });   // los nodos nuevos brotan del centro
        }
      });
      g.updateEachNodeAttributes((id, a) => ({ ...a, ...origen.get(id) }), { attributes: ['x', 'y', 'size'] });
    } else {
      r.setCustomBBox?.(null);
    }
    aristasRef.current = animar ? 0 : 1;
    bboxRef.current = bboxNuevo;

    graphRef.current = g;
    let umbral = 0;
    let visibles = g.size;
    if (g.size > MAX_ARISTAS_VISIBLES) {
      const pesos = [];
      g.forEachEdge((e, a) => pesos.push(Number(a.size) || 0));
      pesos.sort((a, b) => b - a);
      umbral = pesos[MAX_ARISTAS_VISIBLES - 1];
      visibles = pesos.filter((p) => p >= umbral).length;
      if (visibles > MAX_ARISTAS_VISIBLES * 2) { umbral = Infinity; visibles = 0; }  // pesos casi iguales: no hay cómo elegir
    }
    umbralRef.current = umbral;
    setNotaAristas(g.size > MAX_ARISTAS_VISIBLES
      ? (visibles > 0
        ? `Mostrando las ${visibles} conexiones más fuertes de ${g.size}. Pasa el mouse sobre una especie para ver todas las suyas.`
        : 'Hay muchísimas conexiones. Pasa el mouse sobre una especie para ver las suyas.')
      : null);
    r.setGraph(g);
    if (animar) r.setCustomBBox(bboxViejo);
    r.getCamera().animatedReset({ duration: animar ? DURACION_TRANSICION : 0 });
    r.refresh();
    if (!animar) return undefined;

    // Deja todo en su lugar final, pase lo que pase
    const terminar = () => {
      g.updateEachNodeAttributes((id, a) => ({ ...a, ...destino.get(id) }), { attributes: ['x', 'y', 'size'] });
      aristasRef.current = 1;
      bboxRef.current = bboxNuevo;
      r.setCustomBBox(null);
      r.refresh();
    };

    const inicio = performance.now();
    let ultimoBBox = bboxViejo;
    const paso = (ahora) => {
      try {
        const t = Math.min(1, (ahora - inicio) / DURACION_TRANSICION);
        const k = suave(t);
        g.updateEachNodeAttributes((id, a) => {
          const o = origen.get(id); const d = destino.get(id);
          const x = o.x + (d.x - o.x) * k;
          const y = o.y + (d.y - o.y) * k;
          const size = o.size + (d.size - o.size) * k;
          return { ...a, x: Number.isFinite(x) ? x : d.x, y: Number.isFinite(y) ? y : d.y, size: Number.isFinite(size) ? size : d.size };
        }, { attributes: ['x', 'y', 'size'] });
        const bb = mezclaBBox(bboxViejo, bboxNuevo, k);
        ultimoBBox = bboxValido(bb) ? bb : bboxNuevo;
        bboxRef.current = ultimoBBox;
        r.setCustomBBox(ultimoBBox);
        aristasRef.current = suave(Math.max(0, (t - 0.4) / 0.6));   // las aristas aparecen al final
        r.refresh();
        if (t < 1) animRef.current = requestAnimationFrame(paso);
        else terminar();
      } catch (err) {
        console.error('Transición del grafo:', err);
        terminar();
      }
    };
    animRef.current = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(animRef.current);
  }, [grafo]);

  // La selección cambió desde fuera (p. ej. clic en el mapa): redibuja con el resalte
  useEffect(() => { sigmaRef.current?.refresh(); }, [idSel]);
  // La nota aparece unos segundos al cambiar el grafo y se desvanece sola
  useEffect(() => {
    if (!notaAristas) { setNotaVisible(false); return undefined; }
    setNotaVisible(true);
    const t = setTimeout(() => setNotaVisible(false), 6000);
    return () => clearTimeout(t);
  }, [notaAristas]);

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
      {notaAristas && !estado.cargando && (
        <div className={`aviso-flotante nota-aristas${notaVisible ? '' : ' oculta'}`}>{notaAristas}</div>
      )}
    </section>
  );
}
