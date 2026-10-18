import React from 'react';
import { RIESGO, SIN_DATO, VIRIDIS } from '../colors.js';

const f = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(2));

export default function Leyenda({ modo, campo, def, rango, poblacion, sobreponer, leyenda, observaciones }) {
  if (modo === 'grafo') {
    return (
      <div className="leyenda">
        <b>Color de los nodos · tamaño: centralidad</b>
        <ul>{leyenda.map((l) => (<li key={l.label}><span className="sw" style={{ background: l.color }} />{l.label}</li>))}</ul>
      </div>
    );
  }
  const paleta = def?.paleta || (campo === 'ivc' ? RIESGO : VIRIDIS);
  return (
    <div className="leyenda">
      <b>{def?.etiqueta}</b>
      {def?.categorico
        ? <div>Cada color es un bloque conectado de celdas</div>
        : (<><div className="barra" style={{ background: `linear-gradient(90deg, ${paleta.join(',')})` }} />
            <div className="ticks"><span>{f(rango[0])}</span><span>{f(rango[1])}</span></div></>)}
      <div><span className="sw" style={{ background: SIN_DATO }} />sin dato / no evaluable</div>
      {poblacion?.datos && <div><span className="sw circ" />población estimada (área ∝ habitantes)</div>}
      {observaciones?.id && (
        <div><span className="sw" style={{ background: 'rgb(0,200,255)' }} />
          {observaciones.cargando ? 'Buscando observaciones…'
            : observaciones.error ? `Error: ${observaciones.error}`
            : <><i>{observaciones.id}</i>: {observaciones.datos.n_observaciones} obs. en {observaciones.datos.celdas.length} celdas</>}
        </div>)}
      {sobreponer && <div>Grafo sobrepuesto: puntos = nodos, líneas = vínculos</div>}
    </div>
  );
}
