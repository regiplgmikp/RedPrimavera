import React from 'react';
import { CAMPOS_COLOR } from '../mapData.js';
import BuscadorEspecies from './BuscadorEspecies.jsx';
import Ayuda from './Ayuda.jsx';

function Campo({ id, etiqueta, ayuda, children }) {
  return (
    <div className="campo">
      <label htmlFor={id}>{etiqueta}{ayuda && <Ayuda titulo={etiqueta}>{ayuda}</Ayuda>}</label>
      {children}
    </div>
  );
}

export default function FilterPanel({ form, setForm, vista, cambiarVista, resolucionEfectiva, 
  aplicar, limpiar, metaCeldas, metaEspecies, omitidos,especieSel, avisoEspecie, onElegirEspecie, onQuitarEspecie }) {
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
    <div className="campo-check">
      <label className="check"><input type="checkbox" checked={vista[clave]} onChange={(e) => cambiarVista({ [clave]: e.target.checked })} /> {texto}</label>
      {extra}
    </div>
  );
  const esEsp = vista.grafo === 'especies';

  return (
    <aside>
      
      <h2>Territorio</h2>
      <Campo id="resolucion" etiqueta="Resolución H3"
        ayuda="Qué tan grandes son los hexágonos del mapa. Con 8, cada uno cubre unas 70 a 90 hectáreas y se ve el bosque completo. Con 9 son más chicos (unas 10 hectáreas): hay más detalle, pero tarda más en cargar.">
        <select id="resolucion" value={vista.autoRes ? resolucionEfectiva : vista.resolucion} disabled={vista.autoRes}
          onChange={(e) => cambiarVista({ resolucion: Number(e.target.value) })}>
          <option value={8}>8 (≈ 70–90 ha)</option><option value={9}>9 (≈ 10 ha)</option>
        </select>
      </Campo>
      <Campo id="ivc_min" etiqueta="IVC mínimo (0–1)"
        ayuda="El índice de vulnerabilidad (IVC) va de 0 a 1 y sirve para comparar zonas: mientras más cerca de 1, más expuesta y sensible a los incendios. Aquí dejas solo las zonas con un IVC igual o mayor a este valor. Por ejemplo, 0.6 muestra las más vulnerables.">
        {num('ivc_min', { min: 0, max: 1, step: 0.05 })}
      </Campo>
      <Campo id="ivc_max" etiqueta="IVC máximo (0–1)"
        ayuda="Lo contrario al anterior: deja solo las zonas con un IVC menor o igual a este valor. Sirve para ver las menos vulnerables.">
        {num('ivc_max', { min: 0, max: 1, step: 0.05 })}
      </Campo>
      <Campo id="frecuencia_min" etiqueta="Frecuencia de incendios mínima (por año)"
        ayuda="Qué tan seguido se detectó un incendio en esa zona desde el año 2000, con imágenes de satélite. 0.2 significa un incendio cada 5 años. Deja solo las zonas con al menos esta frecuencia.">
        {num('frecuencia_min', { min: 0, max: 1, step: 0.02 })}
      </Campo>
      <Campo id="distancia_camino_max" etiqueta="Distancia máxima a camino (m)"
        ayuda="Qué tan lejos está el camino más cercano al centro de cada hexágono. Deja solo las zonas a esta distancia o menos. En el índice, estar cerca de un camino aumenta la exposición.">
        {num('distancia_camino_max', { min: 0, step: 50 })}
      </Campo>
      <Campo id="en_predio" etiqueta="Predio de institución"
        ayuda="Un predio es un terreno que pertenece a una institución, como una universidad. Puedes quedarte solo con las zonas que tocan un predio o solo con las que no.">
        {sel('en_predio', [['', 'Cualquiera'], ['true', 'Dentro de un predio'], ['false', 'Fuera de predios']])}
      </Campo>

      <h2>Red de especies</h2>
      <BuscadorEspecies seleccionada={especieSel} aviso={avisoEspecie} onElegir={onElegirEspecie} onQuitar={onQuitarEspecie} />
      <Campo id="zona" etiqueta="Zona de las observaciones"
        ayuda="El bosque se divide en el núcleo, la zona de transición y lo que queda fuera de su límite. Aquí eliges de cuál de esas zonas se toman las observaciones de especies para armar la red.">
        {sel('zona', [['', 'Todas'], ['nucleo', 'Núcleo'], ['zona_mab', 'Zona de transición'], ['fuera', 'Fuera de la poligonal']])}
      </Campo>
      <Campo id="min_celdas_compartidas" etiqueta="Celdas compartidas mínimas"
        ayuda="Dos especies se conectan en la red si se han observado en las mismas zonas (hexágonos). Este número es cuántas zonas deben compartir como mínimo para dibujar la conexión. Con 2 hay más conexiones; si lo subes, quedan solo las más fuertes y la red se ve más limpia. Si hay demasiadas, el sistema puede subirlo solo para que la página no se trabe.">
        {num('min_celdas_compartidas', { min: 1, max: 50 })}
      </Campo>

      <button className="primario" onClick={aplicar}>Aplicar filtros</button>
      <button className="secundario" onClick={limpiar}>Limpiar</button>

      <h2>Mapa</h2>
      <Campo id="colorMapa" etiqueta="Color de las celdas"
        ayuda={<>
          Qué característica de cada hexágono pinta el mapa:<br />
          <b>IVC:</b> qué tan vulnerable es a incendios (de 0 a 1).<br />
          <b>Frecuencia:</b> qué tan seguido hubo incendios.<br />
          <b>Intermediación:</b> hexágonos que funcionan como puente entre otras zonas.<br />
          <b>Cercanía:</b> qué tan central es, a pocos pasos de las demás.<br />
          <b>Observaciones:</b> cuánta gente ha registrado especies ahí. Más observaciones no siempre significa más biodiversidad: también depende de cuánta gente visita ese lugar.<br />
          <b>Bloque conectado:</b> un color por cada grupo de zonas unidas.<br />
          <b>NDVI:</b> qué tan verde se ve la vegetación.<br />
          <b>Dosel:</b> altura promedio de los árboles, en metros.
        </>}>
        <select id="colorMapa" value={vista.colorMapa} onChange={(e) => cambiarVista({ colorMapa: e.target.value })}>
          {Object.entries(CAMPOS_COLOR).map(([k, d]) => <option key={k} value={k}>{d.etiqueta}</option>)}
        </select>
      </Campo>
      {chk('verPoblacion', 'Capa demográfica (círculos)',
        <Ayuda titulo="Capa demográfica">Dibuja círculos sobre el mapa: mientras más grande el círculo, más personas viven en esa zona. Los datos son de Kontur y solo existen en resolución 8.</Ayuda>)}
      {chk('dinamico', 'Cargar solo lo visible (al mover el mapa)',
        <Ayuda titulo="Cargar solo lo visible">Pide solo los hexágonos que ves en pantalla y se actualiza al mover el mapa. Va más rápido, pero los números de red (como la intermediación) se calculan solo con esas zonas, así que cambian al mover el mapa.</Ayuda>)}
      {chk('autoRes', 'Resolución automática según el zoom',
        <Ayuda titulo="Resolución automática">Cambia sola entre resolución 8 y 9 según el zoom: de lejos ves hexágonos grandes, y al acercarte aparecen los chicos, con más detalle. Mientras está activa no puedes elegir la resolución a mano.</Ayuda>)}

      <h2>Grafo</h2>
      <Campo id="grafo" etiqueta="Qué grafo mostrar"
        ayuda={<>
          Un grafo es un dibujo de puntos conectados por líneas.<br />
          <b>Especies:</b> cada punto es una especie, y dos se conectan si se han visto en las mismas zonas.<br />
          <b>Celdas:</b> cada punto es un hexágono del mapa, y se conecta con los que tiene al lado.
        </>}>
        <select id="grafo" value={vista.grafo} onChange={(e) => cambiarVista({ grafo: e.target.value })}>
          <option value="especies">Especies (co-ocurrencia)</option>
          <option value="celdas">Celdas (adyacencia)</option>
        </select>
      </Campo>
      <Campo id="colorGrafo" etiqueta="Color de los nodos"
        ayuda={esEsp ? <>
          Cada punto del grafo es una especie.<br />
          <b>Taxonomía:</b> el color indica el tipo de ser vivo, como aves, plantas u hongos.<br />
          <b>Comunidad:</b> el color indica el grupo de especies que suelen verse juntas.
        </> : <>
          Cada punto del grafo es un hexágono.<br />
          <b>Institución:</b> el color indica a quién pertenece el predio.<br />
          <b>IVC:</b> el color indica qué tan vulnerable es.<br />
          <b>Bloque conectado:</b> un color por cada grupo de zonas unidas.
        </>}>
        <select id="colorGrafo" value={vista.colorGrafo} onChange={(e) => cambiarVista({ colorGrafo: e.target.value })}>
          {esEsp
            ? [<option key="t" value="taxonomia">Taxonomía</option>, <option key="c" value="comunidad">Comunidad</option>]
            : [<option key="i" value="institucion">Institución</option>, <option key="v" value="ivc">IVC</option>, <option key="b" value="bloque">Bloque conectado</option>]}
        </select>
      </Campo>
      <Campo id="tamanoGrafo" etiqueta="Tamaño de los nodos"
        ayuda={esEsp ? <>
          Qué tan grande se dibuja cada especie.<br />
          <b>Intermediación:</b> las que sirven de puente entre otras especies se ven más grandes.<br />
          <b>Fuerza:</b> las que comparten más zonas con otras especies se ven más grandes.
        </> : <>
          Qué tan grande se dibuja cada hexágono en el grafo.<br />
          <b>Intermediación:</b> los que sirven de puente entre otras zonas se ven más grandes.<br />
          <b>Cercanía:</b> los más centrales, a pocos pasos de todas las demás, se ven más grandes.
        </>}>
        <select id="tamanoGrafo" value={vista.tamanoGrafo} onChange={(e) => cambiarVista({ tamanoGrafo: e.target.value })}>
          <option value="intermediacion_norm">Intermediación</option>
          {esEsp ? <option value="fuerza_norm">Fuerza (celdas compartidas)</option> : <option value="cercania_norm">Cercanía</option>}
        </select>
      </Campo>
      <div className="campo-check">
        <label className="check"><input type="checkbox" checked={vista.sobreponer} disabled={esEsp}
          onChange={(e) => cambiarVista({ sobreponer: e.target.checked })} /> Sobreponer el grafo al mapa</label>
        <Ayuda titulo="Sobreponer el grafo">Dibuja el grafo de celdas encima del mapa, uniendo con líneas los hexágonos vecinos. Solo funciona con el grafo de celdas.</Ayuda>
      </div>
      {esEsp && <p className="aviso">Con la red de especies, haz clic en una especie del grafo: el mapa ilumina las celdas donde se observó.</p>}
      <Campo id="disposicion" etiqueta="Disposición de paneles"
        ayuda="Cómo se acomodan el mapa y el grafo en la pantalla: uno junto al otro, o uno encima del otro.">
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
