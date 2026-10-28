import React from 'react';
import Carpi from './Carpi.jsx';

// Carpi con el circulito girando, más un texto corto. Se usa mientras llegan los datos.
export default function Cargando({ texto = 'Cargando…', tamano = 96 }) {
  return (
    <div className="cargando">
      <Carpi pose="cargando" tamano={tamano} />
      <span>{texto}</span>
    </div>
  );
}