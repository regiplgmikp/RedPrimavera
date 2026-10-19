import { API } from './config.js';

export class ErrorApi extends Error {}

function consulta(obj) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) if (v !== '' && v != null) p.set(k, String(v));
  return p.toString();
}

async function pedir(ruta, parametros, signal) {
  let r;
  try {
    r = await fetch(`${API}${ruta}?${consulta(parametros)}`, { signal });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ErrorApi(`No se pudo conectar con la API en ${API}. ¿Está corriendo uvicorn? ¿${location.origin} está en CORS_ORIGINS del .env?`);
  }
  if (!r.ok) {
    let detalle = '';
    try { detalle = (await r.json()).detail; } catch { /* sin cuerpo JSON */ }
    throw new ErrorApi(`${r.status} ${typeof detalle === 'string' ? detalle : r.statusText}`);
  }
  return r.json();
}

// filtros: { resolucion, ivc_min, ivc_max, frecuencia_min, distancia_camino_max, en_predio, bbox }
export const getCeldas = (filtros, signal) => pedir('/subgrafos/celdas', filtros, signal);
export const getEspecies = (filtros, extra, signal) => pedir('/subgrafos/especies', { ...filtros, ...extra }, signal);
export const getPoblacion = (signal) => pedir('/capas/poblacion', {}, signal);
export const getObservaciones = (nombre, resolucion, zona, signal) => pedir('/subgrafos/especies/observaciones', { nombre, resolucion, zona }, signal);
export const getEspeciesDeCelda = (h3_id, zona, signal) => pedir('/subgrafos/celdas/especies', { h3_id, zona }, signal);
export const buscarEspecies = (q, signal) => pedir('/subgrafos/especies/buscar', { q, limite: 8 }, signal);