import React, { useEffect, useState } from 'react';
import { buscarEspecies } from '../api.js';

const VACIO = { lista: [], total: 0, cargando: false, error: null };

export default function BuscadorEspecies({ seleccionada, aviso, onElegir, onQuitar }) {
  const [texto, setTexto] = useState('');
  const [res, setRes] = useState(VACIO);
  const [abierto, setAbierto] = useState(false);

  // Busca 250 ms después de la última tecla y cancela la búsqueda anterior
  useEffect(() => {
    const q = texto.trim();
    if (q.length < 2) { setRes(VACIO); return undefined; }
    const ctl = new AbortController();
    const espera = setTimeout(() => {
      setRes((p) => ({ ...p, cargando: true, error: null }));
      buscarEspecies(q, ctl.signal)
        .then((d) => setRes({ lista: d.resultados, total: d.total, cargando: false, error: null }))
        .catch((e) => { if (e?.name !== 'AbortError') setRes({ ...VACIO, error: e.message }); });
    }, 250);
    return () => { clearTimeout(espera); ctl.abort(); };
  }, [texto]);

  const elegir = (especie) => { onElegir(especie.id); setTexto(''); setAbierto(false); };
  const mostrar = abierto && texto.trim().length >= 2;

  return (
    <div className="buscador">
      <label htmlFor="buscar-especie">Buscar especie (nombre común o científico)</label>
      <input id="buscar-especie" type="search" autoComplete="off" placeholder="p. ej. carpintero, mosquero…"
        value={texto} onChange={(e) => { setTexto(e.target.value); setAbierto(true); }} onFocus={() => setAbierto(true)} />
      {mostrar && (
        <ul className="sugerencias">
          {res.cargando && <li className="info">Buscando…</li>}
          {res.error && <li className="info">{res.error}</li>}
          {!res.cargando && !res.error && res.lista.length === 0 && <li className="info">Sin coincidencias</li>}
          {res.lista.map((e) => (
            <li key={e.id}>
              <button type="button" onClick={() => elegir(e)}>
                <b>{e.nombre_comun || e.id}</b>{e.nombre_comun && <i> {e.id}</i>}
                <span> · {e.n_observaciones.toLocaleString('es-MX')} obs.</span>
              </button>
            </li>
          ))}
          {!res.cargando && res.total > res.lista.length && <li className="info">…y {res.total - res.lista.length} más: escribe más letras</li>}
        </ul>
      )}
      {seleccionada && (
        <div className="seleccion-especie">
          <span>{seleccionada.etiqueta}</span>
          <button type="button" onClick={onQuitar} aria-label="Quitar especie seleccionada">×</button>
          {aviso && <p className="aviso">{aviso}</p>}
        </div>
      )}
    </div>
  );
}