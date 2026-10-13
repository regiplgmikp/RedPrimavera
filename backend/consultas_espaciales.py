"""
Construcción de consultas Cypher con filtros territoriales sobre CeldaH3.

Reglas de seguridad y rendimiento:
  - Los VALORES de los filtros siempre van como parámetros ($nombre); nunca se
    concatenan en el texto de la consulta. Lo único que se compone dinámicamente
    son condiciones fijas escritas aquí.
  - El filtro por bbox se resuelve en Python a una lista de h3_id (como ya hace
    routers/celdas.py) y llega como `c.h3_id IN $h3_ids`, que usa el índice.
  - Un filtro activo sobre una propiedad que una celda no tiene (p. ej. celdas
    sin IVC por falta de NDVI) EXCLUYE esa celda: en Cypher `null >= 0.5` no es
    verdadero. Es intencional: no se inventan valores.

Filtros disponibles (todos opcionales):
    ivc_min / ivc_max                  c.indice_vulnerabilidad
    frecuencia_min / frecuencia_max    c.frecuencia_incendios_anual
    ultimo_incendio_desde              c.ultimo_incendio_anio >= año
    ndvi_min / ndvi_max                c.ndvi_actual
    dosel_min                          c.canopy_height_mean
    distancia_camino_min / _max (m)    min(CERCANA_A.distancia_m)
    en_predio (bool)                   tiene DENTRO_DE -> Predio
    institucion (nombre)               el predio es PROPIETARIA_DE esa institución
    bbox                               (west, south, east, north), vía h3_ids
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FiltroCeldas:
    resolucion: int = 8
    ivc_min: float | None = None
    ivc_max: float | None = None
    frecuencia_min: float | None = None
    frecuencia_max: float | None = None
    ultimo_incendio_desde: int | None = None
    ndvi_min: float | None = None
    ndvi_max: float | None = None
    dosel_min: float | None = None
    distancia_camino_min: float | None = None
    distancia_camino_max: float | None = None
    en_predio: bool | None = None
    institucion: str | None = None
    h3_ids: list[str] | None = None   # resultado del bbox (None = sin filtro)

    def aplicados(self) -> dict:
        """Solo los filtros realmente activos (para devolverlos al cliente)."""
        d = {k: v for k, v in self.__dict__.items()
             if v is not None and k not in ("resolucion", "h3_ids")}
        d["resolucion"] = self.resolucion
        if self.h3_ids is not None:
            d["bbox_celdas"] = len(self.h3_ids)
        return d


# (campo del filtro, condición Cypher sobre la celda c)
_COND_CELDA = [
    ("ivc_min", "c.indice_vulnerabilidad >= $ivc_min"),
    ("ivc_max", "c.indice_vulnerabilidad <= $ivc_max"),
    ("frecuencia_min", "c.frecuencia_incendios_anual >= $frecuencia_min"),
    ("frecuencia_max", "c.frecuencia_incendios_anual <= $frecuencia_max"),
    ("ultimo_incendio_desde", "c.ultimo_incendio_anio >= $ultimo_incendio_desde"),
    ("ndvi_min", "c.ndvi_actual >= $ndvi_min"),
    ("ndvi_max", "c.ndvi_actual <= $ndvi_max"),
    ("dosel_min", "c.canopy_height_mean >= $dosel_min"),
    ("h3_ids", "c.h3_id IN $h3_ids"),
]

# condiciones que requieren agregados (se evalúan después del WITH)
_COND_DERIVADA = [
    ("distancia_camino_min", "distancia_camino >= $distancia_camino_min"),
    ("distancia_camino_max", "distancia_camino <= $distancia_camino_max"),
    ("institucion", "$institucion IN instituciones"),
]


def parametros(f: FiltroCeldas) -> dict:
    p = {"resolucion": f.resolucion}
    for campo, _ in _COND_CELDA + _COND_DERIVADA:
        valor = getattr(f, campo)
        if valor is not None:
            p[campo] = valor
    return p


def bloque_celdas_filtradas(f: FiltroCeldas) -> str:
    """
    Fragmento Cypher que deja en el flujo, por cada celda que pasa el filtro:
        c, distancia_camino, predios (ids), instituciones (nombres)
    Se le concatena un RETURN u otro MATCH.
    """
    where_c = [cond for campo, cond in _COND_CELDA if getattr(f, campo) is not None]
    where_d = [cond for campo, cond in _COND_DERIVADA if getattr(f, campo) is not None]
    if f.en_predio is True:
        where_d.append("size(predios) > 0")
    elif f.en_predio is False:
        where_d.append("size(predios) = 0")

    partes = ["MATCH (c:CeldaH3 {resolucion: $resolucion})"]
    if where_c:
        partes.append("WHERE " + " AND ".join(where_c))
    partes += [
        "OPTIONAL MATCH (c)-[rc:CERCANA_A]->(:Camino)",
        "WITH c, min(rc.distancia_m) AS distancia_camino",
        "OPTIONAL MATCH (c)-[:DENTRO_DE]->(p:Predio)",
        "OPTIONAL MATCH (p)<-[:PROPIETARIA_DE]-(i:Institucion)",
        "WITH c, distancia_camino,"
        " collect(DISTINCT p.id) AS predios, collect(DISTINCT i.nombre) AS instituciones",
    ]
    if where_d:
        partes.append("WHERE " + " AND ".join(where_d))
    return "\n".join(partes)


def consulta_nodos_celdas(f: FiltroCeldas) -> str:
    """Celdas que pasan el filtro, con atributos territoriales y conteo de biodiversidad."""
    return bloque_celdas_filtradas(f) + """
