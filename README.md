# RedPrimavera

> Documentación actualizada en octubre de 2026.

RedPrimavera es una aplicación de análisis espacial y vulnerabilidad del
Bosque La Primavera. Integra observaciones de biodiversidad, una malla H3,
variables de vegetación, incendios, caminos, predios, instituciones y
población en un grafo de Neo4j. Los procesos ETL preparan y cargan la
información; una API FastAPI calcula subgrafos y métricas de red; y un
frontend geoespacial en React, Vite, Deck.gl y Sigma permite explorar los
resultados.

La aplicación trabaja principalmente con celdas H3 de resolución 8
(aproximadamente 70–90 ha) y 9 (aproximadamente 10 ha). Las métricas
topológicas se calculan sobre el subconjunto que resulta de los filtros
territoriales, no sobre toda la red.

## Inicio rápido

Para probar la aplicación con una base de Neo4j ya cargada:

1. Instala las dependencias del backend y configura el archivo `.env` como se
   explica en [Configuración](#configuración).
2. Instala las dependencias del frontend:

   ```powershell
   cd frontend
   npm ci
   cd ..
   ```

3. En una terminal, desde la raíz del repositorio, inicia la API:

   ```powershell
   python -m uvicorn backend.main:app --reload
   ```

4. En otra terminal, inicia el frontend:

   ```powershell
   cd frontend
   npm run dev
   ```

5. Abre <http://localhost:5173>. La API estará disponible en
   <http://localhost:8000/docs>.

Este flujo solo inicia los servicios. Si la base de datos aún no tiene datos,
ejecuta primero el [flujo de carga recomendado](#flujo-de-carga-recomendado).

## Arquitectura

```text
RedPrimavera/
├── backend/
│   ├── main.py                  # Aplicación FastAPI y ciclo de vida
│   ├── database.py              # Driver singleton y sesiones Neo4j
│   ├── consultas_espaciales.py  # Consultas Cypher reutilizables
│   ├── analisis/
│   │   └── metricas_red.py      # Métricas topológicas para subgrafos
│   └── routers/
│       ├── capas.py             # Capas auxiliares, como población
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
│   ├── etl_poblacion_kontur.py
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
├── frontend/                     # Aplicación React/Vite
│   ├── src/
│   ├── test/                     # Pruebas de lógica del cliente
│   ├── package.json
│   ├── package-lock.json
│   └── .env.example
├── .env                          # Solo local; nunca versionar
└── README.md
```

`cache/`, `venv/`, `.env`, `data/raw/` y los archivos compilados de Python
están excluidos por `.gitignore`. Las dependencias instaladas de Node se
guardan en `frontend/node_modules/` y también están excluidas. Los archivos
geoespaciales de `data/boundary/` sí forman parte del proyecto; los insumos
pesados o descargados para los ETL deben colocarse en `data/raw/`.

## Requisitos

- Python 3.10 o posterior.
- Node.js 18 o posterior y npm para el frontend.
- Neo4j 5.x accesible desde el equipo.
- Una cuenta y un proyecto de Google Earth Engine para los ETL de NDVI,
  estructura e incendios.
- Un archivo de observaciones en CSV de iNaturalist/Naturalist o un archivo
  `occurrence.txt` de GBIF (Darwin Core).
- Los insumos geoespaciales que correspondan a cada ETL.

### Crear el entorno e instalar dependencias

En Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pandas geopandas shapely pyogrio osmnx h3 neo4j networkx scipy python-dotenv certifi fastapi "uvicorn[standard]" pydantic earthengine-api pytest
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
python -m pip install pandas geopandas shapely pyogrio osmnx h3 neo4j networkx scipy python-dotenv certifi fastapi "uvicorn[standard]" pydantic earthengine-api pytest
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

### Configurar el frontend

En otra terminal, desde la raíz del repositorio:

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
```

Usa `npm install` si necesitas actualizar intencionalmente
`frontend/package-lock.json`.

El archivo `frontend/.env` permite configurar la URL del backend:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Si se cambia ese valor, el origen del frontend también debe estar incluido en
`CORS_ORIGINS` del `.env` de la raíz. Por ejemplo, para el servidor de
desarrollo:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

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
`zona_mab` y `fuera`. En la interfaz, `zona_mab` se presenta como “zona de
transición”. El nombre del atributo es provisional porque la fuente de
geometría distingue entre amortiguamiento y transición; debe confirmarse
antes de cambiarlo en los datos.

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

También puede cargarse un archivo Darwin Core de GBIF. `--csv` y `--gbif`
son fuentes alternativas; `--limite` permite probar con una muestra:

```powershell
python etls/etl_especies_obser.py `
  --gbif data/raw/gbif/occurrence.txt `
  --limite 10000 `
  --geojson-blp data/boundary/La_Primavera.geojson `
  --geojson-mab data/boundary/AreaTransicion.geojson `
  --resoluciones 8 9
```

El nombre y la ubicación del insumo dependen de la fuente disponible.
Consulta todas las opciones con:

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

### 10. Cargar población de Kontur

Descarga manualmente el GeoPackage de **Kontur Population México** desde
[Humanitarian Data Exchange](https://data.humdata.org/dataset/kontur-population-mexico)
y guárdalo en `data/raw/`. El archivo no se incluye en el repositorio. La
descarga local actual puede llamarse `kontur_population_MX_20220630.gpkg`;
el nombre no es fijo, así que usa la ruta real del archivo en cada
instalación.
El ETL carga la población únicamente en celdas H3 de resolución 8; no
interpola datos hacia resolución 9.

Primero revisa el resultado:

```powershell
python etls/etl_poblacion_kontur.py `
  --gpkg data/raw/kontur_population_MX_20220630.gpkg `
  --dry-run
```

Después repite el comando sin `--dry-run` para escribir
`poblacion_kontur` en Neo4j. La fuente se distribuye bajo licencia CC BY 4.0;
la interfaz muestra la atribución correspondiente.

### 11. Calcular el Índice de Vulnerabilidad Compuesto

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

La API necesita `NEO4J_URI` y `NEO4J_PASSWORD` para crear el driver bajo
demanda. El endpoint `/health`, además de comprobar que la aplicación está
viva, ejecuta una consulta sencilla contra Neo4j.

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
| `GET` | `/subgrafos/especies/buscar?q=...` | Busca especies por nombre científico o común. |
| `GET` | `/subgrafos/especies/observaciones` | Devuelve las celdas donde aparece una especie. |
| `GET` | `/subgrafos/celdas/especies` | Devuelve las especies observadas en una celda. |
| `GET` | `/capas/poblacion` | Devuelve la capa de población Kontur en resolución 8. |

`/celdas` acepta `bbox=west,south,east,north` para acotar la consulta:

```text
GET /celdas?resolucion=9&bbox=-103.6,20.5,-103.4,20.8
```

Los endpoints `/subgrafos/celdas` y `/subgrafos/especies` comparten filtros de
territorio: `resolucion` (8 o 9), `ivc_min`, `ivc_max`, `frecuencia_min`,
`frecuencia_max`, `ultimo_incendio_desde`, `ndvi_min`, `ndvi_max`,
`dosel_min`, `distancia_camino_min`, `distancia_camino_max`, `en_predio`,
`institucion` y `bbox`. El subgrafo de especies también acepta `zona`,
`categoria` y `min_celdas_compartidas`. `bbox` usa el formato
`west,south,east,north` en grados decimales.

Las métricas de red se calculan sobre el subconjunto filtrado y se entregan
normalizadas para que un cliente geoespacial pueda usarlas directamente. El
endpoint `/subgrafos/celdas` tiene un límite de seguridad de 4,000 celdas por
respuesta.

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

### Iniciar el frontend

Con el backend corriendo, inicia la interfaz desde otra terminal:

```powershell
cd frontend
npm run dev
```

Abre <http://localhost:5173>. La interfaz permite:

- explorar celdas H3 coloreadas por IVC, NDVI, dosel, incendios o población;
- visualizar también observaciones, centralidad y bloques conectados;
- aplicar filtros territoriales y ajustar la resolución automáticamente según
  el zoom y el encuadre del mapa;
- consultar el grafo de especies o el grafo de celdas;
- buscar y seleccionar una especie para iluminar sus celdas de observación;
- seleccionar una celda para consultar sus especies;
- superponer el grafo territorial sobre el mapa y cambiar el tamaño/color de
  los nodos según sus métricas.

La interfaz muestra una bienvenida la primera vez que se abre en un navegador.
Desde esa ventana se puede iniciar el recorrido guiado; la preferencia se
guarda localmente y puede restablecerse borrando los datos del sitio para
`localhost:5173`.

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

La suite de Node configurada para el frontend se ejecuta desde `frontend/`:

```powershell
npm test
npm run build
```

`npm run dev` inicia Vite en modo desarrollo, `npm run build` genera la
versión de producción en `frontend/dist/` y `npm run preview` permite
servir esa compilación localmente.

También hay scripts auxiliares para revisar la red y los datos:

```powershell
python tests/reparar_adyacencia.py --help
python tests/validar_mcd64a1.py --help
```

`reparar_adyacencia.py` solo aplica cambios si se especifica `--aplicar`.
`validar_mcd64a1.py` inspecciona la detección de incendios MCD64A1 en Earth
Engine. Los scripts `tests/probar_conexion.py`, `tests/probar_subgrafos.py` y
`tests/contar_cruces.py` requieren una instancia de Neo4j con datos cargados.

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
- consultar el grafo y las celdas mediante FastAPI;
- explorar el mapa con color por IVC, incendios, NDVI, dosel, observaciones o
  bloques conectados;
- consultar población estimada de Kontur y superponer el grafo de celdas;
- seleccionar especies o celdas para iluminar sus relaciones y observaciones.

La relación `ACTUA_SOBRE` todavía no es creada por los ETL. La fórmula del IVC
ya está implementada, pero requiere que las variables de entrada estén
disponibles para que una celda reciba un valor completo. La población de
Kontur permanece en su resolución nativa (H3 8), y las métricas de red se
recalculan sobre el subconjunto filtrado que solicita cada consulta.

## Licencias y atribuciones de datos

La capa de población procede de Kontur Population México y se muestra con
atribución **CC BY 4.0**:
[Humanitarian Data Exchange](https://data.humdata.org/dataset/kontur-population-mexico).
Las demás capas y observaciones conservan las condiciones de uso de sus
fuentes originales; revisa esas licencias antes de redistribuir los datos
descargados.
