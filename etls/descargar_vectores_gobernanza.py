"""Descarga y genera capas vectoriales de gobernanza e hidrografía para La Primavera:
1. Municipios oficiales (Zapopan, Tala, Tlajomulco de Zúñiga, El Arenal).
2. Trazo hidrográfico del sector Arroyo Las Tortugas.

Salidas:
    - data/municipios_primavera.geojson
    - data/arroyo_las_tortugas.geojson
"""

import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
import osmnx as ox
from shapely.geometry import box

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MUNICIPIOS = [
    "Zapopan, Jalisco, Mexico",
    "Tala, Jalisco, Mexico",
    "Tlajomulco de Zúñiga, Jalisco, Mexico",
    "El Arenal, Jalisco, Mexico",
]


def extraer_municipios():
    print("\n--- Extrayendo polígonos municipales oficiales ---")
    gdfs = []
    for mun in MUNICIPIOS:
        nombre_corto = mun.split(",")[0].strip()
        print(f"  Consultando límite de: {nombre_corto}...")
        try:
            gdf = ox.geocode_to_gdf(mun)
            gdf["municipio"] = nombre_corto
            gdfs.append(gdf[["municipio", "geometry"]])
        except Exception as e:
            print(f"  Error consultando {mun}: {e}")

    if not gdfs:
        print("Error: No se pudo extraer ningún municipio.")
        return None

    gdf_municipios = gpd.GeoDataFrame(
        pd.concat(gdfs, ignore_index=True),
        crs=gdfs[0].crs,
    ).to_crs(epsg=4326)

    ruta_salida = DATA_DIR / "municipios_primavera.geojson"
    gdf_municipios.to_file(ruta_salida, driver="GeoJSON")
    print(f"  Guardado: {ruta_salida} ({len(gdf_municipios)} municipios)")
    return gdf_municipios

def main():
    print("Iniciando extracción vectorial con OSMnx...")
    extraer_municipios()
    print("\n¡Proceso finalizado!")


if __name__ == "__main__":
    main()