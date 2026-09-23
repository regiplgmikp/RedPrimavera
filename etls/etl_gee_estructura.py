"""Calcula altura de dosel (Meta Canopy Height) y cobertura arbórea (ESA WorldCover) y 
los guarda por celda H3 en Neo4j.

Requisitos:
    - Python con earthengine-api, h3, neo4j y python-dotenv instalados.
    - Una cuenta de Google Earth Engine autenticada y un proyecto de Google
      Cloud indicado por GEE_PROJECT o por --proyecto.
    - Una instancia de Neo4j accesible con NEO4J_URI, NEO4J_USER y
      NEO4J_PASSWORD en el entorno o en un archivo .env.
    - Celdas CeldaH3 creadas previamente para la resolucion solicitada.

Qué hace:
    - Lee de Neo4j los H3 existentes en la resolucion indicada.
    - Consulta Meta Canopy Height (1m) y ESA WorldCover 10m v200 en Google Earth
      Engine, combinándolos en una imagen multibanda estructural.
    - Reduce zonalmente por celda H3 para obtener la altura promedio de dosel
      (canopy_height_mean), la altura máxima (canopy_height_max) y el
      porcentaje de cobertura arbolada (cobertura_arbolada_pct).
    - Actualiza los nodos CeldaH3 correspondientes en Neo4j en lotes.

Notas:
    - Si no hay celdas para la resolucion, termina sin escribir cambios.
    - Requiere conectividad con Google Earth Engine y Neo4j.
"""

import argparse
import os
import sys
from pathlib import Path

import ee
import h3
from dotenv import load_dotenv

# Permite importar utils/ desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver  # noqa: E402

load_dotenv()

BATCH_SIZE = 200


def inicializar_ee(proyecto: str):
    ee.Initialize(project=proyecto)


def leer_celdas(driver, resolucion: int) -> list[str]:
    query = "MATCH (c:CeldaH3 {resolucion: $resolucion}) RETURN c.h3_id AS h3_id"
    with driver.session() as session:
        return [r["h3_id"] for r in session.run(query, resolucion=resolucion)]


def construir_feature_collection(h3_ids: list[str]) -> ee.FeatureCollection:
    features = []
    for h3_id in h3_ids:
        boundary = h3.cell_to_boundary(h3_id)
        coords = [[lon, lat] for lat, lon in boundary]
        coords.append(coords[0])  # Cerrar el polígono
        geom = ee.Geometry.Polygon([coords])
        features.append(ee.Feature(geom, {"h3_id": h3_id}))
    return ee.FeatureCollection(features)


def preparar_stack_estructura(bbox: ee.Geometry) -> ee.Image:
    """
    Combina Meta Canopy Height y ESA WorldCover en una sola imagen de 2 bandas:
    - 'canopy_height' (metros)
    - 'tree_pct' (0 a 100)
    """
    print("  Preparando Meta Canopy Height...")
    canopy = (
        ee.ImageCollection("projects/meta-forest-monitoring-okw37/assets/CanopyHeight")
        .filterBounds(bbox)
        .mosaic()
        .rename("canopy_height")
    )

    print("  Preparando ESA WorldCover 10m v200...")
    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    # Clase 10 es Tree Cover; al multiplicar por 100 el reducer 'mean' da el % directo
    tree_mask = worldcover.eq(10).multiply(100).rename("tree_pct")

    return canopy.addBands(tree_mask)


def reducir_estructura_por_celda(img: ee.Image, fc: ee.FeatureCollection, scale: int = 10):
    reducer = ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True)
    return img.reduceRegions(collection=fc, reducer=reducer, scale=scale)


def extraer_resultados(fc_reducida: ee.FeatureCollection) -> list[dict]:
    datos = fc_reducida.getInfo()
    features = datos.get("features", [])

    if not features:
        print("AVISO: reduceRegions no regresó ningún feature.")
        return []

    print(f"  Ejemplo de propiedades del primer resultado: {features[0]['properties']}")

    resultados = []
    for feat in features:
        p = feat["properties"]
        h3_id = p.get("h3_id")
        if not h3_id:
            continue

        c_mean = p.get("canopy_height_mean")
        c_max = p.get("canopy_height_max")
        t_pct = p.get("tree_pct_mean")

        resultados.append({
            "h3_id": h3_id,
            "canopy_height_mean": round(float(c_mean), 2) if c_mean is not None else 0.0,
            "canopy_height_max": round(float(c_max), 2) if c_max is not None else 0.0,
            "cobertura_arbolada_pct": round(float(t_pct), 2) if t_pct is not None else 0.0,
        })
    return resultados


def escribir_estructura(driver, resolucion: int, registros: list[dict]) -> int:
    query = """
    UNWIND $batch AS row
    MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: $resolucion})
    SET c.canopy_height_mean     = row.canopy_height_mean,
        c.canopy_height_max      = row.canopy_height_max,
        c.cobertura_arbolada_pct = row.cobertura_arbolada_pct
    """
    with driver.session() as session:
        for i in range(0, len(registros), BATCH_SIZE):
            session.run(query, batch=registros[i : i + BATCH_SIZE], resolucion=resolucion)

    return len(registros)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolucion", type=int, default=8, help="Resolución H3 (por defecto 8)")
    parser.add_argument(
        "--proyecto",
        default=os.getenv("GEE_PROJECT", "red-primavera"),
        help="ID del proyecto de Google Cloud para GEE.",
    )
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    args = parser.parse_args()

    proyecto = args.proyecto
    if not proyecto:
        raise SystemExit("Falta GEE_PROJECT en el .env o con --proyecto.")

    if not args.password:
        raise SystemExit("Falta NEO4J_PASSWORD en el .env o con --password.")

    print(f"Proyecto GEE: {proyecto}")
    print("Inicializando Earth Engine...")
    inicializar_ee(proyecto)

    driver = get_driver(args.uri, args.user, args.password)

    print(f"Leyendo celdas H3 de resolución {args.resolucion} desde Neo4j...")
    h3_ids = leer_celdas(driver, args.resolucion)
    print(f"  {len(h3_ids)} celdas encontradas")

    if not h3_ids:
        print("No hay celdas para esta resolución.")
        driver.close()
        return

    print("Construyendo FeatureCollection de hexágonos...")
    fc = construir_feature_collection(h3_ids)
    bbox_general = fc.geometry().bounds()

    print("Preparando stack (Canopy Height + ESA WorldCover)...")
    stack_img = preparar_stack_estructura(bbox_general)

    print("Calculando estadísticas estructurales por celda (reduceRegions)...")
    reducido = reducir_estructura_por_celda(stack_img, fc, scale=10)
    resultados = extraer_resultados(reducido)
    print(f"  {len(resultados)} celdas procesadas")

    print("Escribiendo variables estructurales en Neo4j...")
    n = escribir_estructura(driver, args.resolucion, resultados)
    print(f"  {n} nodos CeldaH3 actualizados con éxito")

    driver.close()
    print("\n¡Listo!")


if __name__ == "__main__":
    main()