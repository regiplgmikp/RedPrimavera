"""Carga la población de Kontur Population en las CeldaH3 de resolución 8.

Kontur Population distribuye la población estimada ya sobre celdas H3 de resolución 8,
por eso se carga en res 8 y NO se reparte a res 9 (sería inventar detalle).

Fuente (descarga manual, no la hace este script):
    https://data.humdata.org/dataset/kontur-population-mexico   -> archivo .gpkg (o .gpkg.gz; descomprime primero)
    Licencia CC BY 4.0: hay que citar a Kontur (la API ya devuelve la atribución).
    Guárdalo, por ejemplo, en data/raw/kontur_population_MX.gpkg (data/raw está en .gitignore).

Qué hace:
    - Abre el GeoPackage con sqlite3 (un .gpkg es SQLite; no necesita geopandas).
    - Busca la tabla que tenga una columna de índice H3 y otra de población, y se adapta
      al nombre real de las columnas (h3 / h3_id / hex..., population / pop...).
    - Solo toma las celdas que YA existen en Neo4j (CeldaH3 res 8): no crea celdas nuevas.
    - Escribe CeldaH3.poblacion_kontur y reporta cuántas celdas quedaron sin dato.

Uso:
    python etls/etl_poblacion_kontur.py --gpkg data/raw/kontur_population_MX.gpkg --dry-run
    python etls/etl_poblacion_kontur.py --gpkg data/raw/kontur_population_MX.gpkg
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
load_dotenv()

try:
    import h3
except ImportError:
    h3 = None

LOTE = 500


def encontrar_tabla(con):
    """Devuelve (tabla, col_h3, col_pob) buscando por nombres de columna comunes."""
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' "
        "AND name NOT LIKE 'rtree_%' AND name NOT LIKE 'sqlite_%'")]
    for t in tablas:
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
        c_h3 = next((c for c in cols if c.lower() in ("h3", "h3_id", "h3index", "hex", "index")), None)
        c_pop = next((c for c in cols if c.lower() in ("population", "pop", "poblacion")), None)
        if c_h3 and c_pop:
            return t, c_h3, c_pop
    raise SystemExit(f"No encontré una tabla con columnas de H3 y población. Tablas: {tablas}")


def a_cadena_h3(valor):
    """Kontur guarda el índice como texto hexadecimal; por si viniera como entero."""
    if isinstance(valor, int):
        if h3 is None:
            raise SystemExit("El índice H3 viene como entero y falta instalar h3")
        return h3.int_to_str(valor)
    return str(valor).strip().lower()


def leer_poblacion(gpkg: Path) -> dict:
    con = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        tabla, c_h3, c_pop = encontrar_tabla(con)
        print(f"Tabla '{tabla}' (H3: {c_h3}, población: {c_pop})")
        return {a_cadena_h3(h): float(p) for h, p in
                con.execute(f'SELECT "{c_h3}", "{c_pop}" FROM "{tabla}" WHERE "{c_pop}" IS NOT NULL')}
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pob = leer_poblacion(Path(a.gpkg))
    res_archivo = {h3.get_resolution(k) for k in list(pob)[:50]} if h3 else {"?"}
    print(f"{len(pob)} celdas en el archivo; resolución(es) de muestra: {sorted(res_archivo)}")

    from utils.neo4j_conn import get_driver
    driver = get_driver(os.environ["NEO4J_URI"], os.environ.get("NEO4J_USER", "neo4j"),
                        os.environ["NEO4J_PASSWORD"])
    with driver.session() as s:
        ids = [r["h"] for r in s.run("MATCH (c:CeldaH3 {resolucion: 8}) RETURN c.h3_id AS h")]
    registros = [{"h3_id": h, "pob": pob[h]} for h in ids if h in pob]
    sin_dato = len(ids) - len(registros)
    total = sum(r["pob"] for r in registros)
    print(f"Celdas res 8 en Neo4j: {len(ids)} | con población: {len(registros)} | sin dato: {sin_dato}")
    print(f"Población total en las celdas del ANP y su entorno: {total:,.0f}")
    if registros:
        top = sorted(registros, key=lambda r: -r["pob"])[:5]
        print("Más pobladas:", [(r["h3_id"], round(r["pob"])) for r in top])
    if a.dry_run or not registros:
        print("--dry-run: no se escribió nada" if a.dry_run else "Nada que escribir")
        driver.close(); return
    with driver.session() as s:
        for i in range(0, len(registros), LOTE):
            s.run("UNWIND $b AS row MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: 8}) "
                  "SET c.poblacion_kontur = row.pob, c.fuente_poblacion = 'kontur_population'",
                  b=registros[i:i + LOTE])
    print(f"{len(registros)} celdas actualizadas")
    driver.close()


if __name__ == "__main__":
    main()
