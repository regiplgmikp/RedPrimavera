
# RedPrimavera

Proyecto de análisis espacial del Bosque La Primavera. Integra datos de
observaciones de especies, celdas H3, caminos y redes de co-ocurrencia en
Neo4j. Los ETL cargan y transforman los datos, mientras que la API expone el
grafo de especies para su consumo desde un frontend.

## Estructura principal

```text
backend/   API FastAPI y endpoints del grafo y las celdas H3
data/      Datos crudos y límites GeoJSON
etls/      Scripts de carga, grid H3 y clustering
schema/    Constraints, índices y modelo de Neo4j
utils/     Conexión compartida a Neo4j
```

## Requisitos e instalación

Desde la raíz del proyecto instala las dependencias:

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install pandas h3 neo4j geopandas shapely networkx python-dotenv certifi fastapi "uvicorn[standard]" pydantic earthengine-api
```

En PowerShell, si la política de ejecución bloquea la activación, usa la
sesión actual de la terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

Configura las credenciales de Neo4j en un archivo `.env` en la raíz del
proyecto. No compartas este archivo ni subas la contraseña al repositorio:

```env
NEO4J_URI=neo4j+s://TU_ID.databases.neo4j.io
NEO4J_USER=TU_USUARIO
NEO4J_PASSWORD=TU_PASSWORD
# Proyecto de Google Earth Engine, requerido por los ETL o scripts que consulten GEE
GEE_PROJECT=TU_PROYECTO_GEE
# Orígenes permitidos por la API, separados por comas (opcional)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

`NEO4J_USER` depende de la instancia configurada; en Aura puede ser un usuario
distinto de `neo4j`. Mantén `.env` fuera del control de versiones y nunca
publiques la contraseña ni las credenciales de Google Earth Engine.

### Comprobar Google Earth Engine

Si vas a ejecutar código que consulte Google Earth Engine, autentícate una vez
con la cuenta o el proyecto configurado y verifica la conexión:

```bash
earthengine authenticate
python -c "import ee, os; from dotenv import load_dotenv; load_dotenv(); ee.Initialize(project=os.environ['GEE_PROJECT']); print('Conexion exitosa a GEE')"
```

## Orden de ejecución

```bash

# 1. Crear constraints e índices (una vez, en Neo4j Browser o cypher-shell)
cypher-shell -u neo4j -p TU_PASSWORD -f schema/schema.cypher

# 2. Cargar especies + observaciones (con clasificación en 3 zonas)
python etls/etl_especies_obser.py \
  --csv data/raw/observations_23082026.csv \
  --geojson-blp data/boundary/La_Primavera.geojson \
  --geojson-mab data/boundary/AreaTransicion.geojson \
  --resoluciones 8 9

# 3. Generar el grid H3 del área de estudio
python etls/generar_grid_h3.py \
  --geojson data/boundary/La_Primavera.geojson \
  --resoluciones 8 9

# 4. (cuando tengas el shp o GeoJSON) cargar caminos
python etls/etl_caminos.py \
  --input ruta/a/caminos_internos.shp \
  --geojson-blp data/boundary/La_Primavera.geojson \
  --tipo interno \
  --resolucion 8

# 5. Calcular clusters de especies por co-ocurrencia espacial
python etls/clustering_especies.py
```

Los ETL leen `NEO4J_URI`, `NEO4J_USER` y `NEO4J_PASSWORD` desde `.env`, por lo
que no es necesario pasarlos como argumentos si el archivo está configurado.

## API backend

El backend está construido con FastAPI y debe ejecutarse desde la raíz del
proyecto para encontrar el paquete `utils` y el archivo `.env`:

```bash
python -m uvicorn backend.main:app --reload
```

