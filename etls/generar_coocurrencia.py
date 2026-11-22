"""Genera (o regenera) la red de co-ocurrencia de especies COOCURRE_CON en Neo4j.

Regla (la misma que usa el panel, backend/analisis/metricas_red.py):
    Dos especies se conectan si fueron registradas en las mismas celdas H3.
    peso = número de celdas que comparten.

Qué hace:
    - Lee los pares (celda, especie) de TODAS las observaciones en la resolución
      indicada.
    - Construye la red con metricas_red.red_cooccurrencia (mismo código del panel).
      Si quedan más de --max-aristas aristas, el umbral de celdas compartidas sube
      solo y se conservan las conexiones más fuertes (igual que en el panel).
    - Con --aplicar: borra las COOCURRE_CON anteriores, quita cluster_especies de
      todas las especies (quedó desactualizado) y escribe la red nueva.

Por defecto NO escribe nada (solo reporta). Después de aplicar, corre
etls/clustering_especies.py para recalcular las comunidades.

Uso (desde la raíz del proyecto):
    python etls/generar_coocurrencia.py --resolucion 8
    python etls/generar_coocurrencia.py --resolucion 8 --aplicar
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver  # noqa: E402
from backend.analisis import metricas_red as mr  # noqa: E402

load_dotenv()
BATCH = 1000


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resolucion", type=int, default=8, choices=[8, 9])
    parser.add_argument("--min-celdas", type=int, default=1,
                        help="Mínimo de celdas compartidas para crear una conexión")
    parser.add_argument("--max-aristas", type=int, default=mr.MAX_ARISTAS_RED,
                        help=f"Tope de conexiones (por defecto {mr.MAX_ARISTAS_RED}, igual que el panel)")
    parser.add_argument("--aplicar", action="store_true", help="Escribe la red en Neo4j")
    args = parser.parse_args()

    driver = get_driver(os.environ["NEO4J_URI"], os.environ.get("NEO4J_USER", "neo4j"),
                        os.environ["NEO4J_PASSWORD"])

    print(f"Leyendo pares (celda, especie) en resolución {args.resolucion} ...")
    with driver.session() as s:
        pares = [(r["h3_id"], r["especie"]) for r in s.run("""
            MATCH (c:CeldaH3 {resolucion: $res})<-[:UBICADA_EN]-(:Observacion)
                  -[:PERTENECE_A]->(e:Especie)
            RETURN DISTINCT c.h3_id AS h3_id, e.nombre_cientifico AS especie
        """, res=args.resolucion)]
    print(f"  {len(pares):,} pares; {len({p[0] for p in pares}):,} celdas; "
          f"{len({p[1] for p in pares}):,} especies")

    G = mr.red_cooccurrencia(pares, args.min_celdas, args.max_aristas)
    umbral = G.graph["umbral_efectivo"]
    aisladas = sum(1 for _, g in G.degree() if g == 0)
    print(f"\nRed resultante: {G.number_of_nodes():,} especies, {G.number_of_edges():,} conexiones")
    print(f"  Umbral efectivo de celdas compartidas: {umbral}"
          + ("  (subió solo por el tope de conexiones)" if umbral > args.min_celdas else ""))
    print(f"  Especies sin ninguna conexión: {aisladas:,}")

    if not args.aplicar:
        print("\nModo revisión: no se escribió nada. Si todo se ve bien, corre con --aplicar.")
        driver.close()
        return

    aristas = [{"a": a, "b": b, "peso": d["peso"]} for a, b, d in G.edges(data=True)]
    with driver.session() as s:
        print("\nBorrando COOCURRE_CON anteriores ...")
        while True:
            n = s.run("""
                MATCH (:Especie)-[r:COOCURRE_CON]-(:Especie)
                WITH DISTINCT r LIMIT 10000
                DELETE r
                RETURN count(*) AS n
            """).single()["n"]
            if n == 0:
                break
        s.run("MATCH (e:Especie) REMOVE e.cluster_especies")

        print("Escribiendo la red nueva ...")
        for i in range(0, len(aristas), BATCH):
            s.run("""
                UNWIND $lote AS r
                MATCH (a:Especie {nombre_cientifico: r.a})
                MATCH (b:Especie {nombre_cientifico: r.b})
                MERGE (a)-[c:COOCURRE_CON]->(b)
                SET c.peso = r.peso, c.resolucion = $res
            """, lote=aristas[i:i + BATCH], res=args.resolucion)
        total = s.run("MATCH ()-[r:COOCURRE_CON]->() RETURN count(r) AS n").single()["n"]

    print(f"Listo: {total:,} relaciones COOCURRE_CON en la base.")
    print("Siguiente paso: python etls/clustering_especies.py")
    driver.close()


if __name__ == "__main__":
    main()