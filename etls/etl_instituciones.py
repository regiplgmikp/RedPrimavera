"""Carga los predios universitarios (shapefile de los profesores) a Neo4j.

Requisitos:
        - Python con geopandas, shapely, h3, neo4j y python-dotenv instalados.
        - El shapefile completo en data/raw/ (.shp, .dbf, .shx y .prj juntos,
            con el mismo nombre base).
        - Grid H3 ya cargado en Neo4j (generar_grid_h3.py).
        - NEO4J_URI, NEO4J_USER y NEO4J_PASSWORD en el entorno o en .env.

Qué hace:
        - Institucion: un nodo por propietario (MERGE por nombre). Solo se
            guarda `nombre`; `tipo` y `labor` quedan vacíos hasta contar con
            información confiable de las instituciones.
        - Predio: un nodo por polígono (id, area_ha, geometria_wkt en EPSG:4326).
        - (Institucion)-[:PROPIETARIA_DE]->(Predio)
        - (CeldaH3)-[:DENTRO_DE]->(Predio) para las celdas H3 que intersectan
            el polígono (incluye celdas que solo lo tocan parcialmente).

Notas:
        - Es idempotente: nodos y relaciones se crean con MERGE, y antes de
            recrear DENTRO_DE / PROPIETARIA_DE se borran las relaciones previas
            del mismo predio, para no dejar relaciones viejas si cambia la
            geometría o el propietario.
        - Usa --dry-run para ver qué cargaría sin tocar Neo4j.
        - NO crea la relación ACTUA_SOBRE: la fórmula sigue pendiente.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver

try:
    import geopandas as gpd
except ImportError:
    sys.exit("Falta geopandas. Instala con: pip install geopandas")

try:
    import h3
except ImportError:
    sys.exit("Falta h3. Instala con: pip install h3")

CRS_METRICO = "EPSG:32613"  # UTM 13N: para calcular áreas en metros


def cargar_predios(path_shp: str):
    """Lee el shapefile y devuelve una lista de dicts, uno por predio."""
    if not Path(path_shp).exists():
        sys.exit(f"No existe {path_shp}. Revisa la ruta (--shp).")

    gdf = gpd.read_file(path_shp)
    if gdf.crs is None:
        sys.exit("El shapefile no trae CRS. Falta el archivo .prj junto al .shp.")
    if "Propietari" not in gdf.columns:
        sys.exit(f"No encuentro la columna 'Propietari'. Columnas: {list(gdf.columns)}")

    # Área calculada desde geometría proyectada (metros), no desde el campo del archivo
    areas_ha = (gdf.to_crs(CRS_METRICO).geometry.area / 10000).round(2).tolist()

    gdf = gdf.to_crs(epsg=4326).reset_index(drop=True)
    try:
        gdf["geometry"] = gdf.geometry.force_2d()  # geopandas >= 1.0
    except AttributeError:
        import shapely

        gdf["geometry"] = gpd.GeoSeries(
            shapely.force_2d(list(gdf.geometry)), index=gdf.index, crs=gdf.crs
        )

    predios = []
    for i, row in gdf.iterrows():
        oid = int(row["OBJECTID"]) if "OBJECTID" in gdf.columns else i + 1
        predios.append({
            "id": f"predio_{oid}",
            "propietario": str(row["Propietari"]).strip(),
            "area_ha": float(areas_ha[i]),
            "geometria_wkt": row.geometry.wkt,
            "geom": row.geometry,
        })
    return predios


def celdas_h3_del_predio(geom, resolucion: int) -> set:
    """Celdas H3 que intersectan el polígono (contain='overlap' si está disponible)."""
    poligonos = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    celdas = set()
    for poly in poligonos:
        # h3-py v4 espera (lat, lon); shapely trae (lon, lat)
        exterior = [(lat, lon) for lon, lat in poly.exterior.coords]
        huecos = [[(lat, lon) for lon, lat in ring.coords] for ring in poly.interiors]
        h3poly = h3.LatLngPoly(exterior, *huecos)

        if hasattr(h3, "polygon_to_cells_experimental"):
            try:
                celdas |= set(h3.polygon_to_cells_experimental(h3poly, resolucion, contain="overlap"))
                continue
            except Exception as e:
                print(f"  polygon_to_cells_experimental falló ({e}), usando polygon_to_cells")
        celdas |= set(h3.polygon_to_cells(h3poly, resolucion))

    if not celdas:  # predio más chico que una celda: al menos la celda de su centroide
        c = geom.centroid
        celdas.add(h3.latlng_to_cell(c.y, c.x, resolucion))
    return celdas


def cargar_a_neo4j(uri, user, password, predios, celdas_por_res):
    driver = get_driver(uri, user, password)
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT predio_id IF NOT EXISTS "
            "FOR (p:Predio) REQUIRE p.id IS UNIQUE"
        )

        propietarios = sorted({p["propietario"] for p in predios})
        session.run(
            """
            UNWIND $nombres AS nombre
            MERGE (:Institucion {nombre: nombre})
            """,
            nombres=propietarios,
        )
        print(f"{len(propietarios)} nodos Institucion asegurados.")

        session.run(
            """
            UNWIND $batch AS row
            MERGE (p:Predio {id: row.id})
            SET p.area_ha = row.area_ha, p.geometria_wkt = row.geometria_wkt
            WITH p, row
            OPTIONAL MATCH (:Institucion)-[old:PROPIETARIA_DE]->(p)
            DELETE old
            WITH p, row
            MATCH (i:Institucion {nombre: row.propietario})
            MERGE (i)-[:PROPIETARIA_DE]->(p)
            """,
            batch=[
                {k: v for k, v in p.items() if k != "geom"} for p in predios
            ],
        )
        print(f"{len(predios)} nodos Predio con relación PROPIETARIA_DE.")

        for res, por_predio in celdas_por_res.items():
            for predio_id, h3_ids in por_predio.items():
                session.run(
                    """
                    MATCH (:CeldaH3 {resolucion: $res})-[r:DENTRO_DE]->(:Predio {id: $id})
                    DELETE r
                    """,
                    res=res, id=predio_id,
                )
                n = session.run(
                    """
                    UNWIND $h3_ids AS h3_id
                    MATCH (c:CeldaH3 {h3_id: h3_id, resolucion: $res})
                    MATCH (p:Predio {id: $id})
                    MERGE (c)-[:DENTRO_DE]->(p)
                    RETURN count(*) AS n
                    """,
                    h3_ids=list(h3_ids), res=res, id=predio_id,
                ).single()["n"]
                print(f"  {predio_id} res {res}: {n} de {len(h3_ids)} celdas calculadas "
                      f"existen en Neo4j y quedaron ligadas")
    driver.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shp", default="data/raw/PrediosUniversitariosCompletosUTM.shp",
        help="Ruta al .shp de los predios universitarios",
    )
    parser.add_argument("--resoluciones", type=int, nargs="+", default=[8, 9])
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra qué se cargaría; no escribe en Neo4j")
    args = parser.parse_args()

    predios = cargar_predios(args.shp)
    print(f"{len(predios)} predios leídos de {args.shp}:")
    for p in predios:
        print(f"  {p['id']}: {p['propietario']} ({p['area_ha']} ha)")

    celdas_por_res = {}
    for res in args.resoluciones:
        celdas_por_res[res] = {
            p["id"]: celdas_h3_del_predio(p["geom"], res) for p in predios
        }
        resumen = ", ".join(f"{pid}={len(c)}" for pid, c in celdas_por_res[res].items())
        print(f"Resolución {res}, celdas H3 por predio: {resumen}")

    if args.dry_run:
        print("\n--dry-run: no se escribió nada en Neo4j.")
        return

    cargar_a_neo4j(args.uri, args.user, args.password, predios, celdas_por_res)
    print("\nListo.")


if __name__ == "__main__":
    main()