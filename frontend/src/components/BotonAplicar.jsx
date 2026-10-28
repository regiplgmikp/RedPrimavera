import React, { useEffect, useRef, useState } from 'react';

const rnd = (a, b) => a + Math.random() * (b - a);

// Genera una ráfaga: 8 estrellitas (rápidas) y 5 plumas (lentas, que giran y caen).
function crearRafaga(id, signo = -1) {
  const estrellas = Array.from({ length: 8 }, (_, i) => ({
    tipo: 'estrella', k: `${id}-e${i}`, x: rnd(15, 85), dx: rnd(-50, 50), dy: signo * rnd(40, 95),
    rot: rnd(-90, 90), t: rnd(0.7, 1.0), d: rnd(0, 0.12), s: rnd(10, 18),
  }));
  const plumas = Array.from({ length: 5 }, (_, i) => ({
    tipo: 'pluma', k: `${id}-p${i}`, x: rnd(10, 90), dx: rnd(-80, 80), dy: signo * rnd(30, 70),
    rot: rnd(-240, 240), t: rnd(1.0, 1.3), d: rnd(0, 0.18), s: rnd(14, 20),
  }));
  return [...estrellas, ...plumas];
}

const Estrella = () => (
  <svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 1 L14.5 9.5 L23 12 L14.5 14.5 L12 23 L9.5 14.5 L1 12 L9.5 9.5 Z" /></svg>
);
const Pluma = () => (
  <svg viewBox="0 0 24 24"><path fill="currentColor" d="M20 3C11 3 5 9 5 17c0 1 .1 2 .3 3l1.6-1.6C7 15 9 12 13 10c-3 3-5 6-5.5 9.5.8.3 1.6.5 2.5.5 8 0 10-8 10-17z" /></svg>
);

// Botón "Aplicar filtros" con una ráfaga de estrellitas y plumas al pulsarlo.
export default function BotonAplicar({ onClick, clase = 'primario', direccion = 'arriba', children }) {
  const [piezas, setPiezas] = useState([]);
  const contador = useRef(0);
  const temporizador = useRef(null);
  useEffect(() => () => clearTimeout(temporizador.current), []);

  const alPulsar = (e) => {
    onClick?.(e);
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    contador.current += 1;
    setPiezas(crearRafaga(contador.current, direccion === 'abajo' ? 1 : -1));
    clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => setPiezas([]), 1600);
  };

  return (
    <div className={`boton-aplicar ${clase}`}>
        <button className={clase} onClick={alPulsar}>{children}</button>
    <span className={`chispas ${direccion}`} aria-hidden="true">
        {piezas.map((p) => (
          <span
            key={p.k}
            className={`chispa ${p.tipo}`}
            style={{
              left: `${p.x}%`, width: p.s, height: p.s,
              '--dx': `${p.dx}px`, '--dy': `${p.dy}px`, '--rot': `${p.rot}deg`,
              animationDuration: `${p.t}s`, animationDelay: `${p.d}s`,
            }}
          >
            {p.tipo === 'estrella' ? <Estrella /> : <Pluma />}
          </span>
        ))}
      </span>
    </div>
  );
}