import React, { useState } from 'react';

// Mascota del proyecto. Busca la imagen en frontend/public/carpi-<pose>.png.
// Si todavía no existe, muestra un hexágono de reemplazo para no dejar un hueco.
export default function Carpi({ pose = 'hola', tamano = 120 }) {
  const [falla, setFalla] = useState(false);

  if (falla) {
    return (
      <svg width={tamano} height={tamano} viewBox="0 0 120 120" role="img"
           aria-label="Carpi, la mascota del proyecto (imagen pendiente)">
        <polygon points="60,6 106,33 106,87 60,114 14,87 14,33"
                 fill="var(--panel)" stroke="var(--accent)" strokeWidth="4" strokeLinejoin="round" />
        <text x="60" y="70" textAnchor="middle" fontSize="30" fontWeight="700" fill="var(--accent)">RP</text>
      </svg>
    );
  }
  return (
    <img
      src={`${import.meta.env.BASE_URL}carpi-${pose}.png`}
      width={tamano} height={tamano}
      alt="Carpi, la mascota del proyecto"
      style={{ objectFit: 'contain' }}
      onError={() => setFalla(true)}
    />
  );
}