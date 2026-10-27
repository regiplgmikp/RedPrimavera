import React from 'react';

// Logo de RedPrimavera (cabeza de carpintero). Usa logo-carpi.png como máscara:
// la forma viene del PNG y el color de la paleta, así cambia solo entre claro y oscuro.
export default function Logo({ tamano = 64, color = 'var(--accent)' }) {
  const url = `${import.meta.env.BASE_URL}logo-carpi.png`;
  return (
    <span
      role="img"
      aria-label="Logo de RedPrimavera"
      style={{
        display: 'inline-block',
        flex: 'none',
        width: tamano,
        height: Math.round((tamano * 421) / 512),
        background: color,
        WebkitMaskImage: `url(${url})`,
        maskImage: `url(${url})`,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
      }}
    />
  );
}