// Paletas. Categórica: Okabe-Ito (distinguible con daltonismo). Secuencial de riesgo: claro = bajo.
export const RIESGO = ['#fff7bc', '#fee391', '#fec44f', '#fe9929', '#ec7014', '#cc4c02', '#993404', '#662506'];
export const VIRIDIS = ['#440154', '#482878', '#3e4989', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6ece58', '#b5de2b', '#fde725'];
export const CATEGORICA = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#D55E00', '#56B4E9', '#F0E442', '#7B3294'];
export const SIN_DATO = '#c9cdca';
export const GRIS = '#999999';

// Taxón icónico de iNaturalist -> color fijo, para que "Aves" sea siempre del mismo color
export const TAXONOMIA = {
  Plantae: '#009E73',
  Aves: '#0072B2',
  Insecta: '#E69F00',
  Mammalia: '#D55E00',
  Reptilia: '#CC79A7',
  Amphibia: '#56B4E9',
  Arachnida: '#7B3294',
  Fungi: '#8c6d31',
  Mollusca: '#5e6b75',
};

export function rampa(paleta, t) {
  const x = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0));
  return paleta[Math.min(paleta.length - 1, Math.floor(x * paleta.length))];
}

export function hexARgb(hex, alpha = 255) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, alpha];
}

export function colorCategorico(i) {
  return CATEGORICA[((i % CATEGORICA.length) + CATEGORICA.length) % CATEGORICA.length];
}

export function colorTaxon(reino) {
  return TAXONOMIA[reino] || GRIS;
}
