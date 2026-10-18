"""
Capas de contexto para el mapa que no dependen de los filtros del IVC.

  GET /capas/poblacion   población estimada por celda H3 de resolución 8 (Kontur Population)
"""
from fastapi import APIRouter, Depends

from ..database import get_session

try:
    import h3
except ImportError:
    h3 = None

router = APIRouter(prefix="/capas", tags=["capas"])

ATRIBUCION = "Kontur Population (CC BY 4.0), https://data.humdata.org/dataset/kontur-population-mexico"


@router.get("/poblacion")
def capa_poblacion(session=Depends(get_session)):
    """
    Población estimada por celda de resolución 8 (la resolución nativa de Kontur; no se
    interpola a resolución 9 para no inventar detalle). Las celdas sin dato se omiten: en
    el frontend se distinguen de las celdas con población 0.
    """
    if h3 is None:
        raise RuntimeError("Falta instalar h3 en el backend: pip install h3")
    filas = session.run(
        "MATCH (c:CeldaH3 {resolucion: 8}) WHERE c.poblacion_kontur IS NOT NULL "
        "RETURN c.h3_id AS h3_id, c.poblacion_kontur AS poblacion"
    )
    celdas = [
        {"h3_id": r["h3_id"], "poblacion": r["poblacion"],
         "boundary": [[la, lo] for la, lo in h3.cell_to_boundary(r["h3_id"])]}
        for r in filas
    ]
    total = sum(c["poblacion"] for c in celdas)
    return {"resolucion": 8, "n_celdas": len(celdas), "poblacion_total": total,
            "atribucion": ATRIBUCION, "celdas": celdas}
