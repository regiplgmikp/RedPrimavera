"""
Verifica /subgrafos contra el servidor y contra la geometría H3 (sin dependencias extra).

  1) uvicorn backend.main:app --reload        (desde la raíz del proyecto, otra terminal)
  2) python tests/probar_subgrafos.py [http://127.0.0.1:8000]

Comprueba:
  - sin filtros, res 8: 489 nodos (o los que haya) y que ADYACENTE_A en la base coincida con la
    adyacencia geométrica de H3 (si no coincide, la relación está incompleta en Neo4j);
  - que un filtro devuelva un subconjunto del total y que sus aristas solo unan nodos del subconjunto;
  - que las métricas vengan normalizadas en [0,1];
  - que la red de especies responda y reporte comunidades.
"""
import json, sys, urllib.parse, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
try:
    import h3
except ImportError:
    h3 = None


def get(ruta, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    with urllib.request.urlopen(f"{BASE}{ruta}?{q}", timeout=120) as r:
        return json.load(r)


def check(ok, msg):
    print(("OK   " if ok else "FALLA"), msg)
    return ok


todo = get("/subgrafos/celdas", resolucion=8)
ids = {n["h3_id"] for n in todo["nodos"]}
check(len(ids) > 0, f"sin filtros: {len(ids)} nodos, {len(todo['aristas'])} aristas, "
                     f"{todo['meta']['n_componentes']} componente(s)")

if h3:
    esperadas = {tuple(sorted((a, b))) for a in ids for b in h3.grid_ring(a, 1) if b in ids}
    en_db = {tuple(sorted((e["source"], e["target"]))) for e in todo["aristas"]}
    check(esperadas == en_db,
          f"ADYACENTE_A coincide con H3 (base {len(en_db)} vs geometría {len(esperadas)})")
else:
    print("(h3 no instalado: se omite la comparación geométrica)")

sub = get("/subgrafos/celdas", resolucion=8, ivc_min=0.6)
ids_sub = {n["h3_id"] for n in sub["nodos"]}
check(ids_sub <= ids and 0 < len(ids_sub) < len(ids),
      f"ivc_min=0.6: {len(ids_sub)} de {len(ids)} celdas, {sub['meta']['n_componentes']} componente(s), "
      f"{sub['meta']['n_articulaciones']} articulaciones")
check(all(e["source"] in ids_sub and e["target"] in ids_sub for e in sub["aristas"]),
      "las aristas del subgrafo solo unen celdas del subgrafo")
check(all(0 <= n["metricas"]["intermediacion_norm"] <= 1 for n in sub["nodos"]),
      "intermediacion_norm en [0, 1]")
if sub["nodos"]:
    top = sorted(sub["nodos"], key=lambda n: -n["metricas"]["intermediacion"])[:3]
    print("     top intermediación:", [(n["h3_id"], round(n["metricas"]["intermediacion"], 3)) for n in top])

comb = get("/subgrafos/celdas", resolucion=9, ivc_min=0.5, distancia_camino_max=1000, en_predio="false")
print(f"     combinado (ivc>=0.5, camino<=1000 m, sin predio): {len(comb['nodos'])} celdas")

esp = get("/subgrafos/especies", resolucion=8, ivc_min=0.6, min_celdas_compartidas=2)
check(esp["meta"]["n_nodos"] > 0, f"especies en zonas ivc>=0.6: {esp['meta']['n_nodos']} nodos, "
      f"{esp['meta']['n_aristas']} aristas, {esp['meta']['n_comunidades']} comunidades")
if esp["nodos"]:
    top = sorted(esp["nodos"], key=lambda n: -n["metricas"]["intermediacion"])[:5]
    print("     especies más intermedias:", [n["id"] for n in top])
