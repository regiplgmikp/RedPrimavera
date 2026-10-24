"""
Métricas topológicas de red para preparar los datos ANTES de enviarlos al cliente.

Este módulo es puro: recibe listas de filas ya extraídas de Neo4j y devuelve
diccionarios. No importa FastAPI ni neo4j, así que se prueba sin base de datos
(ver tests/test_metricas_red.py).

Dos redes:

1. Red de celdas (nodos = celdas H3 que pasan un filtro territorial; aristas =
   adyacencia hexagonal, relación ADYACENTE_A). Las métricas describen la
   CONECTIVIDAD del subconjunto filtrado, no del bosque entero:
     - grado:            cuántas celdas vecinas del subconjunto tiene.
     - intermediacion:   (betweenness) fracción de caminos más cortos entre pares
                         de celdas que pasan por esta celda. Alta = "cuello de
                         botella" que une zonas del subconjunto.
     - cercania:         (closeness) qué tan cerca está, en promedio, del resto de
                         su componente conectado. Alta = celda central.
     - es_articulacion:  true si quitarla desconecta el subconjunto.
     - componente:       id del bloque conectado (0 = el más grande) y su tamaño.

2. Red de especies (nodos = especies; arista = dos especies registradas en las
   mismas celdas, con peso = número de celdas compartidas dentro del filtro):
     - grado, fuerza (suma de pesos), centralidad_grado (grado normalizado),
     - intermediacion (con distancia = 1/peso: más celdas compartidas = más cerca),
     - comunidad (Louvain con semilla fija).

Todas las métricas se devuelven también normalizadas a [0, 1] (sufijo _norm)
por min-max, para que el frontend las use directo como tamaño o color sin
recalcular nada.

Intermediación aproximada: calcularla exacta cuesta O(nodos × aristas). Si hay
más de `max_exacto` nodos se estima muestreando `k` nodos origen con semilla
fija (resultado reproducible). El campo `aproximada` de los metadatos lo indica.
"""

from __future__ import annotations
from collections import Counter
from itertools import combinations

import networkx as nx
import numpy as np
from scipy.sparse.csgraph import shortest_path
np = None

SEMILLA = 42
MAX_EXACTO = 1500      # hasta aquí, intermediación exacta
K_MUESTRA = 400        # nodos origen cuando se aproxima


def _normalizar(valores: dict) -> dict:
    """Min-max a [0, 1]. Si todos son iguales (o no hay datos) devuelve 0.0."""
    if not valores:
        return {}
    lo, hi = min(valores.values()), max(valores.values())
    if hi == lo:
        return {k: 0.0 for k in valores}
    return {k: (v - lo) / (hi - lo) for k, v in valores.items()}


def _intermediacion(G: nx.Graph, weight=None, max_exacto=MAX_EXACTO, k=K_MUESTRA):
    n = G.number_of_nodes()
    if n == 0:
        return {}, False
    if n > max_exacto:
        return nx.betweenness_centrality(
            G, k=min(k, n), weight=weight, normalized=True, seed=SEMILLA
        ), True
    return nx.betweenness_centrality(G, weight=weight, normalized=True), False


# ---------------------------------------------------------------------------
# Red de celdas
# ---------------------------------------------------------------------------

def _cercania(G: nx.Graph) -> dict:
    """Cercanía exacta, igual que nx.closeness_centrality (con wf_improved),
    pero calculada con scipy para que no tarde segundos."""
    n = G.number_of_nodes()
    if n == 0:
        return {}
    if np is None:
        return nx.closeness_centrality(G)
    nodos = list(G.nodes)
    A = nx.to_scipy_sparse_array(G, nodelist=nodos, weight=None, format="csr")
    D = shortest_path(A, method="D", directed=False, unweighted=True)
    alcanzable = np.isfinite(D)
    n_alc = alcanzable.sum(axis=1)              # incluye a la propia celda
    suma = np.where(alcanzable, D, 0).sum(axis=1)
    c = np.zeros(n)
    ok = suma > 0
    c[ok] = ((n_alc[ok] - 1) / suma[ok]) * ((n_alc[ok] - 1) / (n - 1))
    return dict(zip(nodos, c.tolist()))

def metricas_celdas(celdas: list[dict], aristas: list[tuple[str, str]],
                    max_exacto=MAX_EXACTO, k=K_MUESTRA) -> dict:
    """
    celdas:  [{"h3_id": ..., ...atributos}], uno por celda que pasó el filtro.
    aristas: [(h3_a, h3_b), ...]. Se ignoran las que tocan celdas fuera del
             subconjunto y los duplicados/bucles (ADYACENTE_A está en ambos sentidos).
    Devuelve {"metricas": {h3_id: {...}}, "meta": {...}}.
    """
    G = nx.Graph()
    G.add_nodes_from(c["h3_id"] for c in celdas)
    for a, b in aristas:
        if a != b and a in G and b in G:
            G.add_edge(a, b)

    grado = dict(G.degree())
    interm, aprox = _intermediacion(G, None, max_exacto, k)
    cercania = _cercania(G)
    articulaciones = set(nx.articulation_points(G)) if G.number_of_nodes() else set()
    componentes = sorted(nx.connected_components(G), key=len, reverse=True)
    comp_id, comp_tam = {}, {}
    for i, comp in enumerate(componentes):
        for nodo in comp:
            comp_id[nodo], comp_tam[nodo] = i, len(comp)

    grado_n, interm_n, cerc_n = _normalizar(grado), _normalizar(interm), _normalizar(cercania)
    metricas = {
        h: {
            "grado": grado[h],
            "intermediacion": interm.get(h, 0.0),
            "intermediacion_norm": interm_n.get(h, 0.0),
            "cercania": cercania.get(h, 0.0),
            "cercania_norm": cerc_n.get(h, 0.0),
            "grado_norm": grado_n.get(h, 0.0),
            "es_articulacion": h in articulaciones,
            "componente": comp_id[h],
            "componente_tamano": comp_tam[h],
        }
        for h in G.nodes
    }
    meta = {
        "n_nodos": G.number_of_nodes(),
        "n_aristas": G.number_of_edges(),
        "n_componentes": len(componentes),
        "densidad": nx.density(G) if G.number_of_nodes() > 1 else 0.0,
        "n_articulaciones": len(articulaciones),
        "intermediacion_aproximada": aprox,
    }
    return {"metricas": metricas, "meta": meta}


