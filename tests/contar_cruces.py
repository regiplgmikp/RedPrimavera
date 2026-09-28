import json
import geopandas as gpd
from shapely.geometry import shape

poly = shape(json.load(open("data/boundary/La_Primavera.geojson", encoding="utf-8"))["features"][0]["geometry"])
g = gpd.read_file("data/raw/caminos_primavera.geojson")
cruzan = g[g.intersects(poly) & ~g.within(poly)]
print(f"Caminos que cruzan el borde: {len(cruzan)}")
print(cruzan["highway"].value_counts().head(10))