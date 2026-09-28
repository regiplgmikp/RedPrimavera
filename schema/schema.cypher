// ============================================================
// Esquema del grafo — Proyecto Vulnerabilidad Bosque La Primavera
// Neo4j 5.x
// ============================================================
//
// NODOS
// -----
// CeldaH3        (h3_id, resolucion, ndvi_actual, dnbr_reciente,
//                 worldcover_clase, canopy_height_m, elevacion,
//                 pendiente, poblacion_kontur)
// Observacion     (id, uuid, fecha, fuente, lat, lon, categoria,
//                  zona, quality_grade, url, image_url)
//                  zona: clasificación en tres anillos concéntricos --
//                    "nucleo"   = dentro del APFF La Primavera (CONANP/DOF)
//                    "zona_mab" = fuera del núcleo pero dentro de la
//                                 zonificación de la Reserva de la Biósfera
//                                 (UNESCO MAB 2011)
//                    "fuera"    = sin designación oficial (interfaz urbana,
//                                 ej. Las Agujas/CUCBA, Zapopan)
//                  NOTA: el nombre "zona_mab" es provisional. El archivo
//                  fuente se llama LimiteAreaAmortiguamiento pero declara
//                  ZON_GRAL='ZTRANSICION' internamente; amortiguamiento y
//                  transición son anillos distintos en el esquema UNESCO MAB.
//                  Confirmar con la fuente y renombrar si aplica.
// Especie         (taxon_id, nombre_cientifico, nombre_comun,
//                  reino_iconico, estatus_conservacion, endemica)
// Institucion     (nombre, tipo, labor, descripcion)
// Camino          (id, tipo, geometria_wkt)
// Predio          (id, area_ha, geometria_wkt)
// EventoDisturbio (fecha, tipo, dnbr, area_ha, periodo_retorno)
//
// RELACIONES
// ----------
// (Observacion)-[:PERTENECE_A]->(Especie)
// (Observacion)-[:UBICADA_EN]->(CeldaH3)
// (Institucion)-[:ACTUA_SOBRE {peso, dist_calle, dist_arboles, buffer_m}]->(Observacion)
// (CeldaH3)-[:AFECTADO_POR {severidad}]->(EventoDisturbio)
// (CeldaH3)-[:CERCANA_A {distancia_m}]->(Camino)
// (Institucion)-[:PROPIETARIA_DE]->(Predio)
// (CeldaH3)-[:DENTRO_DE]->(Predio)   -- celdas que intersectan el polígono del predio
// (CeldaH3)-[:ADYACENTE_A {resolucion}]->(CeldaH3)
// (Observacion)-[:TIENE_VULNERABILIDAD {exposicion, sensibilidad,
//                capacidad_adaptativa, indice_compuesto}]->(CeldaH3)
// ============================================================

// --- Constraints de unicidad ---
CREATE CONSTRAINT celda_h3_id IF NOT EXISTS
FOR (c:CeldaH3) REQUIRE (c.h3_id, c.resolucion) IS UNIQUE;

CREATE CONSTRAINT observacion_id IF NOT EXISTS
FOR (o:Observacion) REQUIRE o.id IS UNIQUE;

CREATE CONSTRAINT especie_nombre_cientifico IF NOT EXISTS
FOR (e:Especie) REQUIRE e.nombre_cientifico IS UNIQUE;

CREATE CONSTRAINT institucion_nombre IF NOT EXISTS
FOR (i:Institucion) REQUIRE i.nombre IS UNIQUE;

CREATE CONSTRAINT camino_id IF NOT EXISTS
FOR (cam:Camino) REQUIRE cam.id IS UNIQUE;

CREATE CONSTRAINT predio_id IF NOT EXISTS
FOR (p:Predio) REQUIRE p.id IS UNIQUE;

// --- Índices de consulta frecuente ---
CREATE INDEX especie_taxon_id IF NOT EXISTS
FOR (e:Especie) ON (e.taxon_id);

CREATE INDEX especie_nombre_comun IF NOT EXISTS
FOR (e:Especie) ON (e.nombre_comun);

CREATE INDEX observacion_fecha IF NOT EXISTS
FOR (o:Observacion) ON (o.fecha);

CREATE INDEX observacion_categoria IF NOT EXISTS
FOR (o:Observacion) ON (o.categoria);

CREATE INDEX observacion_zona IF NOT EXISTS
FOR (o:Observacion) ON (o.zona);

CREATE INDEX celda_resolucion IF NOT EXISTS
FOR (c:CeldaH3) ON (c.resolucion);

CREATE INDEX evento_fecha IF NOT EXISTS
FOR (e:EventoDisturbio) ON (e.fecha);