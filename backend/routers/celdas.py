"""
Endpoints de celdas H3 para el panel del mapa. Cada celda trae sus vértices
(boundary) ya calculados con h3-py del lado del servidor -- el frontend
(MapLibre/Deck.gl, Semana 6 del plan) recibe polígonos listos para dibujar,
sin tener que traer h3-js ni recalcular nada.

Estadísticas por zona (nucleo/zona_mab/fuera) agregadas por celda: cuántas
observaciones de cada zona cayeron ahí, y un color dominante para pintar
el hexágono de un solo vistazo en el mapa.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

try:
    import h3
except ImportError:
    h3 = None  # se valida al usar, para dar un mensaje de error claro

from ..database import get_session

router = APIRouter(prefix="/celdas", tags=["celdas"])

# Mismos tonos que ya se usan en Bloom (nucleo=lila, zona_mab=amarillo,
# fuera=naranja) -- consistencia visual entre Bloom y el futuro frontend.
COLOR_POR_ZONA = {
    "nucleo": "#C084FC",
    "zona_mab": "#FFC400",
    "fuera": "#FF8B3D",
}
COLOR_SIN_OBSERVACIONES = "#3A3A3A"  # celda sin ningún avistamiento todavía


class CeldaH3(BaseModel):
    h3_id: str
    resolucion: int
    boundary: list[list[float]]  # [[lat, lon], ...] vértices del hexágono
    total_observaciones: int
    n_nucleo: int
    n_zona_mab: int
    n_fuera: int
    zona_dominante: str | None
    color: str


def zona_dominante_y_color(n_nucleo: int, n_zona_mab: int, n_fuera: int):
    conteos = {"nucleo": n_nucleo, "zona_mab": n_zona_mab, "fuera": n_fuera}
    total = sum(conteos.values())
    if total == 0:
        return None, COLOR_SIN_OBSERVACIONES
    dominante = max(conteos, key=lambda zona: conteos[zona])
    return dominante, COLOR_POR_ZONA[dominante]


def celdas_en_bbox(bbox: tuple[float, float, float, float], resolucion: int) -> set[str]:
    if h3 is None:
        raise RuntimeError("Falta instalar h3 en el backend: pip install h3")

    west, south, east, north = bbox
    ring_latlon = [(south, west), (south, east), (north, east), (north, west)]
    poly = h3.LatLngPoly(ring_latlon)
    
    print("polygon_to_cells_experimental disponible:", hasattr(h3, "polygon_to_cells_experimental"))
    if hasattr(h3, "polygon_to_cells_experimental"):
        try:
            return set(
                h3.polygon_to_cells_experimental(
                    poly, resolucion, contain="overlap"
                )
            )
        except Exception:
            pass
    return set(h3.polygon_to_cells(poly, resolucion))



def dentro_de_bbox(
    lat: float, lon: float, bbox: tuple[float, float, float, float] | None
) -> bool:
    if bbox is None:
        return True
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def parsear_bbox(bbox_str: str | None) -> tuple[float, float, float, float] | None:
    if not bbox_str:
        return None
    partes = [float(x) for x in bbox_str.split(",")]
    if len(partes) != 4:
        raise ValueError("bbox debe tener 4 valores: west,south,east,north")
    return partes[0], partes[1], partes[2], partes[3]

@router.get("", response_model=list[CeldaH3])
def listar_celdas(
    resolucion: int = Query(8, description="Resolución H3 (8 o 9 en este proyecto)"),
    bbox: str | None = Query(
        None, description="Filtro opcional 'west,south,east,north' (grados decimales)"
    ),
    session=Depends(get_session),
):
    """Celdas H3 de la resolución pedida, con conteo de observaciones por zona."""
    if h3 is None:
        raise RuntimeError("Falta instalar h3 en el backend: pip install h3")

    bbox_tupla = parsear_bbox(bbox)

    params: dict[str, int | list[str]] = {"resolucion": resolucion}
    filtro_bbox = ""
    if bbox_tupla is not None:
        params["h3_ids"] = list(celdas_en_bbox(bbox_tupla, resolucion))
        filtro_bbox = " AND c.h3_id IN $h3_ids"

    query = f"""
    MATCH (c:CeldaH3 {{resolucion: $resolucion}})
    WHERE true{filtro_bbox}
    OPTIONAL MATCH (c)<-[:UBICADA_EN]-(o:Observacion)
    RETURN c.h3_id AS h3_id,
           sum(CASE WHEN o.zona = 'nucleo' THEN 1 ELSE 0 END) AS n_nucleo,
           sum(CASE WHEN o.zona = 'zona_mab' THEN 1 ELSE 0 END) AS n_zona_mab,
           sum(CASE WHEN o.zona = 'fuera' THEN 1 ELSE 0 END) AS n_fuera,
           count(o) AS total_observaciones
    """

    celdas = []
    for record in session.run(query, **params):
        h3_id = record["h3_id"]
        boundary = [[lat, lon] for lat, lon in h3.cell_to_boundary(h3_id)]
        dominante, color = zona_dominante_y_color(
            record["n_nucleo"], record["n_zona_mab"], record["n_fuera"]
        )

        celdas.append(
            CeldaH3(
                h3_id=h3_id,
                resolucion=resolucion,
                boundary=boundary,
                total_observaciones=record["total_observaciones"],
                n_nucleo=record["n_nucleo"],
                n_zona_mab=record["n_zona_mab"],
                n_fuera=record["n_fuera"],
                zona_dominante=dominante,
                color=color,
            )
        )

    return celdas