import React, { useMemo } from 'react';

const rnd = (a, b) => a + Math.random() * (b - a);
const TIPOS = ['estrellas', 'luciernagas', 'hojas'];
export const tipoAlAzar = () => TIPOS[Math.floor(Math.random() * TIPOS.length)];

const Estrella = () => (
  <svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 1 L14.5 9.5 L23 12 L14.5 14.5 L12 23 L9.5 14.5 L1 12 L9.5 9.5 Z" /></svg>
);
const Pluma = () => (
  <svg viewBox="0 0 24 24"><path fill="currentColor" d="M20 3C11 3 5 9 5 17c0 1 .1 2 .3 3l1.6-1.6C7 15 9 12 13 10c-3 3-5 6-5.5 9.5.8.3 1.6.5 2.5.5 8 0 10-8 10-17z" /></svg>
);
const Hoja = () => (
  <svg viewBox="0 0 24 24">
    <path fill="currentColor" d="M12 2C7 7 5 12 6.5 17c1 2.5 3.300 4.200 5.500 5 2.200-.8 4.500-2.500 5.500-5C19 12 17 7 12 2z" />
    <path d="M12 8v12" stroke="var(--bg)" strokeWidth="1.2" fill="none" opacity=".6" />
  </svg>
);

function crearPiezas(tipo) {
  const n = tipo === 'luciernagas' ? 9 : tipo === 'hojas' ? 7 : 10;
  return Array.from({ length: n }, (_, i) => {
    const ang = rnd(0, Math.PI * 2);
    const dist = tipo === 'luciernagas' ? rnd(25, 70) : rnd(30, 85);
    const cae = tipo === 'hojas';
    return {
      k: i,
      dx: Math.cos(ang) * dist,
      dy: Math.sin(ang) * dist * (cae ? 0.6 : 1) - (cae ? 20 : 0),
      cae: cae ? rnd(30, 70) : 0,
      rot: rnd(-200, 200),
      s: tipo === 'luciernagas' ? rnd(4, 8) : rnd(11, 18),
      d: rnd(0, 0.25),
      t: tipo === 'luciernagas' ? rnd(1.4, 2.0) : rnd(0.9, 1.5),
      variante: cae ? (Math.random() < 0.5 ? 'hoja' : 'pluma') : tipo,
    };
  });
}

// Ráfaga de detalles alrededor de un punto (x, y) en píxeles del panel.
export default function Destellos({ x, y, tipo, llave }) {
  const piezas = useMemo(() => crearPiezas(tipo), [llave, tipo]);
  return (
    <span className="destellos" style={{ left: x, top: y }} aria-hidden="true">
      {piezas.map((p) => (
        <span
          key={`${llave}-${p.k}`}
          className={`destello ${p.variante}`}
          style={{
            width: p.s, height: p.s,
            '--dx': `${p.dx}px`, '--dy': `${p.dy}px`, '--cae': `${p.cae}px`, '--rot': `${p.rot}deg`,
            animationDuration: `${p.t}s`, animationDelay: `${p.d}s`,
          }}
        >
          {p.variante === 'estrellas' ? <Estrella /> : p.variante === 'hoja' ? <Hoja /> : p.variante === 'pluma' ? <Pluma /> : null}
        </span>
      ))}
    </span>
  );
}