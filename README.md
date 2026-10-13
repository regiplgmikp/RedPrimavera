# RedPrimavera

RedPrimavera es un proyecto de análisis espacial y vulnerabilidad del Bosque
La Primavera. Integra observaciones de biodiversidad, una malla H3, variables
de vegetación, incendios, caminos, predios e instituciones en un grafo de
Neo4j. Los procesos ETL preparan y cargan la información; una API FastAPI
expone los datos para un frontend geoespacial.

> El repositorio contiene el backend y los ETL. No incluye un frontend.

## Arquitectura

```text
RedPrimavera/
├── backend/
│   ├── main.py                  # Aplicación FastAPI y ciclo de vida
│   ├── database.py              # Driver singleton y sesiones Neo4j
│   ├── analisis/
│   │   └── metricas_red.py      # Métricas topológicas para subgrafos
│   └── routers/
│       ├── celdas.py            # Celdas H3 y estadísticas por zona
│       ├── grafo.py             # Grafo de especies y clústeres
│       └── subgrafos.py         # Subgrafos territoriales filtrables
├── data/
│   ├── boundary/                # GeoJSON de límites y predios
│   └── raw/                     # Insumos locales; ignorados por Git
├── etls/
│   ├── clustering_especies.py
│   ├── descargar_vectores_gobernanza.py
│   ├── etl_caminos.py
│   ├── etl_especies_obser.py
│   ├── etl_gee_estructura.py
│   ├── etl_gee_incendios.py
│   ├── etl_gee_ndvi.py
│   ├── etl_indice_vulnerabilidad.py
│   ├── etl_instituciones.py
│   └── generar_grid_h3.py
├── schema/
│   └── schema.cypher             # Constraints, índices y modelo del grafo
├── tests/
│   ├── contar_cruces.py
│   ├── probar_conexion.py
│   ├── probar_subgrafos.py
│   ├── reparar_adyacencia.py
│   ├── test_metricas_red.py
│   └── validar_mcd64a1.py
├── utils/
│   └── neo4j_conn.py             # Conexión y verificación de Neo4j
├── .env                          # Solo local; nunca versionar
└── README.md
```

`cache/`, `venv/`, `.env`, `data/raw/` y los archivos compilados de Python
están excluidos por `.gitignore`.

## Requisitos

- Python 3.10 o posterior.
- Neo4j 5.x accesible desde el equipo.
- Una cuenta y un proyecto de Google Earth Engine para los ETL de NDVI,
  estructura e incendios.
- Un archivo de observaciones en CSV (Naturalist/iNaturalist) y los insumos
  geoespaciales que correspondan a cada ETL.

### Crear el entorno e instalar dependencias

En Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pandas geopandas shapely osmnx h3 neo4j networkx python-dotenv certifi fastapi "uvicorn[standard]" pydantic earthengine-api
```

Si PowerShell impide activar el entorno:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

En Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pandas geopandas shapely osmnx h3 neo4j networkx python-dotenv certifi fastapi "uvicorn[standard]" pydantic earthengine-api
```

## Configuración

Crea `.env` en la raíz del proyecto. El archivo está ignorado por Git y debe
contener valores locales, nunca credenciales escritas en el README.

```env
NEO4J_URI=neo4j+s://TU_INSTANCIA.databases.neo4j.io
NEO4J_USER=TU_USUARIO
NEO4J_PASSWORD=TU_PASSWORD
GEE_PROJECT=TU_PROYECTO_GEE
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

`NEO4J_URI` conserva el esquema que indique la instancia (`neo4j+s://`,
`neo4j+ssc://`, `neo4j://` o `bolt://`). `CORS_ORIGINS` es opcional y acepta
orígenes separados por comas. Los scripts que usan Earth Engine leen
`GEE_PROJECT` o permiten indicar el proyecto por línea de comandos.

### Autenticar Google Earth Engine

```powershell
earthengine authenticate
python -c "import ee, os; from dotenv import load_dotenv; load_dotenv(); ee.Initialize(project=os.environ['GEE_PROJECT']); print('Conexion exitosa a GEE')"
```

## Modelo de datos

El modelo completo está en [schema/schema.cypher](schema/schema.cypher).
Incluye, entre otros, los nodos:

- `CeldaH3`: identificador H3, resolución, NDVI, estructura, exposición y
  métricas de incendios.
- `Observacion`: fecha, fuente, ubicación, categoría, zona y calidad.
- `Especie`: taxonomía, reino, conservación y clúster de co-ocurrencia.
- `Institucion`, `Predio`, `Camino` y `EventoDisturbio`.

Relaciones principales:

