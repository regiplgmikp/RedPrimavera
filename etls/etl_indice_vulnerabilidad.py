"""Calcula el Índice de Vulnerabilidad Compuesto (IVC) por celda H3 (marco IPCC, 2007).

Requisitos:
        - Python con pandas, numpy, neo4j y python-dotenv instalados.
        - Neo4j con las celdas ya enriquecidas por los otros ETLs:
            ndvi_actual (etl_gee_ndvi), canopy_height_mean y cobertura_arbolada_pct
            (etl_gee_estructura), frecuencia_incendios_anual (etl_gee_incendios),
            relaciones CERCANA_A (etl_caminos) y DENTRO_DE (etl_instituciones).
        - NEO4J_URI, NEO4J_USER y NEO4J_PASSWORD en el entorno o en .env.

Fórmulas (norm(X) = clip((X - p5) / (p95 - p5), 0, 1)):

    Exposición      E  = 0.6 * norm(frecuencia_incendios_anual)
                         + 0.4 * (1 - norm(distancia al camino más cercano))
    Sensibilidad    S  = 0.5 * norm(canopy_height_mean * cobertura_arbolada_pct / 100)
                         + 0.5 * (1 - norm(ndvi_actual))
    Cap. adaptativa AC = 1 si la celda tiene DENTRO_DE hacia un Predio, 0 si no
    IVC = (0.5 * E + 0.5 * S) * (1 - 0.2 * AC)

Qué escribe en cada CeldaH3: indice_vulnerabilidad, subindice_exposicion,
subindice_sensibilidad, subindice_adaptativo, los cuatro componentes
(exposicion_incendios, exposicion_caminos, sensibilidad_biomasa,
sensibilidad_estres) e ivc_parametros (texto con los pesos, para reproducir).

Notas:
        - NO se rellenan datos faltantes: si a una celda le falta ndvi, dosel,
            cobertura, frecuencia o camino, su IVC queda sin valor y se reporta cuántas
            fueron. Rellenar con valores fijos inventaba datos y además movía los
            percentiles p5/p95 de todas las demás celdas.
        - Los percentiles se calculan por separado en cada resolución.
        - AC es binaria y DENTRO_DE es por intersección: una celda que apenas toca
            un predio recibe AC = 1 (limitación conocida, sobre todo en res 8).
        - Al final se imprime un análisis de sensibilidad (Spearman del ranking de
            celdas contra variantes de pesos) para poder defender los pesos.
        - Usa --dry-run para calcular e imprimir el resumen sin escribir en Neo4j.
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver

BATCH_SIZE = 500
P_MIN, P_MAX = 5, 95
COLUMNAS_NUMERICAS = [
    "frecuencia_incendios", "distancia_camino", "canopy_height",
    "cobertura_arbolada", "ndvi_actual",
]

PESOS = {
    "e_incendios": 0.6, "e_caminos": 0.4,
    "s_biomasa": 0.5, "s_estres": 0.5,
    "e": 0.5, "s": 0.5,
}
ATENUACION_AC = 0.2

VARIANTES_SENSIBILIDAD = [
    ("E: incendios 0.5 / caminos 0.5", {"e_incendios": 0.5, "e_caminos": 0.5}, None),
    ("E: incendios 0.7 / caminos 0.3", {"e_incendios": 0.7, "e_caminos": 0.3}, None),
    ("S: biomasa 0.6 / estrés 0.4", {"s_biomasa": 0.6, "s_estres": 0.4}, None),
    ("S: biomasa 0.4 / estrés 0.6", {"s_biomasa": 0.4, "s_estres": 0.6}, None),
    ("E 0.6 / S 0.4", {"e": 0.6, "s": 0.4}, None),
    ("E 0.4 / S 0.6", {"e": 0.4, "s": 0.6}, None),
    ("Sin atenuación por AC", {}, 0.0),
    ("Atenuación AC 0.4", {}, 0.4),
]


def normalizar_percentiles(serie: pd.Series, p_min=P_MIN, p_max=P_MAX) -> pd.Series:
    """Escala a [0, 1] con percentiles para recortar outliers. Respeta los NaN."""
    validos = serie.dropna()
    if validos.empty:
        return pd.Series(np.nan, index=serie.index)
    val_min, val_max = np.percentile(validos, [p_min, p_max])
    if val_max == val_min:
        return serie.where(serie.isna(), 0.0)  # 0 donde hay dato, NaN donde no
    return ((serie - val_min) / (val_max - val_min)).clip(0.0, 1.0)


def extraer_datos_celdas(driver, resolucion: int) -> pd.DataFrame:
    """Variables biofísicas, distancia a camino y pertenencia a predios por celda."""
    query = """
    MATCH (c:CeldaH3 {resolucion: $res})
    OPTIONAL MATCH (c)-[rc:CERCANA_A]->(:Camino)
    WITH c, min(rc.distancia_m) AS distancia_camino
    OPTIONAL MATCH (c)-[:DENTRO_DE]->(p:Predio)
    WITH c, distancia_camino, count(DISTINCT p) AS n_predios
    RETURN c.h3_id AS h3_id,
           c.frecuencia_incendios_anual AS frecuencia_incendios,
           distancia_camino,
           c.canopy_height_mean AS canopy_height,
           c.cobertura_arbolada_pct AS cobertura_arbolada,
           c.ndvi_actual AS ndvi_actual,
           n_predios > 0 AS en_predio
    """
    with driver.session() as session:
        df = pd.DataFrame([dict(r) for r in session.run(query, res=resolucion)])
    if df.empty:
        return df
    for col in COLUMNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce")  # None -> NaN, sin rellenar
    df["en_predio"] = df["en_predio"].astype(bool)
    return df


def calcular_metricas_ivc(df: pd.DataFrame, pesos=PESOS, atenuacion=ATENUACION_AC) -> pd.DataFrame:
    out = df.copy()

    # 1. Exposición
    n_freq = normalizar_percentiles(out["frecuencia_incendios"])
    n_dist = normalizar_percentiles(out["distancia_camino"])
    out["exposicion_incendios"] = n_freq
    out["exposicion_caminos"] = 1.0 - n_dist  # más cerca de un camino = más exposición
    out["subindice_exposicion"] = (
        pesos["e_incendios"] * out["exposicion_incendios"]
        + pesos["e_caminos"] * out["exposicion_caminos"]
    )

    # 2. Sensibilidad
    out["biomasa"] = out["canopy_height"] * (out["cobertura_arbolada"] / 100.0)
    out["sensibilidad_biomasa"] = normalizar_percentiles(out["biomasa"])
    out["sensibilidad_estres"] = 1.0 - normalizar_percentiles(out["ndvi_actual"])
    out["subindice_sensibilidad"] = (
        pesos["s_biomasa"] * out["sensibilidad_biomasa"]
        + pesos["s_estres"] * out["sensibilidad_estres"]
    )

    # 3. Capacidad adaptativa
    out["subindice_adaptativo"] = out["en_predio"].astype(float)

    # 4. Índice final
    base = pesos["e"] * out["subindice_exposicion"] + pesos["s"] * out["subindice_sensibilidad"]
    out["indice_vulnerabilidad"] = base * (1.0 - atenuacion * out["subindice_adaptativo"])
    return out


def imprimir_resumen(df: pd.DataFrame):
    n = len(df)
    completas = int(df["indice_vulnerabilidad"].notna().sum())
    print(f"  {n} celdas; {completas} con IVC completo")
    etiquetas = {
        "frecuencia_incendios": "frecuencia de incendios", "distancia_camino": "distancia a camino",
        "canopy_height": "altura de dosel", "cobertura_arbolada": "cobertura arbolada",
        "ndvi_actual": "NDVI",
    }
    for col, etiqueta in etiquetas.items():
        faltan = int(df[col].isna().sum())
        if faltan:
            print(f"    sin {etiqueta}: {faltan} celdas")

    print("  Percentiles usados (p5, p95):")
    for col, etiqueta in [("frecuencia_incendios", "frecuencia_incendios_anual"),
                          ("distancia_camino", "distancia_m"),
                          ("biomasa", "biomasa (dosel x cobertura)"),
                          ("ndvi_actual", "ndvi_actual")]:
        v = df[col].dropna()
        if not v.empty:
            lo, hi = np.percentile(v, [P_MIN, P_MAX])
            print(f"    {etiqueta}: {lo:.4g}, {hi:.4g}")

    if completas:
        print(df[["indice_vulnerabilidad", "subindice_exposicion", "subindice_sensibilidad"]]
              .describe().round(3).to_string())
        print(f"  Celdas con capacidad adaptativa = 1: {int(df['subindice_adaptativo'].sum())}")
        print("  Top 10 celdas por IVC:")
        top = df.nlargest(10, "indice_vulnerabilidad")
        for _, r in top.iterrows():
            print(f"    {r['h3_id']:<18} IVC {r['indice_vulnerabilidad']:.3f} | "
                  f"E {r['subindice_exposicion']:.3f} | S {r['subindice_sensibilidad']:.3f} | "
                  f"AC {int(r['subindice_adaptativo'])}")


def imprimir_sensibilidad(df: pd.DataFrame, base: pd.Series, atenuacion: float):
    print("  Sensibilidad a los pesos (Spearman del ranking vs. el IVC base; >0.95 = estable):")
    for nombre, cambios, atenuacion_var in VARIANTES_SENSIBILIDAD:
        pesos = {**PESOS, **cambios}
        att = atenuacion if atenuacion_var is None else atenuacion_var
        variante = calcular_metricas_ivc(df, pesos=pesos, atenuacion=att)["indice_vulnerabilidad"]
        # Spearman = Pearson sobre rangos; así no depende de scipy
        print(f"    {nombre:<34} rho = {base.rank().corr(variante.rank()):.3f}")


def persistir_neo4j(driver, df: pd.DataFrame, resolucion: int, parametros: str):
    query = """
    UNWIND $batch AS row
    MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: $res})
    SET c.indice_vulnerabilidad = row.ivc,
        c.subindice_exposicion = row.exp,
        c.subindice_sensibilidad = row.sens,
        c.subindice_adaptativo = row.adapt,
        c.exposicion_incendios = row.e_inc,
        c.exposicion_caminos = row.e_cam,
        c.sensibilidad_biomasa = row.s_bio,
        c.sensibilidad_estres = row.s_est,
        c.ivc_parametros = $params
    """

    def v(x):  # NaN -> None (Neo4j quita la propiedad en vez de guardar un NaN)
        return None if pd.isna(x) else round(float(x), 4)

    registros = [
        {
            "h3_id": r["h3_id"],
            "ivc": v(r["indice_vulnerabilidad"]),
            "exp": v(r["subindice_exposicion"]),
            "sens": v(r["subindice_sensibilidad"]),
            "adapt": v(r["subindice_adaptativo"]),
            "e_inc": v(r["exposicion_incendios"]),
            "e_cam": v(r["exposicion_caminos"]),
            "s_bio": v(r["sensibilidad_biomasa"]),
            "s_est": v(r["sensibilidad_estres"]),
        }
        for _, r in df.iterrows()
    ]
    with driver.session() as session:
        for i in range(0, len(registros), BATCH_SIZE):
            session.run(query, batch=registros[i:i + BATCH_SIZE], res=resolucion, params=parametros)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resoluciones", type=int, nargs="+", default=[8, 9],
                        help="Resoluciones H3 a calcular (por defecto 8 y 9)")
    parser.add_argument("--atenuacion", type=float, default=ATENUACION_AC,
                        help="Reducción máxima del IVC por capacidad adaptativa (0.2 = hasta 20%%)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcula y muestra el resumen sin escribir en Neo4j")
    args = parser.parse_args()

    driver = get_driver(os.environ["NEO4J_URI"], os.environ.get("NEO4J_USER", "neo4j"),
                        os.environ["NEO4J_PASSWORD"])
    parametros = (
        f"E=0.6*frec+0.4*(1-dist); S=0.5*biomasa+0.5*(1-ndvi); "
        f"IVC=(0.5E+0.5S)*(1-{args.atenuacion}*AC); norm p{P_MIN}-p{P_MAX}"
    )

    for res in args.resoluciones:
        print(f"\nResolución {res}: extrayendo datos de CeldaH3...")
        df = extraer_datos_celdas(driver, res)
        if df.empty:
            print("  No se encontraron celdas de esta resolución.")
            continue

        df = calcular_metricas_ivc(df, atenuacion=args.atenuacion)
        imprimir_resumen(df)
        imprimir_sensibilidad(df, df["indice_vulnerabilidad"], args.atenuacion)

        if args.dry_run:
            continue
        persistir_neo4j(driver, df, res, parametros)
        print(f"  {len(df)} celdas actualizadas en Neo4j")

    driver.close()
    print("\n--dry-run: no se escribió nada en Neo4j." if args.dry_run else "\n¡Completado con éxito!")


if __name__ == "__main__":
    main()