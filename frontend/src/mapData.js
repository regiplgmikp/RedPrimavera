// Utilidades del mapa (puras)
import { RIESGO, VIRIDIS, SIN_DATO, hexARgb, rampa, colorCategorico } from './colors.js';

// La API devuelve [lat, lon]; Deck.gl espera [lon, lat]
export function poligonoDeCelda(celda) {
  return celda.boundary.map(([lat, lon]) => [lon, lat]);
}

export const CAMPOS_COLOR = {
  ivc: { etiqueta: 'Índice de vulnerabilidad (IVC)', paleta: RIESGO, valor: (c) => c.ivc },
  frecuencia_incendios: { etiqueta: 'Frecuencia de incendios (por año)', paleta: RIESGO, valor: (c) => c.frecuencia_incendios },
  intermediacion_norm: { etiqueta: 'Intermediación (cuello de botella)', paleta: VIRIDIS, valor: (c) => c.metricas.intermediacion_norm },
  cercania_norm: { etiqueta: 'Cercanía (centralidad)', paleta: VIRIDIS, valor: (c) => c.metricas.cercania_norm },
  n_observaciones: { etiqueta: 'Número de observaciones', paleta: VIRIDIS, valor: (c) => c.n_observaciones, escala: 'log', cero_sin_dato: true },
  componente: { etiqueta: 'Bloque conectado', categorico: true, valor: (c) => c.metricas.componente },
  ndvi: { etiqueta: 'NDVI medio (vigor de la vegetación)', paleta: VIRIDIS, valor: (c) => c.ndvi },
  dosel: { etiqueta: 'Altura media del dosel (m)', paleta: VIRIDIS, valor: (c) => c.dosel },
};

export function rangoDe(celdas, campo) {
  const def = CAMPOS_COLOR[campo];
  const v = celdas.map(def.valor).filter((x) => x != null && Number.isFinite(x));
  return v.length ? [Math.min(...v), Math.max(...v)] : [0, 1];
}

// Devuelve [r,g,b,a]; las celdas sin dato (p. ej. sin IVC por vegetación insuficiente) van en gris
export function colorCelda(celda, campo, [lo, hi], alpha = 215) {
  const def = CAMPOS_COLOR[campo];
  const v = def.valor(celda);
  if (v == null || !Number.isFinite(v) || (def.cero_sin_dato && v === 0)) return hexARgb(SIN_DATO, alpha);
  if (def.escala === 'log') return hexARgb(rampa(def.paleta, hi <= 0 ? 0 : Math.log1p(v) / Math.log1p(hi)), alpha);
  return hexARgb(rampa(def.paleta, hi === lo ? 0.5 : (v - lo) / (hi - lo)), alpha);
}

export function limitesDeCeldas(celdas) {
  let w = 180, s = 90, e = -180, n = -90;
  for (const c of celdas) for (const [lat, lon] of c.boundary) { w = Math.min(w, lon); e = Math.max(e, lon); s = Math.min(s, lat); n = Math.max(n, lat); }
  return celdas.length ? [[w, s], [e, n]] : null;
}

// Círculos proporcionales para la capa demográfica: el ÁREA del círculo es proporcional a la
// población (radio ~ raíz), y se limita al radio de una celda de resolución 8 (~ 300 m).
export function radioPoblacion(pob, max, radioMax = 280) {
  if (!pob || pob <= 0 || !max) return 0;
  return radioMax * Math.sqrt(pob / max);
}

export function centroPoligono(poligono) {
  return [poligono.reduce((s, p) => s + p[0], 0) / poligono.length, poligono.reduce((s, p) => s + p[1], 0) / poligono.length];
}

export function bboxTexto([w, s, e, n]) {
  return [w, s, e, n].map((x) => x.toFixed(4)).join(',');
}

const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const f = (v, d = 3) => (v == null ? '—' : Number.isInteger(v) ? String(v) : v.toFixed(d));

export function htmlCelda(c) {
  const m = c.metricas;
  return `<b>${esc(c.h3_id)}</b><br>IVC: ${f(c.ivc)} (E ${f(c.exposicion)} · S ${f(c.sensibilidad)})`
    + `<br>Incendios/año: ${f(c.frecuencia_incendios)} · retorno: ${c.periodo_retorno == null ? '—' : Math.round(c.periodo_retorno) + ' años'}`
    + `<br>NDVI: ${f(c.ndvi)} · dosel: ${c.dosel == null ? '—' : f(c.dosel) + ' m'}`
    + `<br>Camino: ${c.distancia_camino == null ? '—' : Math.round(c.distancia_camino) + ' m'} · ${c.en_predio ? 'en predio' : 'sin predio'}`
    + `<br>Observaciones: ${c.n_observaciones} · especies: ${c.n_especies}`
    + (c.poblacion != null ? `<br>Población estimada: ${Math.round(c.poblacion).toLocaleString('es-MX')}` : '')
    + `<br>Vecinos: ${m.grado} · intermediación: ${f(m.intermediacion)} · bloque ${m.componente + 1}`
    + (m.es_articulacion ? '<br><b>Punto de articulación</b>' : '')
    + ((c.instituciones || []).length ? `<br>Instituciones: ${c.instituciones.map(esc).join(', ')}` : '');
}
