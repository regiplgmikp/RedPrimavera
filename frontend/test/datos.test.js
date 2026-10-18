import test from 'node:test';
import assert from 'node:assert/strict';
import { grafoEspecies, grafoCeldas, datosSobreposicion, tamanoPorCentralidad } from '../src/graphData.js';
import { colorCelda, poligonoDeCelda, radioPoblacion, rangoDe, limitesDeCeldas, htmlCelda, bboxTexto } from '../src/mapData.js';
import { colorTaxon, hexARgb, rampa, RIESGO } from '../src/colors.js';

const esp = {
  nodos: [
    { id: 'Quercus A', nombre_comun: 'encino', reino_iconico: 'Plantae', tipo: 'flora', lat: 20.6, lon: -103.5, n_celdas: 5, metricas: { grado: 3, fuerza: 9, intermediacion: 0.4, intermediacion_norm: 1, fuerza_norm: 0.5, centralidad_grado: 0.2, comunidad: 0 } },
    { id: 'Aves B', nombre_comun: null, reino_iconico: 'Aves', tipo: 'fauna', lat: null, lon: null, n_celdas: 0, metricas: { grado: 0, fuerza: 0, intermediacion: 0, intermediacion_norm: 0, fuerza_norm: 0, centralidad_grado: 0, comunidad: null } },
    { id: 'Rara C', nombre_comun: null, reino_iconico: 'Xyz', tipo: 'fauna', lat: 20.7, lon: -103.6, n_celdas: 1, metricas: { grado: 1, fuerza: 2, intermediacion: 0.1, intermediacion_norm: 0.25, fuerza_norm: 1, centralidad_grado: 0.1, comunidad: 1 } },
  ],
  aristas: [{ source: 'Quercus A', target: 'Rara C', peso: 4 }],
};

test('tamaño por centralidad: monótono, acotado y con raíz', () => {
  assert.equal(tamanoPorCentralidad(0), 3);
  assert.equal(tamanoPorCentralidad(1), 22);
  assert.ok(tamanoPorCentralidad(0.25) > (3 + 19 * 0.25), 'la raíz levanta los valores bajos');
  assert.equal(tamanoPorCentralidad(NaN), 3);
  assert.equal(tamanoPorCentralidad(5), 22);
});

test('grafo de especies: color por taxonomía y por comunidad', () => {
  const t = grafoEspecies(esp, { colorPor: 'taxonomia' });
  assert.equal(t.nodos[0].color, colorTaxon('Plantae'));
  assert.equal(t.nodos[2].color, '#999999', 'taxón desconocido -> gris');
  assert.equal(t.nodos[0].label, 'Quercus A (encino)');
  assert.ok(t.leyenda.some((l) => l.label === 'Plantae'));
  const c = grafoEspecies(esp, { colorPor: 'comunidad' });
  assert.equal(c.nodos[1].grupo, 'sin comunidad');
  assert.notEqual(c.nodos[0].color, c.nodos[2].color);
  assert.equal(c.aristas[0].size, 3, 'la arista de mayor peso tiene el grosor máximo');
});

test('tamaño por otra métrica', () => {
  const g = grafoEspecies(esp, { tamanoPor: 'fuerza_norm' });
  assert.ok(g.nodos[2].size > g.nodos[0].size);
});

const celda = (id, lat, lon, extra = {}) => ({
  h3_id: id, boundary: [[lat + 0.01, lon], [lat, lon + 0.01], [lat - 0.01, lon], [lat, lon - 0.01]],
  ivc: 0.5, exposicion: 0.5, sensibilidad: 0.5, frecuencia_incendios: 0.04, periodo_retorno: 25, distancia_camino: 120, en_predio: false,
  n_observaciones: 3, n_especies: 2, poblacion: null, instituciones: [],
  metricas: { grado: 2, intermediacion: 0.2, intermediacion_norm: 0.5, cercania_norm: 0.4, es_articulacion: false, componente: 0, componente_tamano: 3 }, ...extra,
});
const cel = {
  nodos: [celda('a', 20.6, -103.5, { instituciones: ['ITESO'] }), celda('b', 20.62, -103.5, { instituciones: ['UdeG', 'ITESO'] }), celda('c', 20.64, -103.5, { ivc: null })],
  aristas: [{ source: 'a', target: 'b' }, { source: 'b', target: 'c' }],
};

test('grafo de celdas: color por institución con leyenda estable', () => {
  const g = grafoCeldas(cel, { colorPor: 'institucion' });
  assert.equal(g.nodos.find((n) => n.id === 'c').grupo, 'sin institución');
  assert.equal(g.nodos.find((n) => n.id === 'a').grupo, 'ITESO');
  assert.equal(g.nodos.find((n) => n.id === 'b').grupo, 'UdeG', 'toma la primera institución del predio');
  assert.deepEqual(g.leyenda.map((l) => l.label), ['ITESO', 'UdeG', 'sin institución']);
  const porIvc = grafoCeldas(cel, { colorPor: 'ivc' });
  assert.equal(porIvc.nodos.find((n) => n.id === 'c').color, '#c9cdca', 'sin IVC -> gris de sin dato');
});

test('sobreposición: omite nodos sin coordenadas y devuelve [lon, lat]', () => {
  const g = grafoEspecies(esp);
  const o = datosSobreposicion(g);
  assert.equal(o.omitidos, 1);
  assert.equal(o.puntos.length, 2);
  assert.deepEqual(o.puntos[0].position, [-103.5, 20.6]);
  assert.equal(o.lineas.length, 1);
  assert.deepEqual(o.lineas[0].to, [-103.6, 20.7]);
  assert.ok(o.puntos[0].radio > o.puntos[1].radio);
});

test('mapa: polígono en [lon, lat], color de celdas sin dato y límites', () => {
  const v0 = poligonoDeCelda(cel.nodos[0])[0];
  assert.equal(v0[0], -103.5);
  assert.ok(Math.abs(v0[1] - 20.61) < 1e-9, 'segundo valor = latitud');
  const r = rangoDe(cel.nodos, 'ivc');
  assert.deepEqual(r, [0.5, 0.5]);
  assert.deepEqual(colorCelda(cel.nodos[2], 'ivc', r), hexARgb('#c9cdca', 215));
  assert.deepEqual(colorCelda(cel.nodos[0], 'ivc', r).length, 4);
  const [[w, s], [e, n]] = limitesDeCeldas(cel.nodos);
  assert.ok(w < e && s < n);
  assert.equal(limitesDeCeldas([]), null);
});

test('población: área proporcional y acotada', () => {
  assert.equal(radioPoblacion(0, 100), 0);
  assert.equal(radioPoblacion(100, 100), 280);
  assert.ok(Math.abs(radioPoblacion(25, 100) - 140) < 1e-9, 'un cuarto de población = la mitad del radio');
  assert.equal(radioPoblacion(null, 100), 0);
});

test('tooltip escapa HTML y bbox usa 4 decimales', () => {
  const h = htmlCelda(celda('x<img>', 20, -103, { instituciones: ['<script>alert(1)</script>'] }));
  assert.ok(!h.includes('<script>') && !h.includes('<img>'));
  assert.equal(bboxTexto([-103.123456, 20.1, -103, 20.2]), '-103.1235,20.1000,-103.0000,20.2000');
  assert.equal(rampa(RIESGO, 1), RIESGO[RIESGO.length - 1]);
});