# ---------------------------------------------------------------------------
# Red de especies por co-ocurrencia
# ---------------------------------------------------------------------------

MAX_ARISTAS_RED = 20000   # tope para que la red se pueda calcular y dibujar


def red_cooccurrencia(pares_celda_especie: list[tuple[str, str]],
                      min_celdas_compartidas: int = 1,
                      max_aristas: int = MAX_ARISTAS_RED) -> nx.Graph:
    """
    pares_celda_especie: [(h3_id, especie), ...] (se deduplican).
    Arista entre dos especies = nº de celdas del filtro donde ambas aparecen.
    Si el umbral pedido deja más de max_aristas aristas, se sube automáticamente
    (se conservan las más fuertes); el umbral usado queda en G.graph["umbral_efectivo"].
    """
    por_celda: dict[str, set[str]] = {}
    for h3_id, especie in pares_celda_especie:
        por_celda.setdefault(h3_id, set()).add(especie)

    pesos: Counter = Counter()
    for especies in por_celda.values():
        for a, b in combinations(sorted(especies), 2):
            pesos[(a, b)] += 1

    umbral = min_celdas_compartidas
    valores = [w for w in pesos.values() if w >= umbral]
    if len(valores) > max_aristas:
        valores.sort(reverse=True)
        umbral = valores[max_aristas] + 1   # deja a lo más max_aristas aristas

    G = nx.Graph()
    for especies in por_celda.values():
        G.add_nodes_from(especies)
    for (a, b), w in pesos.items():
        if w >= umbral:
            G.add_edge(a, b, peso=w)
    G.graph["umbral_efectivo"] = umbral
    return G

def metricas_especies(G: nx.Graph, max_exacto=800, k=K_MUESTRA) -> dict:
    n = G.number_of_nodes()
    if n == 0:
        return {"metricas": {}, "aristas": [], "meta": {
            "n_nodos": 0, "n_aristas": 0, "n_comunidades": 0, "modularidad": None,
            "intermediacion_aproximada": False}}

    grado = dict(G.degree())
    fuerza = dict(G.degree(weight="peso"))
    cent_grado = nx.degree_centrality(G)

    # distancia = 1/peso: más celdas compartidas => más cercanas
    H = nx.Graph()
    H.add_nodes_from(G.nodes)
    for a, b, d in G.edges(data=True):
        H.add_edge(a, b, dist=1.0 / d["peso"])
    interm, aprox = _intermediacion(H, "dist", max_exacto, k)

    comunidades, modularidad = [], None
    if G.number_of_edges() > 0:
        particion = nx.community.louvain_communities(G, weight="peso", seed=SEMILLA)
        modularidad = nx.community.modularity(G, particion, weight="peso")
        # Solo cuentan como comunidad los grupos de 2+ especies; las especies sin
        # ninguna arista en este filtro quedan con comunidad = None (no son "clústeres").
        comunidades = sorted((c for c in particion if len(c) >= 2), key=len, reverse=True)
    com_de = {e: i for i, c in enumerate(comunidades) for e in c}

    fuerza_n, interm_n = _normalizar(fuerza), _normalizar(interm)
    metricas = {
        e: {
            "grado": grado[e],
            "fuerza": fuerza[e],
            "fuerza_norm": fuerza_n.get(e, 0.0),
            "centralidad_grado": cent_grado[e],
            "intermediacion": interm.get(e, 0.0),
            "intermediacion_norm": interm_n.get(e, 0.0),
            "comunidad": com_de.get(e),   # None = especie aislada en este filtro
        }
        for e in G.nodes
    }
    aristas = [(a, b, d["peso"]) for a, b, d in G.edges(data=True)]
    meta = {
        "n_nodos": n,
        "n_aristas": G.number_of_edges(),
        "n_comunidades": len(comunidades),
        "n_aisladas": sum(1 for g in grado.values() if g == 0),
        "modularidad": modularidad,
        "intermediacion_aproximada": aprox,
    }
    return {"metricas": metricas, "aristas": aristas, "meta": meta}


def centroides_por_especie(pares_celda_especie, coords_celda):
    """
    Posición geográfica aproximada de cada especie: promedio de las celdas del filtro donde
    aparece. Sirve para dibujar la red SOBRE el mapa (sobreposición) -- es el centro de donde
    se ha visto, no un punto real de la especie.

    pares_celda_especie: [(h3_id, especie), ...]; coords_celda: {h3_id: (lat, lon)}.
    Devuelve {especie: {"lat": ..., "lon": ..., "n_celdas": ...}}.
    """
    celdas_por_especie = {}
    for h3_id, especie in pares_celda_especie:
        if h3_id in coords_celda:
            celdas_por_especie.setdefault(especie, set()).add(h3_id)
    out = {}
    for especie, celdas in celdas_por_especie.items():
        lats = [coords_celda[c][0] for c in celdas]
        lons = [coords_celda[c][1] for c in celdas]
        out[especie] = {"lat": sum(lats) / len(lats), "lon": sum(lons) / len(lons),
                        "n_celdas": len(celdas)}
    return out
