"""
Compara ADYACENTE_A en Neo4j con la adyacencia geométrica de H3 y, si se pide,
crea SOLO las relaciones que faltan (MERGE: no duplica nada).

Desde la raíz del proyecto:
    python tests/reparar_adyacencia.py --resolucion 8            # solo diagnostica
    python tests/reparar_adyacencia.py --resolucion 8 --aplicar  # crea las faltantes
    (repetir con --resolucion 9)

Crea ambas direcciones, igual que etls/generar_grid_h3.py. No borra nada: si en la
base hay relaciones que NO son vecinas geométricas, las lista para que las revises.
"""
import argparse, os, sys
from pathlib import Path

import h3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver

load_dotenv()
ap = argparse.ArgumentParser()
ap.add_argument("--resolucion", type=int, default=8)
ap.add_argument("--aplicar", action="store_true")
a = ap.parse_args()

driver = get_driver(os.environ["NEO4J_URI"], os.environ.get("NEO4J_USER", "neo4j"),
                    os.environ["NEO4J_PASSWORD"])
res = a.resolucion
with driver.session() as s:
    ids = {r["h"] for r in s.run(
        "MATCH (c:CeldaH3 {resolucion:$r}) RETURN c.h3_id AS h", r=res)}
    en_db = {frozenset((r["a"], r["b"])) for r in s.run(
        """MATCH (x:CeldaH3 {resolucion:$r})-[:ADYACENTE_A]-(y:CeldaH3 {resolucion:$r})
           WHERE x.h3_id < y.h3_id RETURN x.h3_id AS a, y.h3_id AS b""", r=res)}

    geo = {frozenset((c, v)) for c in ids for v in h3.grid_ring(c, 1) if v in ids}
    faltan, sobran = geo - en_db, en_db - geo
    print(f"res {res}: {len(ids)} celdas | en base {len(en_db)} | geométricas {len(geo)}")
    print(f"  faltan en la base: {len(faltan)} | en la base pero no vecinas: {len(sobran)}")
    for par in sorted(map(sorted, faltan)):
        print("   falta:", par[0], "<->", par[1])
    for par in sorted(map(sorted, sobran)):
        print("   sobra:", par[0], "<->", par[1])

    if a.aplicar and faltan:
        lote = [{"a": x, "b": y} for p in faltan for x, y in (sorted(p), sorted(p)[::-1])]
        s.run("""UNWIND $b AS par
                 MATCH (x:CeldaH3 {h3_id: par.a, resolucion: $r})
                 MATCH (y:CeldaH3 {h3_id: par.b, resolucion: $r})
                 MERGE (x)-[:ADYACENTE_A {resolucion: $r}]->(y)""", b=lote, r=res)
        print(f"  creadas {len(faltan)} adyacencias (ambas direcciones)")
    elif faltan:
        print("  (solo diagnóstico; usa --aplicar para crearlas)")
driver.close()