OPTIONAL MATCH (c)<-[:UBICADA_EN]-(o:Observacion)
OPTIONAL MATCH (o)-[:PERTENECE_A]->(e:Especie)
RETURN c.h3_id AS h3_id,
       c.indice_vulnerabilidad AS ivc,
       c.subindice_exposicion AS exposicion,
       c.subindice_sensibilidad AS sensibilidad,
       c.frecuencia_incendios_anual AS frecuencia_incendios,
       c.periodo_retorno_anios AS periodo_retorno,
       c.ultimo_incendio_anio AS ultimo_incendio,
       c.ndvi_actual AS ndvi,
       c.canopy_height_mean AS dosel,
       distancia_camino,
       size(predios) > 0 AS en_predio,
       instituciones,
       count(DISTINCT o) AS n_observaciones,
       count(DISTINCT e) AS n_especies
"""


# Aristas de adyacencia entre las celdas ya seleccionadas ($ids). Las dos
# direcciones de ADYACENTE_A se reducen a una (a.h3_id < b.h3_id).
CONSULTA_ARISTAS_CELDAS = """
MATCH (a:CeldaH3 {resolucion: $resolucion})-[:ADYACENTE_A]-(b:CeldaH3 {resolucion: $resolucion})
WHERE a.h3_id IN $ids AND b.h3_id IN $ids AND a.h3_id < b.h3_id
RETURN DISTINCT a.h3_id AS source, b.h3_id AS target
"""


def consulta_pares_celda_especie(f: FiltroCeldas, zona: bool, categoria: bool) -> str:
    """(celda, especie) dentro del filtro territorial; opcionalmente por zona/categoría de la observación."""
    cond = []
    if zona:
        cond.append("o.zona = $zona")
    if categoria:
        cond.append("o.categoria = $categoria")
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    return bloque_celdas_filtradas(f) + f"""
MATCH (c)<-[:UBICADA_EN]-(o:Observacion)-[:PERTENECE_A]->(e:Especie)
{where}
RETURN DISTINCT c.h3_id AS h3_id, e.nombre_cientifico AS especie
"""


CONSULTA_META_ESPECIES = """
MATCH (e:Especie)
WHERE e.nombre_cientifico IN $nombres
RETURN e.nombre_cientifico AS id, e.nombre_comun AS nombre_comun,
       e.reino_iconico AS reino_iconico
"""
