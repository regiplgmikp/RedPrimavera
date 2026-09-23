
# RedPrimavera

Proyecto de análisis espacial del Bosque La Primavera. Integra datos de
observaciones de especies, celdas H3, caminos y redes de co-ocurrencia en
Neo4j. Los ETL cargan y transforman los datos, mientras que la API expone el
grafo de especies para su consumo desde un frontend.

## Estructura principal

```text
RedPrimavera/
├── backend/
│   ├── __init__.py
│   ├── database.py              # Sesiones y driver de Neo4j para la API
│   ├── main.py                  # Aplicación FastAPI y endpoint /health
│   └── routers/
│       ├── __init__.py
│       ├── celdas.py             # Endpoint de celdas H3
│       └── grafo.py              # Endpoints del grafo de especies
├── data/
│   ├── boundary/
│   │   ├── AreaTransicion.geojson
│   │   └── La_Primavera.geojson
│   └── raw/
│       ├── export.geojson
│       └── observations_23082026.csv
├── etls/
│   ├── clustering_especies.py    # Comunidades Louvain en COOCURRE_CON
│   ├── etl_caminos.py             # Caminos y relaciones CERCANA_A
│   ├── etl_especies_obser.py      # Especies, observaciones y celdas H3
│   ├── etl_gee_estructura.py      # Dosel y cobertura arbórea con GEE
│   ├── etl_gee_ndvi.py             # NDVI por celda H3 con GEE
│   └── generar_grid_h3.py          # Grid H3 completo y adyacencias
├── schema/
│   └── schema.cypher              # Constraints, índices y modelo de Neo4j
├── utils/
│   ├── __init__.py
│   └── neo4j_conn.py              # Conexión compartida a Neo4j
├── .env                           # Variables locales; no versionar
├── .gitignore
└── README.md
```

La carpeta `venv/` puede existir localmente como entorno virtual, pero no forma
parte del código fuente ni debe subirse al repositorio.

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

# 4. Calcular NDVI reciente por celda H3 con Sentinel-2
python etls/etl_gee_ndvi.py \
  --resolucion 9 \
  --fecha-inicio 2026-06-24 \
  --fecha-fin 2026-09-22

# 5. Calcular estructura de vegetación por celda H3 con Google Earth Engine
python etls/etl_gee_estructura.py --resolucion 9

# 6. (cuando tengas el shp o GeoJSON) cargar caminos
python etls/etl_caminos.py \
  --input ruta/a/caminos_internos.shp \
  --geojson-blp data/boundary/La_Primavera.geojson \
  --tipo interno \
  --resolucion 8

# 7. Calcular clusters de especies por co-ocurrencia espacial
python etls/clustering_especies.py
```

Los ETL leen `NEO4J_URI`, `NEO4J_USER` y `NEO4J_PASSWORD` desde `.env`, por lo
que no es necesario pasarlos como argumentos si el archivo está configurado.

El ETL de NDVI debe ejecutarse después de generar el grid H3. Consulta
Sentinel-2 SR Harmonized en Google Earth Engine, aplica una máscara de nubes y
guarda el promedio por celda en la propiedad `CeldaH3.ndvi_actual`. Si no se
indican fechas, usa los 90 días anteriores a la fecha de ejecución. El proyecto
de GEE puede pasarse con `--proyecto` o mediante `GEE_PROJECT`.

Ejemplo usando la ventana predeterminada de 90 días:

```bash
python etls/etl_gee_ndvi.py --resolucion 9
```

El ETL de estructura (`etls/etl_gee_estructura.py`) consulta Meta Canopy Height
y ESA WorldCover en Google Earth Engine. Guarda en cada `CeldaH3` la altura
promedio y máxima del dosel (`canopy_height_mean` y `canopy_height_max`), así
como el porcentaje de cobertura arbórea (`cobertura_arbolada_pct`). Requiere
que el grid H3 ya exista y usa `GEE_PROJECT` o `--proyecto` para seleccionar el
proyecto de Google Earth Engine.

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
(necesita el shp de caminos) y `dist_arboles` (la variable de estructura ya se
calcula por celda, pero todavía falta definir cómo convertirla en distancia a
árboles y completar la fórmula).

## Verificación rápida post-carga

```cypher
MATCH (o:Observacion) RETURN count(o);                    // ~12,077
MATCH (e:Especie) RETURN count(e);                        // ~1,909
MATCH (c:CeldaH3 {resolucion: 8}) RETURN count(c);
MATCH (c:CeldaH3 {resolucion: 8})-[r:ADYACENTE_A]->() RETURN count(r);

// Celdas con NDVI calculado
MATCH (c:CeldaH3 {resolucion: 9})
WHERE c.ndvi_actual IS NOT NULL
RETURN count(c), min(c.ndvi_actual), max(c.ndvi_actual);

// Celdas con variables de estructura calculadas
MATCH (c:CeldaH3)
WHERE c.canopy_height_mean IS NOT NULL
RETURN c.resolucion AS resolucion,
       count(c) AS total_celdas,
       round(avg(c.canopy_height_mean), 2) AS altura_promedio_m,
       round(max(c.canopy_height_max), 2) AS altura_maxima_m,
       round(avg(c.cobertura_arbolada_pct), 2) AS cobertura_promedio_pct
ORDER BY resolucion;

// También puede usarse el siguiente para verificar NDVI
MATCH (c:CeldaH3)
WHERE c.ndvi_actual IS NOT NULL
RETURN c.resolucion AS resolucion,
       count(c) AS total_celdas,
       round(min(c.ndvi_actual), 3) AS ndvi_min,
       round(avg(c.ndvi_actual), 3) AS ndvi_promedio,
       round(max(c.ndvi_actual), 3) AS ndvi_max
ORDER BY resolucion;

// Top especies por número de observaciones
MATCH (o:Observacion)-[:PERTENECE_A]->(e:Especie)
RETURN e.nombre_cientifico, count(o) AS n
ORDER BY n DESC LIMIT 10;
```
