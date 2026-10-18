// Conversión de las respuestas JSON del backend a la estructura que consumen Sigma
// (nodos/aristas con tamaño y color) y Deck.gl (puntos/líneas con coordenadas).
// Todo es puro: no importa React ni librerías, así que se prueba con `npm test`.
import { CATEGORICA, GRIS, RIESGO, SIN_DATO, TAXONOMIA, colorCategorico, colorTaxon, rampa } from './colors.js';

const TAM_MIN = 3;
const TAM_MAX = 22;

// El tamaño crece con la raíz de la centralidad normalizada: sin la raíz, unos pocos nodos
// enormes y todos los demás invisibles (la intermediación está muy sesgada).
export function tamanoPorCentralidad(norm, min = TAM_MIN, max = TAM_MAX) {
  const t = Math.max(0, Math.min(1, Number.isFinite(norm) ? norm : 0));
  return min + (max - min) * Math.sqrt(t);
}

// Con muchos nodos los círculos grandes se encapsulan y el grafo se vuelve una mancha:
// el tamaño máximo baja con la raíz del número de nodos (y sube hasta TAM_MAX con pocos).
export function tamanoMaximo(n) {
  return Math.max(5, Math.min(TAM_MAX, 130 / Math.sqrt(Math.max(n, 1))));
}
const TAM_BAJO = 1.5;

function centroideCelda(n) {
  const b = n.boundary;
  return [b.reduce((s, p) => s + p[0], 0) / b.length, b.reduce((s, p) => s + p[1], 0) / b.length]; // [lat, lon]
}

const TAMANO_ESPECIE = { intermediacion_norm: 'intermediacion_norm', fuerza_norm: 'fuerza_norm', grado: 'centralidad_grado' };

export function grafoEspecies(data, { colorPor = 'taxonomia', tamanoPor = 'intermediacion_norm' } = {}) {
  const campo = TAMANO_ESPECIE[tamanoPor] || 'intermediacion_norm';
  const tmax = tamanoMaximo((data?.nodos || []).length);
  const nodos = (data?.nodos || []).map((n) => {
    const m = n.metricas;
    const color = colorPor === 'comunidad'
      ? (m.comunidad == null ? GRIS : colorCategorico(m.comunidad))
      : colorTaxon(n.reino_iconico);
    return {
      id: n.id,
      label: n.nombre_comun ? `${n.id} (${n.nombre_comun})` : n.id,
      size: tamanoPorCentralidad(m[campo], TAM_BAJO, tmax),
      norm: m[campo],
      color,
      lat: n.lat ?? null,
      lon: n.lon ?? null,
      grupo: colorPor === 'comunidad' ? (m.comunidad == null ? 'sin comunidad' : `comunidad ${m.comunidad + 1}`) : (n.reino_iconico || 'sin clasificar'),
      detalle: { grado: m.grado, fuerza: m.fuerza, intermediacion: m.intermediacion, comunidad: m.comunidad, celdas: n.n_celdas, tipo: n.tipo },
    };
  });
  const maxPeso = Math.max(1, ...(data?.aristas || []).map((a) => a.peso));
  const aristas = (data?.aristas || []).map((a) => ({
    id: `${a.source}||${a.target}`, source: a.source, target: a.target,
    size: 0.3 + 1.2 * (a.peso / maxPeso), peso: a.peso,
  }));
  return { tipo: 'especies', colorPor, nodos, aristas, leyenda: leyendaEspecies(nodos, colorPor), titulo: 'Co-ocurrencia de especies' };
}

// Recorta la red de especies a las que viven en una celda: se queda con esos nodos y con las
// aristas que los unen entre sí. Los tamaños se recalculan para que se vean con pocos nodos
// (la centralidad sigue siendo la de la red completa). `omitidas` cuenta especies de la celda
// que no están en la red (por ejemplo, filtradas por la zona).
export function subgrafoDeEspecies(grafo, ids) {
  const quedan = new Set(ids);
  const nodos = grafo.nodos.filter((n) => quedan.has(n.id));
  const presentes = new Set(nodos.map((n) => n.id));
  const tmax = tamanoMaximo(nodos.length);
  return {
    ...grafo,
    titulo: 'Especies de la celda',
    nodos: nodos.map((n) => ({ ...n, size: tamanoPorCentralidad(n.norm, TAM_BAJO, tmax) })),
    aristas: grafo.aristas.filter((e) => presentes.has(e.source) && presentes.has(e.target)),
    leyenda: leyendaEspecies(nodos, grafo.colorPor),
    omitidas: quedan.size - presentes.size,
  };
}