```text
Observacion -[:PERTENECE_A]-> Especie
Observacion -[:UBICADA_EN]-> CeldaH3
Especie -[:COOCURRE_CON]- Especie
CeldaH3 -[:ADYACENTE_A]-> CeldaH3
CeldaH3 -[:CERCANA_A]-> Camino
CeldaH3 -[:DENTRO_DE]-> Predio
CeldaH3 -[:AFECTADO_POR]-> EventoDisturbio
Institucion -[:PROPIETARIA_DE]-> Predio
```

La clasificación espacial usada por las observaciones es `nucleo`,
`zona_mab` y `fuera`.

## Flujo de carga recomendado

Ejecuta los comandos desde la raíz del repositorio. Los ETL usan `MERGE` para
los identificadores principales y pueden repetirse sin duplicar esos nodos.

### 1. Crear constraints e índices

```powershell
cypher-shell -u neo4j -p TU_PASSWORD -f schema/schema.cypher
```

### 2. Preparar capas de referencia

Los GeoJSON actualmente disponibles están en `data/boundary/`. El script de
gobernanza consulta OpenStreetMap mediante OSMnx y genera capas adicionales en
`data/`:

```powershell
python etls/descargar_vectores_gobernanza.py
```

También se incluyen límites de `La_Primavera.geojson`, `AreaTransicion.geojson`,
municipios, predios y el arroyo Las Tortugas.

### 3. Cargar observaciones, especies y celdas asociadas

```powershell
python etls/etl_especies_obser.py `
  --csv data/raw/observaciones.csv `
  --geojson-blp data/boundary/La_Primavera.geojson `
  --geojson-mab data/boundary/AreaTransicion.geojson `
  --resoluciones 8 9
```

El nombre y la ubicación del CSV dependen del insumo disponible. Consulta
todas las opciones con:

```powershell
python etls/etl_especies_obser.py --help
```

### 4. Generar la malla H3 completa

```powershell
python etls/generar_grid_h3.py `
  --geojson data/boundary/La_Primavera.geojson `
  --resoluciones 8 9
```

Este paso crea `CeldaH3` aunque todavía no tengan observaciones y genera
`ADYACENTE_A`. Se recomienda ejecutarlo antes de los ETL de Google Earth
Engine.

### 5. Cargar predios e instituciones

```powershell
python etls/etl_instituciones.py `
  --shp data/raw/PrediosUniversitariosCompletosUTM.shp `
  --resoluciones 8 9
```

Se puede usar `--dry-run` para revisar los predios sin escribir en Neo4j.
El archivo debe conservar sus archivos auxiliares `.dbf`, `.prj` y `.shx`.

### 6. Cargar caminos

```powershell
python etls/etl_caminos.py `
  --input data/raw/caminos_primavera.geojson `
  --geojson-blp data/boundary/La_Primavera.geojson `
  --tipo interno `
  --resolucion 8
```

El ETL crea nodos `Camino` y relaciones `CERCANA_A`. El formato de entrada
puede ser Shapefile o GeoJSON; usa `--help` para ver los nombres exactos de
los argumentos opcionales.

### 7. Calcular variables de vegetación

NDVI reciente con Sentinel-2:

```powershell
python etls/etl_gee_ndvi.py --resolucion 9
```

Opcionalmente:

```powershell
python etls/etl_gee_ndvi.py `
  --resolucion 9 `
  --fecha-inicio 2026-06-24 `
  --fecha-fin 2026-09-22 `
  --proyecto TU_PROYECTO_GEE
```

Estructura del dosel y cobertura arbórea con Meta Canopy Height y ESA
WorldCover:

```powershell
python etls/etl_gee_estructura.py --resolucion 9
```

### 8. Detectar incendios históricos

`etl_gee_incendios.py` compara NBR de Landsat entre años consecutivos,
enmascara nubes y superficies no vegetadas, calcula dNBR por celda y escribe
`EventoDisturbio`, `AFECTADO_POR` y métricas agregadas en `CeldaH3`.

Primero revisa el resultado sin modificar Neo4j:

```powershell
python etls/etl_gee_incendios.py `
  --resolucion 8 `
  --anio-inicio 2000 `
  --anio-fin 2025 `
  --dry-run
```

Después de calibrar los umbrales con la tabla de sensibilidad impresa por el
script, ejecuta nuevamente sin `--dry-run`. La ventana adaptativa y los
resultados anuales se guardan en `cache/`; usa `--sin-cache` para ignorarlos.
Otros parámetros importantes son `--umbral-dnbr`, `--umbral-fraccion`,
`--min-valido`, `--min-cobertura-anual`, `--sin-adaptativo` y `--sin-offset`.

### 9. Construir comunidades de especies

```powershell
python etls/clustering_especies.py
```

Este script lee `COOCURRE_CON`, aplica Louvain con `networkx` y guarda
`cluster_especies` en cada nodo `Especie`. La red de co-ocurrencia debe existir
antes de ejecutar este paso.

### 10. Calcular el Índice de Vulnerabilidad Compuesto