La API queda disponible en [http://localhost:8000](http://localhost:8000).
La documentación interactiva de Swagger se encuentra en
[http://localhost:8000/docs](http://localhost:8000/docs).

Endpoints principales:

```text
GET /health
GET /grafo/especies
GET /grafo/especies?incluir_aisladas=true
GET /grafo/especies/resumen
GET /celdas?resolucion=8
GET /celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8
```

`/grafo/especies` devuelve nodos `Especie` y relaciones `COOCURRE_CON`,
incluyendo color por `cluster_especies` y forma por reino taxonómico. Por
defecto omite especies sin clúster; usa `incluir_aisladas=true` para incluirlas.

`/celdas` devuelve las celdas H3 con sus vértices, resolución, total de
observaciones, conteos por zona (`nucleo`, `zona_mab` y `fuera`), zona dominante
y color. El parámetro opcional `bbox` usa el formato
`west,south,east,north` en grados decimales para limitar los resultados.

Pruebas rápidas desde otra terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/grafo/especies
curl "http://localhost:8000/grafo/especies?incluir_aisladas=true"
curl http://localhost:8000/grafo/especies/resumen
curl "http://localhost:8000/celdas?resolucion=8"
curl "http://localhost:8000/celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8"
```

La respuesta de `/health` confirma que la API está activa y devuelve el total
de nodos consultado en Neo4j. Si la API no inicia, verifica que el comando se
ejecute desde la raíz del proyecto y que `.env` contenga las variables de
Neo4j.

## ETL de clustering de especies

`etls/clustering_especies.py` agrupa las especies a partir de la red de
co-ocurrencia espacial (`COOCURRE_CON`). Lee las relaciones desde Neo4j,
construye el grafo en `networkx` y aplica el algoritmo de comunidades Louvain
incluido en `networkx`, usando `r.peso` como peso de cada relación. El resultado
se guarda en cada nodo `Especie` mediante la propiedad `cluster_especies`.

El script requiere que la red `COOCURRE_CON` ya exista en Neo4j. Lee las
credenciales desde el archivo `.env`:

```env
NEO4J_URI=neo4j+s://TU_ID.databases.neo4j.io
NEO4J_USER=TU_USUARIO
NEO4J_PASSWORD=TU_PASSWORD
```

Al finalizar muestra el número de relaciones, especies, clusters y la
modularidad calculada. En Neo4j Bloom, `cluster_especies` puede utilizarse como
atributo de color o agrupación para visualizar las comunidades.

## Institucion — carga faltante - SOLICITAR INFORMACIÓN

Un ejemplo de como podría ser la carga es el siguiente:

```cypher
UNWIND [
  {nombre: "ITESO", tipo: "academica", labor: "monitoreo"},
  {nombre: "Tec de Monterrey", tipo: "academica", labor: "monitoreo"},
  {nombre: "OPD Bosque La Primavera", tipo: "gubernamental", labor: "gestion"},
  {nombre: "Ejido", tipo: "comunitaria", labor: "uso de suelo"},
  {nombre: "Colectivo", tipo: "civil", labor: "vigilancia"}
] AS row
MERGE (i:Institucion {nombre: row.nombre})
SET i.tipo = row.tipo, i.labor = row.labor;
```

La relación `ACTUA_SOBRE` (Institución→Observación, con el peso compuesto
`0.2·dist_calle + 0.3·dist_arboles` del pizarrón) **no se carga todavía** —
depende de que definan la fórmula completa y de tener `dist_calle` resuelto
(necesita el shp de caminos) y `dist_arboles` (necesita canopy height vía GEE,
que es la siguiente pieza del stack, no de esta semana).

## Verificación rápida post-carga

```cypher
MATCH (o:Observacion) RETURN count(o);                    // ~12,077
MATCH (e:Especie) RETURN count(e);                        // ~1,909
MATCH (c:CeldaH3 {resolucion: 8}) RETURN count(c);
MATCH (c:CeldaH3 {resolucion: 8})-[r:ADYACENTE_A]->() RETURN count(r);

// Top especies por número de observaciones
MATCH (o:Observacion)-[:PERTENECE_A]->(e:Especie)
RETURN e.nombre_cientifico, count(o) AS n
ORDER BY n DESC LIMIT 10;
```