function leyendaEspecies(nodos, colorPor) {
  const vistos = new Map();
  for (const n of nodos) if (!vistos.has(n.grupo)) vistos.set(n.grupo, n.color);
  const items = [...vistos].map(([label, color]) => ({ label, color }));
  return colorPor === 'comunidad' ? items.sort((a, b) => a.label.localeCompare(b.label, 'es', { numeric: true })) : items;
}

// Grafo de celdas: nodos = celdas H3 filtradas, aristas = adyacencia. Se colorea por la
// institución dueña del predio (primera si hay varias), por IVC o por bloque conectado.
export function grafoCeldas(data, { colorPor = 'institucion', tamanoPor = 'intermediacion_norm' } = {}) {
  const celdas = data?.nodos || [];
  const frecuencia = new Map();
  for (const c of celdas) for (const i of c.instituciones || []) frecuencia.set(i, (frecuencia.get(i) || 0) + 1);
  const instituciones = [...frecuencia].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'es')).map(([n]) => n);
  const colorInst = (n) => colorCategorico(instituciones.indexOf(n));
  const MAX_VISIBLES = CATEGORICA.length - 1;

  const nodos = celdas.map((c) => {
    const [lat, lon] = centroideCelda(c);
    const m = c.metricas;
    let color = SIN_DATO, grupo = 'sin dato';
    if (colorPor === 'institucion') {
      const inst = (c.instituciones || [])[0];
      const idx = inst ? instituciones.indexOf(inst) : -1;
      if (inst) { color = idx < MAX_VISIBLES ? colorInst(inst) : GRIS; grupo = idx < MAX_VISIBLES ? inst : 'otras instituciones'; }
      else { color = SIN_DATO; grupo = 'sin institución'; }
    } else if (colorPor === 'ivc') {
      if (c.ivc != null) { color = rampa(RIESGO, c.ivc); grupo = 'IVC'; }
    } else {
      color = m.componente < MAX_VISIBLES ? colorCategorico(m.componente) : GRIS;
      grupo = `bloque ${m.componente + 1}`;
    }
    return {
      id: c.h3_id, label: c.h3_id, size: tamanoPorCentralidad(m[tamanoPor] ?? m.intermediacion_norm, TAM_BAJO, tamanoMaximo(celdas.length)),
      color, lat, lon, grupo,
      detalle: { ivc: c.ivc, grado: m.grado, intermediacion: m.intermediacion, instituciones: c.instituciones || [], componente: m.componente },
    };
  });
  const aristas = (data?.aristas || []).map((a) => ({ id: `${a.source}||${a.target}`, source: a.source, target: a.target, size: 0.8, peso: 1 }));

  let leyenda;
  if (colorPor === 'institucion') {
    leyenda = instituciones.slice(0, MAX_VISIBLES).map((n) => ({ label: n, color: colorInst(n) }));
    if (instituciones.length > MAX_VISIBLES) leyenda.push({ label: 'otras instituciones', color: GRIS });
    leyenda.push({ label: 'sin institución', color: SIN_DATO });
  } else if (colorPor === 'ivc') {
    leyenda = [{ label: 'IVC bajo', color: RIESGO[0] }, { label: 'IVC alto', color: RIESGO[RIESGO.length - 1] }, { label: 'sin dato', color: SIN_DATO }];
  } else {
    leyenda = [...new Set(nodos.map((n) => n.grupo))].slice(0, MAX_VISIBLES + 1).map((g) => ({ label: g, color: nodos.find((n) => n.grupo === g).color }));
  }
  return { tipo: 'celdas', nodos, aristas, leyenda, titulo: 'Adyacencia de celdas' };
}

// Datos para sobreponer el grafo al mapa con capas de Deck.gl. Los nodos sin coordenadas
// (especies sin celdas en el filtro) se omiten y se cuentan para avisar al usuario.
export function datosSobreposicion(grafo, { radioMin = 60, radioMax = 420 } = {}) {
  const conPos = grafo.nodos.filter((n) => n.lat != null && n.lon != null);
  const pos = new Map(conPos.map((n) => [n.id, [n.lon, n.lat]]));
  const minSize = Math.min(...conPos.map((n) => n.size));
  const maxSize = Math.max(minSize, ...conPos.map((n) => n.size));
  const puntos = conPos.map((n) => ({
    id: n.id, position: pos.get(n.id), color: n.color, label: n.label,
    radio: radioMin + (radioMax - radioMin) * ((n.size - minSize) / ((maxSize - minSize) || 1)),
  }));
  const lineas = grafo.aristas
    .filter((e) => pos.has(e.source) && pos.has(e.target))
    .map((e) => ({ id: e.id, source: e.source, target: e.target, from: pos.get(e.source), to: pos.get(e.target), ancho: e.size }));
  return { puntos, lineas, omitidos: grafo.nodos.length - conPos.length };
}

export { TAXONOMIA };