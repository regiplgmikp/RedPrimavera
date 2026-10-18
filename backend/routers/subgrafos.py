"""
Subgrafos territoriales con métricas de red ya calculadas.

El cliente (Deck.gl / Sigma.js) recibe nodos y aristas listos, con las métricas
topológicas (grado, intermediación, cercanía, comunidad...) ya incluidas y
normalizadas a [0, 1]; no recalcula nada.

  GET /subgrafos/celdas    celdas H3 filtradas por atributos territoriales + adyacencia
  GET /subgrafos/especies  red de co-ocurrencia de especies dentro de ese mismo filtro
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..analisis import metricas_red as mr
from ..consultas_espaciales import (
    CONSULTA_ARISTAS_CELDAS,
    CONSULTA_CELDAS_ESPECIE,
    CONSULTA_META_ESPECIES,
    FiltroCeldas,
    consulta_nodos_celdas,
    consulta_pares_celda_especie,
    parametros,
)
from ..database import get_session
from .celdas import celdas_en_bbox, parsear_bbox

try:
    import h3
except ImportError:
    h3 = None

router = APIRouter(prefix="/subgrafos", tags=["subgrafos"])

MAX_CELDAS = 4000  # tope de seguridad: res 9 completa son 2,991


# ---------------------------------------------------------------- modelos
class MetricasCelda(BaseModel):
    grado: int
    grado_norm: float
    intermediacion: float
    intermediacion_norm: float
    cercania: float
    cercania_norm: float
    es_articulacion: bool
    componente: int
    componente_tamano: int


class NodoCelda(BaseModel):
    h3_id: str
    boundary: list[list[float]]  # [[lat, lon], ...]
    ivc: float | None
    exposicion: float | None
    sensibilidad: float | None
    frecuencia_incendios: float | None
    periodo_retorno: float | None
    ultimo_incendio: int | None
    ndvi: float | None
    dosel: float | None
    poblacion: float | None
    distancia_camino: float | None
    en_predio: bool
    instituciones: list[str]
    n_observaciones: int
    n_especies: int
    metricas: MetricasCelda


class AristaSimple(BaseModel):
    source: str
    target: str


class SubgrafoCeldas(BaseModel):
    filtros: dict
    meta: dict
    nodos: list[NodoCelda]
    aristas: list[AristaSimple]


class MetricasEspecie(BaseModel):
    grado: int
    fuerza: int
    fuerza_norm: float
    centralidad_grado: float
    intermediacion: float
    intermediacion_norm: float
    comunidad: int | None


class NodoEspecieSub(BaseModel):
    id: str
    nombre_comun: str | None
    reino_iconico: str | None   # taxón icónico de iNaturalist (Plantae, Aves, Insecta...)
    tipo: str                   # flora | fauna | hongos (misma regla que routers/grafo.py)
    lat: float | None           # centro de las celdas del filtro donde aparece (para sobreponer al mapa)
    lon: float | None
    n_celdas: int
    metricas: MetricasEspecie


class AristaPeso(BaseModel):
    source: str
    target: str
    peso: int


class SubgrafoEspecies(BaseModel):
    filtros: dict
    meta: dict
    nodos: list[NodoEspecieSub]
    aristas: list[AristaPeso]


# ---------------------------------------------------------------- filtros
def filtros_dependency(
    resolucion: int = Query(8, ge=8, le=9, description="Resolución H3 (8 o 9)"),
    ivc_min: float | None = Query(None, ge=0, le=1),
    ivc_max: float | None = Query(None, ge=0, le=1),
    frecuencia_min: float | None = Query(None, ge=0, le=1, description="Incendios por año observado"),
    frecuencia_max: float | None = Query(None, ge=0, le=1),
    ultimo_incendio_desde: int | None = Query(None, ge=1990, le=2100),
    ndvi_min: float | None = Query(None, ge=-1, le=1),
    ndvi_max: float | None = Query(None, ge=-1, le=1),
    dosel_min: float | None = Query(None, ge=0, description="Altura media del dosel (m)"),
    distancia_camino_min: float | None = Query(None, ge=0, description="metros"),
    distancia_camino_max: float | None = Query(None, ge=0, description="metros"),
    en_predio: bool | None = Query(None, description="true = solo celdas traslapadas con un predio"),
    institucion: str | None = Query(None, max_length=200, description="Nombre exacto de la institución"),
    bbox: str | None = Query(None, description="west,south,east,north (grados)"),
) -> FiltroCeldas:
    try:
        bbox_t = parsear_bbox(bbox)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    h3_ids = sorted(celdas_en_bbox(bbox_t, resolucion)) if bbox_t else None
    return FiltroCeldas(
        resolucion=resolucion, ivc_min=ivc_min, ivc_max=ivc_max,
        frecuencia_min=frecuencia_min, frecuencia_max=frecuencia_max,
        ultimo_incendio_desde=ultimo_incendio_desde,
        ndvi_min=ndvi_min, ndvi_max=ndvi_max, dosel_min=dosel_min,
        distancia_camino_min=distancia_camino_min, distancia_camino_max=distancia_camino_max,
        en_predio=en_predio, institucion=institucion, h3_ids=h3_ids,
    )


def _limpiar(x):
    return None if isinstance(x, float) and x != x else x


# ---------------------------------------------------------------- endpoints
@router.get("/celdas", response_model=SubgrafoCeldas)
def subgrafo_celdas(filtro: FiltroCeldas = Depends(filtros_dependency),
                    session=Depends(get_session)):
    """
    Celdas que cumplen los filtros territoriales, conectadas por adyacencia, con
    métricas topológicas calculadas SOBRE ESE SUBCONJUNTO. Ejemplo: celdas con
    IVC alto (>= 0.7) y cerca de caminos (<= 500 m): la intermediación alta marca
    las que unen los focos de riesgo entre sí.
    """
    if h3 is None:
        raise RuntimeError("Falta instalar h3 en el backend: pip install h3")
    registros = [r.data() for r in session.run(consulta_nodos_celdas(filtro), parametros(filtro))]
    if len(registros) > MAX_CELDAS:
        raise HTTPException(422, f"El filtro devuelve {len(registros)} celdas (máx {MAX_CELDAS}).")

    ids = [r["h3_id"] for r in registros]
    aristas = []
    if ids:
        aristas = [(r["source"], r["target"]) for r in session.run(
            CONSULTA_ARISTAS_CELDAS, resolucion=filtro.resolucion, ids=ids)]

    res = mr.metricas_celdas(registros, aristas)
    nodos = []
    for r in registros:
        boundary = [[lat, lon] for lat, lon in h3.cell_to_boundary(r["h3_id"])]
        nodos.append(NodoCelda(
            h3_id=r["h3_id"], boundary=boundary,
            ivc=_limpiar(r["ivc"]), exposicion=_limpiar(r["exposicion"]),
            sensibilidad=_limpiar(r["sensibilidad"]),
            frecuencia_incendios=_limpiar(r["frecuencia_incendios"]),
            periodo_retorno=_limpiar(r["periodo_retorno"]),
            ultimo_incendio=r["ultimo_incendio"], ndvi=_limpiar(r["ndvi"]),
            dosel=_limpiar(r["dosel"]), poblacion=_limpiar(r["poblacion"]),
            distancia_camino=_limpiar(r["distancia_camino"]),
            en_predio=bool(r["en_predio"]), instituciones=r["instituciones"] or [],
            n_observaciones=r["n_observaciones"], n_especies=r["n_especies"],
            metricas=MetricasCelda(**res["metricas"][r["h3_id"]]),
        ))
    uniq = sorted({tuple(sorted(a)) for a in aristas})
    return SubgrafoCeldas(
        filtros=filtro.aplicados(), meta=res["meta"], nodos=nodos,
        aristas=[AristaSimple(source=a, target=b) for a, b in uniq],
    )


@router.get("/especies", response_model=SubgrafoEspecies)
def subgrafo_especies(
    filtro: FiltroCeldas = Depends(filtros_dependency),
    zona: str | None = Query(None, pattern="^(nucleo|zona_mab|fuera)$",
                             description="Solo observaciones de esa zona"),
    categoria: str | None = Query(None, max_length=60, description="Categoría de la observación"),
    min_celdas_compartidas: int = Query(1, ge=1, le=50,
                                        description="Mínimo de celdas compartidas para dibujar una arista"),
    session=Depends(get_session),
):
    """
    Red de co-ocurrencia de especies RESTRINGIDA al territorio filtrado: dos
    especies se conectan si aparecen en las mismas celdas que cumplen el filtro
    (peso = nº de celdas compartidas). Responde preguntas como: ¿qué especies
    son más centrales en las zonas de alta vulnerabilidad?
    """
    params = parametros(filtro)
    if zona:
        params["zona"] = zona
    if categoria:
        params["categoria"] = categoria
    q = consulta_pares_celda_especie(filtro, zona=bool(zona), categoria=bool(categoria))
    pares = [(r["h3_id"], r["especie"]) for r in session.run(q, params)]

    G = mr.red_cooccurrencia(pares, min_celdas_compartidas)
    res = mr.metricas_especies(G)

    nombres = list(res["metricas"].keys())
    info = {}
    if nombres:
        info = {r["id"]: r for r in session.run(CONSULTA_META_ESPECIES, nombres=nombres)}
    coords = {h: h3.cell_to_latlng(h) for h in {p[0] for p in pares}}
    centros = mr.centroides_por_especie(pares, coords)
    nodos = []
    for nombre, m in res["metricas"].items():
        i = info.get(nombre)
        c = centros.get(nombre)
        reino = _limpiar(i["reino_iconico"]) if i else None
        nodos.append(NodoEspecieSub(
            tipo=("flora" if reino == "Plantae" else "hongos" if reino == "Fungi" else "fauna"),
            lat=c["lat"] if c else None, lon=c["lon"] if c else None,
            n_celdas=c["n_celdas"] if c else 0,
            id=nombre,
            nombre_comun=_limpiar(i["nombre_comun"]) if i else None,
            reino_iconico=_limpiar(i["reino_iconico"]) if i else None,
            metricas=MetricasEspecie(**m),
        ))
    res["meta"]["n_celdas_filtro"] = len({p[0] for p in pares})
    return SubgrafoEspecies(
        filtros={**filtro.aplicados(), **({"zona": zona} if zona else {}),
                 **({"categoria": categoria} if categoria else {}),
                 "min_celdas_compartidas": min_celdas_compartidas},
        meta=res["meta"], nodos=nodos,
        aristas=[AristaPeso(source=a, target=b, peso=w) for a, b, w in res["aristas"]],
    )


class CeldaObservada(BaseModel):
    h3_id: str
    boundary: list[list[float]]  # [[lat, lon], ...]
    n_observaciones: int


class ObservacionesEspecie(BaseModel):
    especie: str
    resolucion: int
    n_observaciones: int
    celdas: list[CeldaObservada]


@router.get("/especies/observaciones", response_model=ObservacionesEspecie)
def observaciones_especie(
    nombre: str = Query(..., min_length=1, max_length=200, description="Nombre científico exacto"),
    resolucion: int = Query(8, ge=8, le=9),
    zona: str | None = Query(None, pattern="^(nucleo|zona_mab|fuera)$"),
    session=Depends(get_session),
):
    """Celdas donde se observó una especie (con el nº de observaciones por celda), para iluminarlas en el mapa."""
    filas = list(session.run(CONSULTA_CELDAS_ESPECIE, resolucion=resolucion, nombre=nombre, zona=zona))
    celdas = [
        CeldaObservada(
            h3_id=r["h3_id"],
            boundary=[[lat, lon] for lat, lon in h3.cell_to_boundary(r["h3_id"])],
            n_observaciones=r["n_observaciones"],
        )
        for r in filas
    ]
    return ObservacionesEspecie(
        especie=nombre, resolucion=resolucion,
        n_observaciones=sum(c.n_observaciones for c in celdas), celdas=celdas,
    )
