import React, { useEffect, useRef } from 'react';
import Carpi from './Carpi.jsx';

export default function Bienvenida({ onCerrar, onRecorrido }) {
  const botonRef = useRef(null);
  const cerrarRef = useRef(onCerrar);
  cerrarRef.current = onCerrar;

  useEffect(() => {
    botonRef.current?.focus();
    const alTeclear = (e) => { if (e.key === 'Escape') cerrarRef.current(); };
    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, []);

  return (
    <div className="bienvenida-fondo" onClick={onCerrar}>
      <section
        className="bienvenida" role="dialog" aria-modal="true" aria-labelledby="bienvenida-titulo"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bienvenida-cabeza">
          <Carpi pose="hola" tamano={110} />
          <div>
            <h2 id="bienvenida-titulo">¡Hola! Soy Carpi</h2>
            <p>
              Te acompaño a explorar el Bosque La Primavera: qué zonas están más expuestas
              a los incendios y qué especies viven en ellas.
            </p>
          </div>
        </div>

        <div className="bienvenida-bloques">
          <div>
            <h3>Qué ves</h3>
            <p>
              El bosque está dividido en hexágonos. Cada color cuenta algo distinto de esa zona:
              qué tan vulnerable es a los incendios, qué tan verde está o cuántas observaciones hay.
            </p>
          </div>
          <div>
            <h3>Qué puedes hacer</h3>
            <p>
              Filtrar zonas, buscar una especie por su nombre y ver dónde se ha visto, o tocar
              un hexágono para saber qué especies tiene.
            </p>
          </div>
          <div>
            <h3>De dónde vienen los datos</h3>
            <p>
              Las observaciones las aportan personas como tú en eBird e iNaturalist. La vegetación
              y los incendios vienen de imágenes de satélite.
            </p>
          </div>
        </div>

        <p className="bienvenida-nota">
          Ojo: el índice de vulnerabilidad es una estimación para comparar zonas entre sí,
          no un pronóstico de incendios.
        </p>

        <div className="bienvenida-acciones">
          <button ref={botonRef} className="secundario" onClick={onCerrar}>Cerrar</button>
          {onRecorrido && (
            <button className="primario" onClick={onRecorrido}>Hacer el recorrido</button>
          )}
        </div>
        <p className="bienvenida-pie">Proyecto de aplicación profesional del ITESO.</p>
      </section>
    </div>
  );
}