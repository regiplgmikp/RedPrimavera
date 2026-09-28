
# RedPrimavera

Proyecto de análisis espacial del Bosque La Primavera. Integra observaciones
de especies, celdas H3, caminos, variables de vegetación y redes de
co-ocurrencia en Neo4j. Los ETL cargan y transforman los datos, mientras que
la API FastAPI expone el grafo de especies y las celdas para un frontend.

## Estructura actual

```text
RedPrimavera/
├── backend/
│   ├── __init__.py
│   ├── database.py              # Driver singleton y sesión de Neo4j
│   ├── main.py                  # Aplicación FastAPI + /health + CORS
│   └── routers/
│       ├── __init__.py
│       ├── celdas.py             # GET /celdas
│       └── grafo.py              # GET /grafo/especies y /grafo/especies/resumen
├── data/
│   ├── boundary/
│   │   ├── AreaTransicion.geojson
│   │   ├── arroyo_lasTortugas.geojson
│   │   ├── La_Primavera.geojson
│   │   ├── municipios_primavera.geojson
│   │   ├── predios_iteso.geojson
│   │   └── predios_UDG.geojson
│   └── raw/
│       ├── observations_23082026.csv
│       └── PrediosUniversitariosCompletosUTM.*
├── cache/                         # archivos locales generados por ETL / caché
├── etls/
│   ├── clustering_especies.py     # Louvain sobre COOCURRE_CON
│   ├── descargar_vectores_gobernanza.py
│   ├── etl_caminos.py             # carga de caminos y relaciones CERCANA_A
│   ├── etl_especies_obser.py      # especies, observaciones y celdas H3
│   ├── etl_gee_estructura.py      # Meta Canopy Height + ESA WorldCover
│   ├── etl_gee_ndvi.py            # NDVI desde Sentinel-2 SR Harmonized
│   ├── etl_instituciones.py       # predios/instituciones y relación con celdas
│   └── generar_grid_h3.py         # grid H3 completo y ADYACENTE_A
├── schema/
│   └── schema.cypher              # constraints, índices y modelo del grafo
├── tests/
│   ├── contar_cruces.py
│   └── probar_conexion.py
├── utils/
│   ├── __init__.py
│   └── neo4j_conn.py              # conexión a Neo4j con manejo de certificados
├── .env                           # credenciales locales (no versionar)
├── .gitignore
├── README.md
└── venv/                          # entorno virtual local (no versionar)
```

La carpeta `venv/` puede existir localmente como entorno virtual, pero no forma
parte del repositorio. Los archivos en `data/raw/`, `cache/`, `.env` y `venv/`
se excluyen por `.gitignore`.

## Requisitos

Se requiere Python 3.10+ y una instancia de Neo4j accesible.

### Dependencias principales

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install pandas h3 neo4j geopandas shapely networkx python-dotenv certifi fastapi "uvicorn[standard]" pydantic earthengine-api
```

Si PowerShell bloquea la activación del entorno virtual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

En Linux/macOS:

```bash
source venv/bin/activate
```

## Variables de entorno

Crea un archivo `.env` en la raíz del proyecto con tus credenciales locales.
Nunca subas este archivo ni publiques la contraseña.

```env
NEO4J_URI=neo4j+s://TU_ID.databases.neo4j.io
NEO4J_USER=TU_USUARIO
NEO4J_PASSWORD=TU_PASSWORD
# Proyecto de Google Earth Engine, requerido por los ETL o scripts que consulten GEE
GEE_PROJECT=TU_PROYECTO_GEE
# Orígenes permitidos por la API, separados por comas (opcional)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Notas:
- `NEO4J_USER` puede variar según la instancia de Neo4j/Aura.
- `GEE_PROJECT` solo es necesario para los ETL que usan Google Earth Engine.
- `CORS_ORIGINS` es opcional pero se usa por la API FastAPI.

## Verificación de Earth Engine

Si vas a ejecutar código que consulte Google Earth Engine, autentícate una vez
con la cuenta o el proyecto configurado y verifica la conexión:

```bash
earthengine authenticate
python -c "import ee, os; from dotenv import load_dotenv; load_dotenv(); ee.Initialize(project=os.environ['GEE_PROJECT']); print('Conexion exitosa a GEE')"
```

## Modelo de datos y esquema

El esquema de Neo4j se define en [schema/schema.cypher](schema/schema.cypher).
Incluye nodos como:
- `CeldaH3`
- `Observacion`
- `Especie`
- `Camino`
- `Predio`
- `Institucion`
- `EventoDisturbio`

Y relaciones clave como:
- `(:Especie)-[:COOCURRE_CON]-(:Especie)`
- `(:Observacion)-[:PERTENECE_A]->(:Especie)`
- `(:Observacion)-[:UBICADA_EN]->(:CeldaH3)`
- `(:CeldaH3)-[:ADYACENTE_A]->(:CeldaH3)`
- `(:CeldaH3)-[:CERCANA_A]->(:Camino)`
- `(:CeldaH3)-[:DENTRO_DE]->(:Predio)`

## Orden de ejecución recomendado

Los scripts usan `MERGE` en Neo4j y son idempotentes para los identificadores que
ya existen. Se recomienda ejecutar desde la raíz del proyecto.

### 1) Crear constraints e índices

```bash
cypher-shell -u neo4j -p TU_PASSWORD -f schema/schema.cypher
```

### 2) Cargar observaciones y especies

El ETL principal de observaciones clasifica cada punto en las zonas `nucleo`,
`zona_mab` y `fuera` cuando se le pasan los GeoJSON correspondientes.

