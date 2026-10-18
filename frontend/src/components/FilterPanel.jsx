import React from 'react';
import { CAMPOS_COLOR } from '../mapData.js';

function Campo({ id, etiqueta, children }) {
  return (<div className="campo"><label htmlFor={id}>{etiqueta}</label>{children}</div>);
}

export default function FilterPanel({ form, setForm, vista, cambiarVista, resolucionEfectiva, aplicar, limpiar, metaCeldas, metaEspecies, omitidos }) {
  const num = (id, props = {}) => (
    <input id={id} type="number" placeholder="sin filtro" value={form[id]} {...props}
      onChange={(e) => setForm({ ...form, [id]: e.target.value })}
      onKeyDown={(e) => e.key === 'Enter' && aplicar()} />
  );
  const sel = (id, opciones) => (
    <select id={id} value={form[id]} onChange={(e) => setForm({ ...form, [id]: e.target.value })}>
      {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
    </select>
  );
  const chk = (clave, texto, extra) => (
    <label className="check"><input type="checkbox" checked={vista[clave]} onChange={(e) => cambiarVista({ [clave]: e.target.checked })} /> {texto}{extra}</label>
  );
  const esEsp = vista.grafo === 'especies';

  return (
    <aside>
      <h2>Territorio</h2>
      <Campo id="resolucion" etiqueta="Resolución H3">
        <select id="resolucion" value={vista.autoRes ? resolucionEfectiva : vista.resolucion} disabled={vista.autoRes}
          onChange={(e) => cambiarVista({ resolucion: Number(e.target.value) })}>
          <option value={8}>8 (≈ 70–90 ha)</option><option value={9}>9 (≈ 10 ha)</option>
        </select>
      </Campo>
      <Campo id="ivc_min" etiqueta="IVC mínimo (0–1)">{num('ivc_min', { min: 0, max: 1, step: 0.05 })}</Campo>
      <Campo id="ivc_max" etiqueta="IVC máximo (0–1)">{num('ivc_max', { min: 0, max: 1, step: 0.05 })}</Campo>
      <Campo id="frecuencia_min" etiqueta="Frecuencia de incendios mínima (por año)">{num('frecuencia_min', { min: 0, max: 1, step: 0.02 })}</Campo>
      <Campo id="distancia_camino_max" etiqueta="Distancia máxima a camino (m)">{num('distancia_camino_max', { min: 0, step: 50 })}</Campo>
      <Campo id="en_predio" etiqueta="Predio de institución">
        {sel('en_predio', [['', 'Cualquiera'], ['true', 'Dentro de un predio'], ['false', 'Fuera de predios']])}
      </Campo>

      <h2>Red de especies</h2>
      <Campo id="zona" etiqueta="Zona de las observaciones">
        {sel('zona', [['', 'Todas'], ['nucleo', 'Núcleo'], ['zona_mab', 'Zona de transición'], ['fuera', 'Fuera de la poligonal']])}
      </Campo>
      <Campo id="min_celdas_compartidas" etiqueta="Celdas compartidas mínimas">{num('min_celdas_compartidas', { min: 1, max: 50 })}</Campo>

      <button className="primario" onClick={aplicar}>Aplicar filtros</button>
      <button className="secundario" onClick={limpiar}>Limpiar</button>

      <h2>Mapa</h2>
      <Campo id="colorMapa" etiqueta="Color de las celdas">
        <select id="colorMapa" value={vista.colorMapa} onChange={(e) => cambiarVista({ colorMapa: e.target.value })}>
          {Object.entries(CAMPOS_COLOR).map(([k, d]) => <option key={k} value={k}>{d.etiqueta}</option>)}
        </select>
      </Campo>
      {chk('verPoblacion', 'Capa demográfica (círculos)')}
      {chk('dinamico', 'Cargar solo lo visible (al mover el mapa)')}
      {chk('autoRes', 'Resolución automática según el zoom')}

      <h2>Grafo</h2>
      <Campo id="grafo" etiqueta="Qué grafo mostrar">
        <select id="grafo" value={vista.grafo} onChange={(e) => cambiarVista({ grafo: e.target.value })}>
          <option value="especies">Especies (co-ocurrencia)</option>
          <option value="celdas">Celdas (adyacencia)</option>
        </select>
      </Campo>
      <Campo id="colorGrafo" etiqueta="Color de los nodos">
        <select id="colorGrafo" value={vista.colorGrafo} onChange={(e) => cambiarVista({ colorGrafo: e.target.value })}>
          {esEsp
            ? [<option key="t" value="taxonomia">Taxonomía</option>, <option key="c" value="comunidad">Comunidad</option>]
            : [<option key="i" value="institucion">Institución</option>, <option key="v" value="ivc">IVC</option>, <option key="b" value="bloque">Bloque conectado</option>]}
        </select>
      </Campo>
      <Campo id="tamanoGrafo" etiqueta="Tamaño de los nodos">
        <select id="tamanoGrafo" value={vista.tamanoGrafo} onChange={(e) => cambiarVista({ tamanoGrafo: e.target.value })}>
          <option value="intermediacion_norm">Intermediación</option>
          {esEsp ? <option value="fuerza_norm">Fuerza (celdas compartidas)</option> : <option value="cercania_norm">Cercanía</option>}
        </select>
      </Campo>
      <label className="check"><input type="checkbox" checked={vista.sobreponer} disabled={esEsp}
        onChange={(e) => cambiarVista({ sobreponer: e.target.checked })} /> Sobreponer el grafo al mapa</label>
      {esEsp && <p className="aviso">Con la red de especies, haz clic en una especie del grafo: el mapa ilumina las celdas donde se observó.</p>}
      <Campo id="disposicion" etiqueta="Disposición de paneles">
        <select id="disposicion" value={vista.disposicion} onChange={(e) => cambiarVista({ disposicion: e.target.value })}>
          <option value="lado">Lado a lado</option><option value="apilado">Uno sobre otro</option>
        </select>
      </Campo>

      <div className="meta">
        {metaCeldas && (<p><b>Celdas filtradas</b><br />{metaCeldas.n_nodos} celdas · {metaCeldas.n_aristas} adyacencias<br />
          {metaCeldas.n_componentes} bloques · {metaCeldas.n_articulaciones} puntos de articulación
          {metaCeldas.intermediacion_aproximada && <><br /><i>intermediación estimada con muestra</i></>}</p>)}
        {metaEspecies && (<p><b>Red de especies</b><br />{metaEspecies.n_nodos} especies · {metaEspecies.n_aristas} vínculos<br />
          {metaEspecies.n_comunidades} comunidades · {metaEspecies.n_aisladas ?? 0} aisladas
          {metaEspecies.modularidad != null && <><br />modularidad {metaEspecies.modularidad.toFixed(2)}</>}</p>)}
        {vista.sobreponer && omitidos > 0 && <p className="aviso">{omitidos} nodos sin posición geográfica no se muestran sobre el mapa.</p>}
        {vista.dinamico && <p className="aviso">Con la carga dinámica, las métricas de red se calculan solo con las celdas visibles.</p>}
      </div>
    </aside>
  );
}
