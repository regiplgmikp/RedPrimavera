"""
Endpoints del grafo de especies: nodos (Especie) + aristas (COOCURRE_CON),
con color y forma ya calculados del lado del backend -- así el frontend
(Sigma.js/Graphology, Semana 7 del plan) no tiene que duplicar esta lógica,
solo dibujar lo que le llega.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..database import get_session

router = APIRouter(prefix="/grafo", tags=["grafo"])

# Paleta fija para cluster_especies. Si Louvain encuentra más clústeres que
# colores en la paleta, se repiten (índice % len(paleta)) -- ajusta esta
# lista si quieres colores distintos.
PALETA_CLUSTERS = [
    "#4C9AFF",  # 0 azul
    "#FFC400",  # 1 amarillo
    "#C084FC",  # 2 lila
    "#FF8B3D",  # 3 naranja
    "#36B37E",  # 4 verde
    "#FF5C5C",  # 5 rojo
]

# reino_iconico -> (tipo simplificado, forma). Mismo criterio que el ETL
# (categoria_desde_iconic en 02_etl_especies_obser.py) para no divergir.
TIPO_POR_REINO = {
    "Plantae": ("flora", "square"),
    "Fungi": ("hongos", "triangle"),
}
DEFAULT_TIPO = ("fauna", "circle")


def color_por_cluster(cluster_id):
    if cluster_id is None:
        return "#888888"  # gris para especies sin clúster asignado (aisladas)
    return PALETA_CLUSTERS[cluster_id % len(PALETA_CLUSTERS)]


def limpiar_valor(valor):
    """
    Convierte NaN (float('nan'), que puede colarse desde datos de origen
    con huecos, ej. un CSV con celdas vacías) a None. Pydantic rechaza NaN
    donde espera un string, y con razón -- NaN no es texto ni "nada", es
    un valor numérico especial que rompe la validación.
    """
    if isinstance(valor, float) and valor != valor:  # NaN nunca es igual a sí mismo
        return None
    return valor


def limpiar_texto(valor) -> str | None:
    valor = limpiar_valor(valor)
    return valor if isinstance(valor, str) else None


def tipo_y_forma(reino_iconico):
    tipo, forma = TIPO_POR_REINO.get(reino_iconico, DEFAULT_TIPO)
    return tipo, forma


class NodoEspecie(BaseModel):
    id: str  # nombre_cientifico, es la llave primaria en Neo4j
    nombre_comun: str | None
    reino_iconico: str | None
    tipo: str
    forma: str
    cluster: int | None
    color: str


class AristaCoocurrencia(BaseModel):
    source: str
    target: str
    peso: int


class GrafoEspecies(BaseModel):
    nodos: list[NodoEspecie]
    aristas: list[AristaCoocurrencia]


@router.get("/especies", response_model=GrafoEspecies)
def grafo_especies(
    incluir_aisladas: bool = Query(
        False, description="Si es true, incluye especies sin ninguna relación COOCURRE_CON"
    ),
    session=Depends(get_session),
):
    """
    Devuelve el grafo de especies por co-ocurrencia espacial, con color
    (por cluster_especies, resultado de Louvain) y forma (por tipo
    taxonómico simplificado) ya calculados.
    """
    if incluir_aisladas:
        query_nodos = """
        MATCH (e:Especie)
        RETURN e.nombre_cientifico AS id, e.nombre_comun AS nombre_comun,
               e.reino_iconico AS reino_iconico, e.cluster_especies AS cluster
        """
    else:
        query_nodos = """
        MATCH (e:Especie)
        WHERE e.cluster_especies IS NOT NULL
        RETURN e.nombre_cientifico AS id, e.nombre_comun AS nombre_comun,
               e.reino_iconico AS reino_iconico, e.cluster_especies AS cluster
        """

    query_aristas = """
    MATCH (e1:Especie)-[r:COOCURRE_CON]-(e2:Especie)
    WHERE e1.nombre_cientifico < e2.nombre_cientifico
    RETURN e1.nombre_cientifico AS source, e2.nombre_cientifico AS target, r.peso AS peso
    """

    nodos = []
    for record in session.run(query_nodos):
        reino_iconico = limpiar_texto(record["reino_iconico"])
        tipo, forma = tipo_y_forma(reino_iconico)
        nodos.append(
            NodoEspecie(
                id=record["id"],
                nombre_comun=limpiar_texto(record["nombre_comun"]),
                reino_iconico=reino_iconico,
                tipo=tipo,
                forma=forma,
                cluster=record["cluster"],
                color=color_por_cluster(record["cluster"]),
            )
        )

    aristas = [
        AristaCoocurrencia(source=r["source"], target=r["target"], peso=r["peso"] or 1)
        for r in session.run(query_aristas)
    ]

    return GrafoEspecies(nodos=nodos, aristas=aristas)


@router.get("/especies/resumen")
def resumen_clusters(session=Depends(get_session)):
    """Conteo de especies por clúster -- útil para una leyenda en el frontend."""
    query = """
    MATCH (e:Especie)
    WHERE e.cluster_especies IS NOT NULL
    RETURN e.cluster_especies AS cluster, count(e) AS total
    ORDER BY cluster
    """
    return [
        {"cluster": r["cluster"], "total": r["total"], "color": color_por_cluster(r["cluster"])}
        for r in session.run(query)
    ]