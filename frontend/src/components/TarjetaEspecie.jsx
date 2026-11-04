import { useEffect, useState } from 'react';
import { infoEspecie } from '../inaturalist.js';

// Tarjeta con foto y datos de la especie elegida en el grafo (datos de iNaturalist).
export default function TarjetaEspecie({ nombre, comunLocal, onCerrar }) {
  const [estado, setEstado] = useState({ cargando: true, info: null, error: false });

  useEffect(() => {
    const ctl = new AbortController();
    setEstado({ cargando: true, info: null, error: false });
    infoEspecie(nombre, ctl.signal)
      .then((info) => setEstado({ cargando: false, info, error: false }))
      .catch((e) => { if (e.name !== 'AbortError') setEstado({ cargando: false, info: null, error: true }); });
    return () => ctl.abort();
  }, [nombre]);

  const { cargando, info, error } = estado;
  return (
    <div className="tarjeta-especie" role="complementary" aria-live="polite">
      <button type="button" className="tarjeta-cerrar" onClick={onCerrar} aria-label="Cerrar tarjeta">×</button>
      {info?.foto && <img src={info.foto} alt={info.comun || nombre} loading="lazy" />}
      <div className="tarjeta-texto">
        <h4>{info?.comun || comunLocal || nombre}</h4>
        <p className="tarjeta-cientifico"><i>{nombre}</i></p>
        {cargando && <p className="tarjeta-nota">Buscando información…</p>}
        {error && <p className="tarjeta-nota">No pude conectar con iNaturalist en este momento.</p>}
        {!cargando && !error && !info && <p className="tarjeta-nota">No encontré esta especie en iNaturalist.</p>}
        {info?.estado && <p><b>Conservación:</b> {info.estado}</p>}
        {info?.observaciones != null && <p>{info.observaciones.toLocaleString('es-MX')} observaciones en iNaturalist</p>}
        {info?.resumen && <p className="tarjeta-resumen">{info.resumen}</p>}
        {info && <a href={info.enlace} target="_blank" rel="noreferrer">Ver en iNaturalist ↗</a>}
        {info?.credito && <small>Foto: {info.credito}</small>}
      </div>
    </div>
  );
}