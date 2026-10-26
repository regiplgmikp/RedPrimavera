import React, { useEffect, useId, useState } from 'react';

// Botón "?" que muestra una nota explicativa en línea.
// Uso:  <label>Resolución H3 <Ayuda titulo="Resolución H3">Texto de ayuda…</Ayuda></label>
export default function Ayuda({ titulo, children }) {
  const [abierta, setAbierta] = useState(false);
  const id = useId();

  useEffect(() => {
    if (!abierta) return undefined;
    const alTeclear = (e) => { if (e.key === 'Escape') setAbierta(false); };
    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, [abierta]);

  return (
    <>
      <button
        type="button" className="ayuda-mini"
        aria-expanded={abierta} aria-controls={id} aria-label={`Ayuda: ${titulo}`}
        onClick={(e) => { e.preventDefault(); setAbierta((a) => !a); }}
      >?</button>
        {abierta && <span id={id} role="note" className="ayuda-nota" onClick={(e) => e.preventDefault()}>{children}</span>}
    </>
  );
}