"""Calcula NDVI reciente de Sentinel-2 y lo guarda por celda H3 en Neo4j.

Requisitos:
        - Python con earthengine-api, h3, neo4j y python-dotenv instalados.
        - Una cuenta de Google Earth Engine autenticada y un proyecto de Google
            Cloud indicado por GEE_PROJECT o por --proyecto.
        - Una instancia de Neo4j accesible con NEO4J_URI, NEO4J_USER y
            NEO4J_PASSWORD en el entorno o en un archivo .env.
        - Celdas CeldaH3 creadas previamente para la resolucion solicitada.

Qué hace:
        - Lee de Neo4j los H3 existentes en la resolucion indicada.
        - Consulta Sentinel-2 SR Harmonized en Google Earth Engine, enmascara
            sombras y nubes mediante SCL y calcula un composite mediano de NDVI.
        - Obtiene el promedio de NDVI por celda y actualiza CeldaH3.ndvi_actual.

Notas:
        - Por defecto procesa los 90 dias anteriores a la fecha de ejecucion;
            usa --fecha-inicio y --fecha-fin para definir otra ventana.
        - Si no hay celdas para la resolucion, termina sin escribir cambios.
        - Requiere conectividad con Google Earth Engine y Neo4j.
"""

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import ee
import h3
from dotenv import load_dotenv

# Permitir importar utils/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver

# Cargar variables del archivo .env
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
        boundary = h3.cell_to_boundary(h3_id)  # [(lat, lon), ...]
        coords = [[lon, lat] for lat, lon in boundary]  # GEE espera [lon, lat]
        coords.append(coords[0])  # cerrar polígono
        geom = ee.Geometry.Polygon([coords])
        features.append(ee.Feature(geom, {"h3_id": h3_id}))
    return ee.FeatureCollection(features)


def enmascarar_nubes_scl(imagen):
    """
    Enmascara nubes y sombras usando la banda SCL de Sentinel-2 SR.
    Valores SCL a excluir: 3 (sombra), 8/9 (nubes), 10 (cirrus).
    """
    scl = imagen.select("SCL")
    mascara = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return imagen.updateMask(mascara)


def construir_imagen_ndvi(fecha_inicio: str, fecha_fin: str, bbox: ee.Geometry) -> ee.Image:
    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(bbox)
        .filterDate(fecha_inicio, fecha_fin)
        .map(enmascarar_nubes_scl)
    )
    mediana = coleccion.median()
    ndvi = mediana.normalizedDifference(["B8", "B4"]).rename("ndvi")
    return ndvi


def reducir_ndvi_por_celda(ndvi_img: ee.Image, fc: ee.FeatureCollection, scale: int = 10):
    return ndvi_img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=scale)


def extraer_resultados(fc_reducida: ee.FeatureCollection) -> dict:
    datos = fc_reducida.getInfo()
    features = datos.get("features", [])

    if not features:
        print("AVISO: reduceRegions no regresó ningún feature.")
        return {}

    print(f"  Ejemplo de propiedades del primer resultado: {features[0]['properties']}")

    resultados = {}
    for feature in features:
        props = feature["properties"]
        h3_id = props.get("h3_id")
        otras_claves = [k for k in props if k != "h3_id"]
        valor = props[otras_claves[0]] if otras_claves else None
        if h3_id:
            resultados[h3_id] = valor
    return resultados


def escribir_ndvi(driver, resolucion: int, resultados: dict) -> int:
    registros = [
        {"h3_id": h3_id, "resolucion": resolucion, "ndvi": valor}
        for h3_id, valor in resultados.items()
        if valor is not None
    ]

    query = """
    UNWIND $batch AS row
    MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: row.resolucion})
    SET c.ndvi_actual = row.ndvi
    """
    with driver.session() as session:
        for i in range(0, len(registros), BATCH_SIZE):
            session.run(query, batch=registros[i : i + BATCH_SIZE])

    return len(registros)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolucion", type=int, default=8, help="Resolución H3 (por defecto 8)")
    parser.add_argument(
        "--proyecto",
        default=os.getenv("GEE_PROJECT", "red-primavera"),
        help="ID del proyecto de Google Cloud para GEE. Por defecto lee GEE_PROJECT del .env o 'red-primavera'.",
    )
    parser.add_argument("--fecha-inicio", default=None)
    parser.add_argument("--fecha-fin", default=None)
    args = parser.parse_args()

    proyecto = args.proyecto
    if not proyecto:
        raise SystemExit(
            "Falta el proyecto de Google Cloud. Pásalo con --proyecto TU_PROYECTO "
            "o agrega GEE_PROJECT=TU_PROYECTO a tu .env."
        )

    fecha_fin = args.fecha_fin or date.today().isoformat()
    fecha_inicio = args.fecha_inicio or (date.today() - timedelta(days=90)).isoformat()

    print(f"Ventana temporal: {fecha_inicio} a {fecha_fin}")
    print(f"Proyecto GEE: {proyecto}")
    print("Inicializando Earth Engine...")
    inicializar_ee(proyecto)

    neo4j_uri = os.environ["NEO4J_URI"]
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ["NEO4J_PASSWORD"]
    driver = get_driver(neo4j_uri, neo4j_user, neo4j_password)

    print(f"Leyendo celdas H3 de resolución {args.resolucion} desde Neo4j...")
    h3_ids = leer_celdas(driver, args.resolucion)
    print(f"  {len(h3_ids)} celdas encontradas")

    if not h3_ids:
        print("No hay celdas para esta resolución. ¿Ya corriste el generador del grid H3?")
        driver.close()
        return

    print("Construyendo FeatureCollection de hexágonos...")
    fc = construir_feature_collection(h3_ids)
    bbox_general = fc.geometry().bounds()

    print("Construyendo composite de NDVI (Sentinel-2, con máscara de nubes SCL)...")
    ndvi_img = construir_imagen_ndvi(fecha_inicio, fecha_fin, bbox_general)

    print("Calculando NDVI promedio por celda (reduceRegions)...")
    ndvi_reducido = reducir_ndvi_por_celda(ndvi_img, fc)
    resultados = extraer_resultados(ndvi_reducido)
    print(f"  {len(resultados)} celdas con NDVI calculado")

    print("Escribiendo ndvi_actual en Neo4j...")
    n = escribir_ndvi(driver, args.resolucion, resultados)
    print(f"  {n} nodos CeldaH3 actualizados con éxito")

    driver.close()
    print("\n¡Listo!")


if __name__ == "__main__":
    main()