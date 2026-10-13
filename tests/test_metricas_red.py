"""Pruebas de backend/analisis/metricas_red.py -- sin Neo4j ni FastAPI.
Correr desde la raíz:  python -m pytest tests/test_metricas_red.py   (o  python tests/test_metricas_red.py)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.analisis import metricas_red as mr


def test_camino_de_5_celdas():
    # a-b-c-d-e: c es el cuello de botella; b, c, d son puntos de articulación
    celdas = [{"h3_id": x} for x in "abcde"]
    r = mr.metricas_celdas(celdas, [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("b", "a")])
    m = r["metricas"]
    assert r["meta"]["n_aristas"] == 4 and r["meta"]["n_componentes"] == 1
    assert m["c"]["intermediacion"] > m["b"]["intermediacion"] > m["a"]["intermediacion"] == 0
    assert m["c"]["intermediacion_norm"] == 1.0
    assert {h for h, v in m.items() if v["es_articulacion"]} == {"b", "c", "d"}
    assert m["c"]["cercania_norm"] == 1.0


def test_componentes_y_aristas_fuera_del_subconjunto():
    celdas = [{"h3_id": x} for x in ["a", "b", "c", "z"]]
    r = mr.metricas_celdas(celdas, [("a", "b"), ("b", "c"), ("c", "x")])  # x no está en el filtro
    assert r["meta"]["n_aristas"] == 2
    assert r["metricas"]["z"]["componente_tamano"] == 1
    assert r["metricas"]["a"]["componente"] == 0 and r["metricas"]["z"]["componente"] == 1


def test_vacio():
    assert mr.metricas_celdas([], [])["meta"]["n_nodos"] == 0
    assert mr.metricas_especies(mr.red_cooccurrencia([]))["metricas"] == {}


def test_cooccurrencia_pesos():
    pares = [("c1", "A"), ("c1", "B"), ("c1", "C"), ("c2", "A"), ("c2", "B"), ("c3", "C"), ("c1", "A")]
    G = mr.red_cooccurrencia(pares)
    assert G["A"]["B"]["peso"] == 2 and G["A"]["C"]["peso"] == 1
    G2 = mr.red_cooccurrencia(pares, min_celdas_compartidas=2)
    assert list(G2.edges) == [("A", "B")] and "C" in G2  # C queda aislada, no desaparece


def test_metricas_especies_y_comunidades():
    # dos triángulos unidos por un puente X-Y (peso 1); X e Y deben tener la mayor intermediación
    pares = []
    for i in range(3):
        pares += [(f"t1_{i}", e) for e in ("A", "B", "X")]
        pares += [(f"t2_{i}", e) for e in ("C", "D", "Y")]
    pares += [("puente", "X"), ("puente", "Y")]
    r = mr.metricas_especies(mr.red_cooccurrencia(pares))
    m = r["metricas"]
    assert r["meta"]["n_comunidades"] == 2
    assert max(m, key=lambda e: m[e]["intermediacion"]) in ("X", "Y")
    assert m["A"]["comunidad"] == m["B"]["comunidad"] != m["C"]["comunidad"]
    assert 0 < r["meta"]["modularidad"] < 1


def test_reproducible_y_aproximada():
    import random
    random.seed(1)
    ids = [str(i) for i in range(60)]
    ar = [(random.choice(ids), random.choice(ids)) for _ in range(200)]
    a = mr.metricas_celdas([{"h3_id": i} for i in ids], ar, max_exacto=10, k=20)
    b = mr.metricas_celdas([{"h3_id": i} for i in ids], ar, max_exacto=10, k=20)
    assert a["meta"]["intermediacion_aproximada"] is True and a == b


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
