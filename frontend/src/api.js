import { API } from './config.js';

export class ErrorApi extends Error {}

// Traduce las respuestas de error de la API a frases claras para quien usa el panel.
// El detalle técnico queda en la consola del navegador (F12) por si hace falta.
function mensajeHttp(estado, detalle, texto) {
  console.error('Error de la API:', estado, detalle ?? texto);
  if (estado === 422) {
    const campo = Array.isArray(detalle) ? detalle[0]?.loc?.slice(-1)[0] : null;
    return `Algún filtro tiene un valor fuera de rango${campo ? ` (${campo})` : ''}. Revisa los números e intenta de nuevo.`;
  }
  if (estado >= 500) {
    return 'No pude conectar con la base de datos. Si estuvo inactiva puede tardar un minuto en despertar; intenta de nuevo en un momento.';
  }
  return `${estado} ${typeof detalle === 'string' ? detalle : texto}`;
}

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
      console.error(`No se pudo conectar con la API en ${API}. ¿Está corriendo uvicorn? ¿${location.origin} está en CORS_ORIGINS del .env?`, e);
      throw new ErrorApi('No hay respuesta del servidor. Revisa tu conexión e intenta de nuevo en un momento.');
  }
  if (!r.ok) {
    let detalle = '';
    try { detalle = (await r.json()).detail; } catch { /* sin cuerpo JSON */ }
        throw new ErrorApi(mensajeHttp(r.status, detalle, r.statusText));
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