import React, { useEffect, useRef, useState } from 'react';

const MAX_ENLACES_3D = 2500;       // más que esto se vuelve pesado: se usan solo los más fuertes
const MAX_ENLACES_VISIBLES = 400;  // en reposo solo se dibujan los más fuertes
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const idDe = (extremo) => (extremo !== null && typeof extremo === 'object' ? extremo.id : extremo);

export default function Grafo3D({ grafo, idSel, tipo, girando, onSelect, onHover }) {
  const caja = useRef(null);
  const gRef = useRef(null);
  const [listo, setListo] = useState(false);
  const [error, setError] = useState(null);
  const activoRef = useRef(null);
  const hoverRef = useRef(null);
  const vecinosRef = useRef(new Map());
  const umbralRef = useRef(0);
  const porAjustarRef = useRef(false);
  const onSelectRef = useRef(onSelect); onSelectRef.current = onSelect;
  const onHoverRef = useRef(onHover); onHoverRef.current = onHover;
  const tipoRef = useRef(tipo); tipoRef.current = tipo;
  activoRef.current = idSel;

  // 1) Crear la escena una sola vez (la librería se descarga solo cuando se necesita)
  useEffect(() => {
    let vivo = true; let ro; let g;
    const oscuro = !!window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const colorEnlace = oscuro ? '#9aa7a0' : '#6b7a73';
    const colorApagado = oscuro ? '#46514c' : '#c5cdc9';
    const activo = () => hoverRef.current || activoRef.current;
    const incidente = (l) => { const a = activo(); return !!a && (idDe(l.source) === a || idDe(l.target) === a); };
    const esVecino = (id) => { const a = activo(); return !a || id === a || !!vecinosRef.current.get(a)?.has(id); };

    import('3d-force-graph').then(({ default: ForceGraph3D }) => {
      if (!vivo || !caja.current) return;
      g = new ForceGraph3D(caja.current, { controlType: 'orbit' })
        .backgroundColor('rgba(0,0,0,0)')
        .showNavInfo(false)
        .enableNodeDrag(false)
        .nodeRelSize(3)
        .nodeOpacity(0.9)
        .nodeVal((n) => n.val)
        .nodeColor((n) => (esVecino(n.id) ? n.color : colorApagado))
        .nodeLabel((n) => esc(n.name))
        .linkOpacity(0.35)
        .linkColor((l) => (incidente(l) ? '#F4B72E' : colorEnlace))
        .linkVisibility((l) => incidente(l) || l.peso >= umbralRef.current)
        .linkDirectionalParticles((l) => (incidente(l) ? 3 : 0))
        .linkDirectionalParticleWidth(2.2)
        .linkDirectionalParticleSpeed(0.006)
        .linkDirectionalParticleColor(() => '#F4B72E')
        .onNodeClick((n) => onSelectRef.current({ tipo: tipoRef.current, id: n.id }))
        .onBackgroundClick(() => onSelectRef.current(null))
        .onNodeHover((n) => { hoverRef.current = n ? n.id : null; onHoverRef.current(n ? n.id : null); g.refresh(); })
        .cooldownTime(4000)
        .onEngineStop(() => {
          if (porAjustarRef.current) { porAjustarRef.current = false; g.zoomToFit(600, 40); }
        });
      const medir = () => { if (caja.current) g.width(caja.current.clientWidth).height(caja.current.clientHeight); };
      medir();
      if (typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(medir); ro.observe(caja.current); }
      gRef.current = g;
      setListo(true);
    }).catch((e) => { console.error('Grafo 3D:', e); setError('No se pudo abrir la vista 3D en este navegador.'); });

    return () => {
      vivo = false;
      ro?.disconnect();
      try { g?.pauseAnimation?.(); g?._destructor?.(); } catch { /* ya liberado */ }
      gRef.current = null;
    };
  }, []);

  // 2) Cuando cambian los datos, se vuelven a cargar nodos y enlaces
  useEffect(() => {
    const g = gRef.current;
    if (!g || !listo) return;
    const nodos = (grafo?.nodos || []).map((n) => ({ id: n.id, name: n.label, color: n.color, val: Math.max(1, Number(n.size) || 1) }));
    const ids = new Set(nodos.map((n) => n.id));
    let enlaces = (grafo?.aristas || [])
      .filter((e) => ids.has(e.source) && ids.has(e.target) && e.source !== e.target)
      .map((e) => ({ source: e.source, target: e.target, peso: Number(e.size) || 0 }));
    if (enlaces.length > MAX_ENLACES_3D) enlaces = enlaces.sort((a, b) => b.peso - a.peso).slice(0, MAX_ENLACES_3D);

    const vec = new Map(nodos.map((n) => [n.id, new Set()]));
    enlaces.forEach((e) => { vec.get(e.source).add(e.target); vec.get(e.target).add(e.source); });
    vecinosRef.current = vec;

    let umbral = 0;
    if (enlaces.length > MAX_ENLACES_VISIBLES) {
      const pesos = enlaces.map((e) => e.peso).sort((a, b) => b - a);
      umbral = pesos[MAX_ENLACES_VISIBLES - 1];
      if (pesos.filter((p) => p >= umbral).length > MAX_ENLACES_VISIBLES * 2) umbral = Infinity;
    }
    umbralRef.current = umbral;
    porAjustarRef.current = true;
    g.graphData({ nodes: nodos, links: enlaces });
  }, [grafo, listo]);

  // 3) La selección cambió (desde aquí o desde el mapa): se redibuja el resalte
  useEffect(() => { gRef.current?.refresh(); }, [idSel, listo]);

  // 4) Giro automático de la cámara
  useEffect(() => {
    const c = gRef.current?.controls?.();
    if (!c) return;
    c.autoRotate = !!girando;
    c.autoRotateSpeed = 1.2;
  }, [girando, listo]);

  return (
    <>
      <div ref={caja} className="grafo3d" aria-label="Grafo 3D de relaciones" />
      {error && <div className="msg">{error}</div>}
    </>
  );
}