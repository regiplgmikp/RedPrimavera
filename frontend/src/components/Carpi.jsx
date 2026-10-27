import React from 'react';
import { CarpiMascota } from './CarpiPersonaje.jsx';

// Traduce las poses que usa la app a las expresiones del personaje.
const POSES = {
  hola: { expresion: 'Feliz', vista: 'frente' },
  hablando: { expresion: 'Hablando', vista: 'frente' },
  senalando: { expresion: 'Señalando', vista: 'frente' },
  presentando: { expresion: 'Presentando', vista: 'frente' },
  curiosa: { expresion: 'Curiosa', vista: 'frente' },
  sorprendida: { expresion: 'Sorprendida', vista: 'frente' },
  cargando: { expresion: 'Cargando', vista: 'frente' },
  dormida: { expresion: 'Dormida', vista: 'frente' },
  perfil: { expresion: 'Sonriendo', vista: 'perfil' },
};

// Mascota del proyecto. Mantiene la misma forma de uso: <Carpi pose="hola" tamano={120} />
export default function Carpi({ pose = 'hola', tamano = 120 }) {
  const { expresion, vista } = POSES[pose] || POSES.hola;
  return <CarpiMascota expresion={expresion} vista={vista} tamano={tamano} />;
}