```bash
python etls/etl_especies_obser.py \
  --csv data/raw/observations_23082026.csv \
  --geojson-blp data/boundary/La_Primavera.geojson \
  --geojson-mab data/boundary/AreaTransicion.geojson \
  --resoluciones 8 9
```

### 3) Generar el grid H3 del área de estudio

```bash
python etls/generar_grid_h3.py \
  --geojson data/boundary/La_Primavera.geojson \
  --resoluciones 8 9
```

### 4) Generar NDVI por celda H3 con Google Earth Engine

```bash
python etls/etl_gee_ndvi.py --resolucion 9
```

También acepta:

```bash
python etls/etl_gee_ndvi.py \
  --resolucion 9 \
  --fecha-inicio 2026-06-24 \
  --fecha-fin 2026-09-22 \
  --proyecto TU_PROYECTO_GEE
```

Este script actualiza la propiedad `CeldaH3.ndvi_actual`.

### 5) Calcular estructura de vegetación por celda H3

```bash
python etls/etl_gee_estructura.py --resolucion 9
```

Escribe en cada celda:
- `canopy_height_mean`
- `canopy_height_max`
- `cobertura_arbolada_pct`

### 6) Cargar caminos (si se cuenta con el shapefile o GeoJSON)

```bash
python etls/etl_caminos.py \
  --input ruta/a/caminos_internos.shp \
  --geojson-blp data/boundary/La_Primavera.geojson \
  --tipo interno \
  --resolucion 8
```

### 7) Calcular comunidades de especies por co-ocurrencia

```bash
python etls/clustering_especies.py
```

Esto usa Louvain en `networkx` y escribe `Especie.cluster_especies`.

## Comandos útiles para explorar opciones

```bash
python etls/etl_especies_obser.py --help
python etls/generar_grid_h3.py --help
python etls/etl_gee_ndvi.py --help
python etls/etl_gee_estructura.py --help
python etls/etl_caminos.py --help
python etls/clustering_especies.py --help
```

## API backend

El backend está implementado con FastAPI y se debe ejecutar desde la raíz del
proyecto para que encuentre `utils` y `.env`.

```bash
python -m uvicorn backend.main:app --reload
```

La API estará disponible en:
- http://localhost:8000
- Swagger docs: http://localhost:8000/docs

### Endpoints implementados

```text
GET /health
GET /grafo/especies
GET /grafo/especies?incluir_aisladas=true
GET /grafo/especies/resumen
GET /celdas?resolucion=8
GET /celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8
```

### Descripción de los endpoints

- `/health`: confirma que la API responde y que puede consultar Neo4j.
  Devuelve `status` y `nodos_en_base`.
- `/grafo/especies`: devuelve nodos `Especie` y aristas `COOCURRE_CON` con
  color por `cluster_especies` y forma según el reino.
- `/grafo/especies?incluir_aisladas=true`: incluye especies sin clúster.
- `/grafo/especies/resumen`: cuenta especies por clúster para uso visual.
- `/celdas`: devuelve celdas H3 con su `boundary`, resolución, conteo por zona y
  color dominante. El parámetro `bbox` acepta `west,south,east,north`.

### Pruebas rápidas

```bash
curl http://localhost:8000/health
curl http://localhost:8000/grafo/especies
curl "http://localhost:8000/grafo/especies?incluir_aisladas=true"
curl http://localhost:8000/grafo/especies/resumen
curl "http://localhost:8000/celdas?resolucion=8"
curl "http://localhost:8000/celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8"
```

## Solución de problemas comunes

- `KeyError: NEO4J_URI` o `KeyError: NEO4J_PASSWORD`: falta una variable en
  `.env` o el archivo está en otra ubicación.
- Error de conexión con Neo4j: revisa la dirección, el esquema (`neo4j://`,
  `neo4j+s://`, etc.) y que la base se encuentre disponible.
- Error con Earth Engine: ejecuta `earthengine authenticate` y asegúrate de que
  `GEE_PROJECT` exista y esté habilitado en Google Cloud.
- La API devuelve cero celdas: revisa que ya se haya corrido `generar_grid_h3.py`
  para la resolución que consultas.
- El backend debe ejecutarse con:

```bash
python -m uvicorn backend.main:app --reload
```

## Notas del repositorio

- `utils/neo4j_conn.py` centraliza la conexión a Neo4j y manejar certificados
  con `certifi`.
- `backend/database.py` carga `.env` desde la raíz y expone una dependencia
  `get_session()` para FastAPI.
- Los scripts `etl_gee_ndvi.py` y `etl_gee_estructura.py` requieren que la
  grilla H3 ya exista antes de calcular estadísticas zonales.
- El archivo `schema/schema.cypher` debe ejecutarse antes de cargar datos si la
  base está vacía.

## Estado del proyecto

El repositorio actual ya contiene la base para:

- cargar observaciones y especies desde CSV
- generar y consultar celdas H3
- calcular NDVI y estructura del dosel mediante GEE
- crear relaciones de co-ocurrencia espacial entre especies
- consultar el grafo y la distribución espacial a través de FastAPI

Si quieres continuar el desarrollo, el siguiente paso natural es conectar el
frontend al backend para visualizar celdas, especies y grafo de co-ocurrencia en
el mapa.
  desde la raíz; ejecutar Uvicorn dentro de `backend/` rompe la importación de
  `utils`.

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

## Institucion — falta cargar info sobre como actuan. ya se tienen los predios

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