El ETL `etl_indice_vulnerabilidad.py` calcula el IVC por resolución a partir de
incendios, distancia a caminos, biomasa del dosel, NDVI y pertenencia a
predios. Normaliza los componentes con los percentiles p5 y p95, no rellena
datos faltantes y muestra un análisis de sensibilidad de los pesos.

Primero calcula un resumen sin escribir en Neo4j:

```powershell
python etls/etl_indice_vulnerabilidad.py `
  --resoluciones 8 9 `
  --dry-run
```

Cuando el resultado sea satisfactorio, repite el comando sin `--dry-run` para
guardar `indice_vulnerabilidad`, `subindice_exposicion`,
`subindice_sensibilidad`, `subindice_adaptativo` y sus componentes en cada
`CeldaH3`. Las celdas sin todas las variables requeridas quedan sin IVC.

## API FastAPI

Inicia el backend desde la raíz; hacerlo desde `backend/` puede impedir que se
encuentren `utils` y `.env`:

```powershell
python -m uvicorn backend.main:app --reload
```

URLs útiles:

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- OpenAPI: <http://localhost:8000/openapi.json>

### Endpoints disponibles

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/health` | Comprueba la API y la consulta a Neo4j. |
| `GET` | `/grafo/especies` | Devuelve nodos y aristas del grafo de especies. |
| `GET` | `/grafo/especies?incluir_aisladas=true` | Incluye especies sin clúster. |
| `GET` | `/grafo/especies/resumen` | Cuenta especies por clúster y devuelve su color. |
| `GET` | `/celdas?resolucion=8` | Devuelve celdas H3 y estadísticas por zona. |
| `GET` | `/subgrafos/celdas` | Devuelve celdas filtradas, adyacencias y métricas topológicas. |
| `GET` | `/subgrafos/especies` | Devuelve co-ocurrencias restringidas al territorio filtrado. |

`/celdas` acepta `bbox=west,south,east,north` para acotar la consulta:

```text
GET /celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8
```

Los endpoints `/subgrafos/celdas` y `/subgrafos/especies` aceptan filtros como
`ivc_min`, `frecuencia_min`, `ndvi_min`, `dosel_min`,
`distancia_camino_max`, `en_predio`, `institucion` y `bbox`. El subgrafo de
especies también acepta `zona`, `categoria` y
`min_celdas_compartidas`. Las métricas de red se calculan sobre el subconjunto
filtrado y se entregan normalizadas para que un cliente geoespacial pueda
usarlas directamente.

Ejemplos:

```powershell
curl "http://localhost:8000/subgrafos/celdas?resolucion=8&ivc_min=0.6&distancia_camino_max=1000"
curl "http://localhost:8000/subgrafos/especies?resolucion=8&ivc_min=0.6&min_celdas_compartidas=2"
```

Ejemplos con `curl`:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/grafo/especies
curl "http://localhost:8000/celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8"
```

## Verificación y diagnóstico

Prueba la conexión y cuenta las celdas existentes:

```powershell
python tests/probar_conexion.py
```

Para revisar caminos que cruzan el límite del bosque:

```powershell
python tests/contar_cruces.py
```

Con la API corriendo, valida los subgrafos, la adyacencia H3 y las métricas
topológicas:

```powershell
python tests/probar_subgrafos.py
```

Las pruebas unitarias de `backend/analisis/metricas_red.py` se ejecutan con
pytest:

```powershell
python -m pytest tests/test_metricas_red.py
```

Para consultar opciones de cualquier ETL:

```powershell
python etls/NOMBRE_DEL_SCRIPT.py --help
```

Problemas frecuentes:

- `KeyError: NEO4J_URI` o `NEO4J_PASSWORD`: falta una variable en `.env`.
- Error TLS o de autenticación: revisa el esquema de `NEO4J_URI`, usuario,
  contraseña y disponibilidad de la instancia.
- Error de Earth Engine: vuelve a ejecutar `earthengine authenticate` y
  confirma que `GEE_PROJECT` está habilitado.
- Cero celdas: genera primero el grid H3 para la resolución consultada.
- Fallos de importación de `utils`: ejecuta los comandos desde la raíz y
  verifica que el entorno virtual esté activo.

## Estado actual

El proyecto ya permite:

- cargar observaciones y taxonomía;
- generar celdas H3 y adyacencias;
- calcular NDVI, estructura de vegetación e incendios históricos con GEE;
- cargar caminos, predios e instituciones;
- calcular comunidades de especies por co-ocurrencia;
- calcular el Índice de Vulnerabilidad Compuesto por celda;
- generar subgrafos territoriales con métricas de conectividad y centralidad;
- consultar el grafo y las celdas mediante FastAPI.

La relación `ACTUA_SOBRE` todavía no es creada por los ETL. La fórmula del IVC
ya está implementada, pero requiere que las variables de entrada estén
disponibles para que una celda reciba un valor completo.
