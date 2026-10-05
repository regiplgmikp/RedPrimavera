"""Detecta cicatrices de incendio por año (Landsat, dNBR) y calcula frecuencia
y periodo de retorno por celda H3.

Requisitos:
        - Python con earthengine-api, h3, neo4j y python-dotenv instalados.
        - Una cuenta de Google Earth Engine autenticada y un proyecto de Google
            Cloud indicado por GEE_PROJECT o por --proyecto.
        - Una instancia de Neo4j accesible con NEO4J_URI, NEO4J_USER y
            NEO4J_PASSWORD en el entorno o en un archivo .env.
        - Celdas CeldaH3 creadas previamente para la resolucion solicitada.

Qué hace:
        - Para cada año Y compara el NBR (Normalized Burn Ratio) de una ventana
            de fechas en Y-1 contra la MISMA ventana en Y (dNBR = NBR_Y-1 - NBR_Y).
            Al comparar la misma época del año se evita confundir la fenología
            (verde/seco) con un incendio. El "año" Y cubre, en la práctica, los
            incendios ocurridos entre las dos ventanas (incluye la temporada
            fuerte de febrero a mayo).
        - VENTANA ADAPTATIVA: se prueba primero la ventana angosta (--ventana,
            por defecto 15-mayo a 30-junio). Si para ese año la cobertura de
            datos válidos no alcanza --min-cobertura-anual, se repite el año
            con una ventana más ancha, moviendo el INICIO más temprano dentro
            de la temporada seca (nunca se mueve el fin hacia la temporada de
            lluvias, para no diluir la cicatriz con el reverdecimiento de
            junio-agosto, que es justo lo que pasó al principio al probar con
            una ventana fija 02-01 a 08-31: arregló años con huecos de nubes
            pero aplanó la señal de años con buena cobertura). Se documenta
            qué ventana terminó usando cada año (ventana_usada).
        - Enmascara nubes y sombras (QA_PIXEL) y deja solo cobertura vegetal
            (ESA WorldCover: arbolado, matorral y pastizal) para no confundir
            cosecha o labranza con quemas.
        - Resta a cada año un "offset" (mediana del dNBR en el área de estudio,
            que es casi todo vegetación sin quemar) para absorber diferencias de
            humedad entre años.
        - Por celda calcula la fracción de píxeles con dNBR >= umbral y la
            fracción de datos válidos. Una celda-año es "quemada" si la fracción
            quemada >= --umbral-fraccion y "sin dato" si los datos válidos son
            menores a --min-valido (esos años NO cuentan como observados).
        - Escribe en Neo4j: nodos EventoDisturbio (uno por año con detección),
            relaciones (CeldaH3)-[:AFECTADO_POR {severidad, fraccion_quemada}]->
            (EventoDisturbio) y, en cada CeldaH3, n_incendios, anios_observados,
            frecuencia_incendios_anual, periodo_retorno_anios y
            ultimo_incendio_anio.

Notas:
        - LOS UMBRALES POR DEFECTO SON UN PUNTO DE PARTIDA, NO UN RESULTADO.
            Al final se imprime una tabla de sensibilidad contra incendios de
            referencia (2005 y 2018) para calibrarlos; úsala antes de escribir.
        - Con un registro finito, una celda sin incendios NO tiene periodo de
            retorno infinito: queda sin periodo_retorno_anios y con
            anios_observados, para poder expresarlo como "mayor a N años".
        - Usa --dry-run para calcular y ver el resumen sin escribir en Neo4j.
        - Los resultados por año se guardan en cache/ (ignorada por git) para
            poder reanudar si se interrumpe y recalcular umbrales sin volver a
            consultar GEE.
        - Requiere conectividad con Google Earth Engine y Neo4j.
"""

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import ee
import h3
from dotenv import load_dotenv

# Permitir importar utils/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.neo4j_conn import get_driver

# Cargar variables del archivo .env
load_dotenv()

BATCH_CELDAS_GEE = 400
BATCH_NEO4J = 200
ESCALA_LANDSAT_M = 30
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

# Umbrales de dNBR que se evalúan a la vez (para calibrar sin volver a GEE)
UMBRALES_DNBR = [0.10, 0.15, 0.20, 0.27, 0.35, 0.44]

# Para la ventana adaptativa: si el año no alcanza cobertura, se mueve el
# INICIO a una de estas fechas (siempre más temprano, nunca se toca el fin),
# de la más angosta a la más ancha, probando solo las que empiecen antes que
# la ventana base.
PASOS_INICIO_VENTANA = ["04-01", "02-15", "01-01"]

# Landsat Collection 2 Level 2: (banda NIR, banda SWIR2)
COLECCIONES_LANDSAT = {
    "LANDSAT/LT05/C02/T1_L2": ("SR_B4", "SR_B7"),
    "LANDSAT/LE07/C02/T1_L2": ("SR_B4", "SR_B7"),
    "LANDSAT/LC08/C02/T1_L2": ("SR_B5", "SR_B7"),
    "LANDSAT/LC09/C02/T1_L2": ("SR_B5", "SR_B7"),
}

# ESA WorldCover: 10 arbolado, 20 matorral, 30 pastizal
CLASES_VEGETACION = [10, 20, 30]

# Incendios de referencia para validar. Solo 2005 y 2018 tienen superficie
# conocida en las fuentes revisadas; 2008 y 2023 son solo de presencia.
REFERENCIA_AREA_HA = {
    2005: 11439,  # ~37.5% del ANP (Castañeda-González et al., Ra Ximhai 2012)
    2018: 3000,   # "más de tres mil hectáreas" (nota del ITESO, abril 2018)
}
REFERENCIA_PRESENCIA = {
    2008: "incendio en zona de restauración del ITESO (nota del ITESO, 2018)",
    2023: "incendio en Los Volcanes, 22 de febrero (Zona Docs, 2023)",
}


def chunks(lista, tam):
    for i in range(0, len(lista), tam):
        yield lista[i : i + tam]


def nombre_banda_umbral(umbral: float) -> str:
    return f"q{int(round(umbral * 100)):03d}"


PROPS_DATOS = ["dnbr", "valido"] + [nombre_banda_umbral(u) for u in UMBRALES_DNBR]


# ---------------------------------------------------------------------------
# Lógica pura (sin GEE ni Neo4j): clasificación y agregados
# ---------------------------------------------------------------------------

def construir_candidatos_ventana(ventana_base: tuple[str, str]) -> list[tuple[str, str]]:
    """Ventana base primero, y luego versiones con el mismo fin pero un
    inicio más temprano (solo las que de verdad amplíen la ventana base).
    Las fechas MM-DD se comparan como texto, que para este formato ordena
    igual que por fecha.
    """
    inicio_base, fin = ventana_base
    candidatos = [ventana_base]
    for inicio in PASOS_INICIO_VENTANA:
        if inicio < inicio_base:
            candidatos.append((inicio, fin))
    return candidatos


def clasificar_celda_anio(datos, clave_umbral, min_valido, umbral_fraccion) -> str:
    """'sin_dato', 'quemada' o 'no_quemada' para una celda en un año."""
    if not datos:
        return "sin_dato"
    valido = datos.get("valido")
    fraccion = datos.get(clave_umbral)
    if valido is None or fraccion is None or valido < min_valido:
        return "sin_dato"
    return "quemada" if fraccion >= umbral_fraccion else "no_quemada"


def calcular_estados(resultados, h3_ids, clave_umbral, min_valido, umbral_fraccion):
    """{anio: {h3_id: estado}} a partir de {anio: {h3_id: datos}}."""
    return {
        anio: {
            h: clasificar_celda_anio(por_celda.get(h), clave_umbral, min_valido, umbral_fraccion)
            for h in h3_ids
        }
        for anio, por_celda in resultados.items()
    }


def calcular_agregados(estados, h3_ids):
    """Frecuencia y periodo de retorno por celda.

    anios_observados cuenta solo los años con dato válido; el periodo de
    retorno queda en None si no hubo incendios (no es infinito: es "mayor a
    anios_observados").
    """
    por_celda = {}
    for h in h3_ids:
        quemados = [a for a, est in estados.items() if est[h] == "quemada"]
        observados = sum(1 for est in estados.values() if est[h] != "sin_dato")
        n = len(quemados)
        por_celda[h] = {
            "n_incendios": n,
            "anios_observados": observados,
            "frecuencia": (n / observados) if observados > 0 else None,
            "periodo_retorno": (observados / n) if n > 0 else None,
            "ultimo_anio": max(quemados) if quemados else None,
        }
    return por_celda


def resumir_anio(estados_anio, datos_anio, areas_ha):
    quemadas = [h for h, e in estados_anio.items() if e == "quemada"]
    sin_dato = sum(1 for e in estados_anio.values() if e == "sin_dato")
    dnbrs = [
        datos_anio[h]["dnbr"] for h in quemadas
        if datos_anio.get(h) and datos_anio[h].get("dnbr") is not None
    ]
    return {
        "n_quemadas": len(quemadas),
        "n_sin_dato": sin_dato,
        "area_ha": sum(areas_ha[h] for h in quemadas),
        "dnbr_medio": (sum(dnbrs) / len(dnbrs)) if dnbrs else None,
    }


# ---------------------------------------------------------------------------
# Google Earth Engine
# ---------------------------------------------------------------------------

def inicializar_ee(proyecto: str):
    ee.Initialize(project=proyecto)


def con_reintentos(fn, intentos=3, espera=5):
    for i in range(intentos):
        try:
            return fn()
        except ee.EEException as e:
            if i == intentos - 1:
                raise
            print(f"  Error de GEE ({e}); reintentando en {espera * (i + 1)} s...")
            time.sleep(espera * (i + 1))


def leer_celdas(driver, resolucion: int) -> list[str]:
    query = "MATCH (c:CeldaH3 {resolucion: $resolucion}) RETURN c.h3_id AS h3_id"
    with driver.session() as session:
        return [r["h3_id"] for r in session.run(query, resolucion=resolucion)]


def construir_feature_collection(h3_ids: list[str]) -> ee.FeatureCollection:
    features = []
    for h3_id in h3_ids:
        boundary = h3.cell_to_boundary(h3_id)  # [(lat, lon), ...]
        coords = [[lon, lat] for lat, lon in boundary]  # GEE espera [lon, lat]
        coords.append(coords[0])  # cerrar polígono
        features.append(ee.Feature(ee.Geometry.Polygon([coords]), {"h3_id": h3_id}))
    return ee.FeatureCollection(features)


def construir_region(h3_ids: list[str]) -> ee.Geometry:
    lons, lats = [], []
    for h3_id in h3_ids:
        for lat, lon in h3.cell_to_boundary(h3_id):
            lats.append(lat)
            lons.append(lon)
    return ee.Geometry.Rectangle([min(lons), min(lats), max(lons), max(lats)])


def _nbr_landsat(nir: str, swir2: str):
    def f(img):
        qa = img.select("QA_PIXEL")
        limpio = (
            qa.bitwiseAnd(1 << 1).eq(0)   # nube dilatada
            .And(qa.bitwiseAnd(1 << 3).eq(0))  # nube
            .And(qa.bitwiseAnd(1 << 4).eq(0))  # sombra de nube
        )
        # Factores de escala de Landsat C2 L2 (necesarios: el offset afecta al cociente)
        opt = img.select([nir, swir2]).multiply(0.0000275).add(-0.2)
        nbr = opt.normalizedDifference([nir, swir2]).rename("nbr")
        return nbr.updateMask(limpio)
    return f


def compuesto_nbr(anio: int, ventana: tuple[str, str], region) -> ee.Image:
    inicio, fin = f"{anio}-{ventana[0]}", f"{anio}-{ventana[1]}"
    total = None
    for coleccion, (nir, swir2) in COLECCIONES_LANDSAT.items():
        parte = (
            ee.ImageCollection(coleccion)
            .filterBounds(region)
            .filterDate(inicio, fin)
            .map(_nbr_landsat(nir, swir2))
        )
        total = parte if total is None else total.merge(parte)
    vacia = ee.Image.constant(0).selfMask().rename("nbr")  # imagen totalmente enmascarada
    return ee.Image(
        ee.Algorithms.If(total.size().gt(0), total.median().rename("nbr"), vacia)
    )


def cobertura_vegetal() -> ee.Image:
    mapa = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    mascara = mapa.eq(CLASES_VEGETACION[0])
    for clase in CLASES_VEGETACION[1:]:
        mascara = mascara.Or(mapa.eq(clase))
    return mascara


def imagen_para_reducir(anio, ventana, region, aplicar_offset) -> ee.Image:
    pre = compuesto_nbr(anio - 1, ventana, region)
    post = compuesto_nbr(anio, ventana, region)
    dnbr = pre.subtract(post).rename("dnbr").updateMask(cobertura_vegetal())

    if aplicar_offset:
        stats = dnbr.reduceRegion(
            reducer=ee.Reducer.median(),
            geometry=region,
            scale=120,
            maxPixels=int(1e9),
            bestEffort=True,
        )
        offset = ee.Number(stats.get("dnbr", 0))
        dnbr = dnbr.subtract(offset).rename("dnbr")

    valido = dnbr.mask().unmask(0).rename("valido")  # 1 donde hay dato, 0 donde no
    bandas = [dnbr, valido] + [
        dnbr.gte(u).rename(nombre_banda_umbral(u)) for u in UMBRALES_DNBR
    ]
    return ee.Image.cat(bandas)


def obtener_resultados_anio(anio, h3_ids, region, ventana, aplicar_offset, resolucion, usar_cache):
    CACHE_DIR.mkdir(exist_ok=True)
    tag_ventana = f"{ventana[0]}_{ventana[1]}"
    ruta = CACHE_DIR / f"incendios_res{resolucion}_v{tag_ventana}_off{int(aplicar_offset)}_{anio}.json"

    if usar_cache and ruta.exists():
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if all(h in datos for h in h3_ids):
            print(f"  {anio}: desde cache")
            return datos

    print(f"  {anio}: consultando GEE...")
    img = imagen_para_reducir(anio, ventana, region, aplicar_offset)
    resultados = {}
    for lote in chunks(h3_ids, BATCH_CELDAS_GEE):
        fc = construir_feature_collection(lote)
        reducido = img.reduceRegions(
            collection=fc, reducer=ee.Reducer.mean(), scale=ESCALA_LANDSAT_M
        ).select(["h3_id"] + PROPS_DATOS, retainGeometry=False)
        feats = con_reintentos(lambda: reducido.getInfo()).get("features", [])
        for feat in feats:
            p = feat["properties"]
            if p.get("h3_id"):
                resultados[p["h3_id"]] = {k: p.get(k) for k in PROPS_DATOS}

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resultados, f)
    return resultados


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

def imprimir_resumen(resumenes, n_celdas, ventanas_usadas=None):
    ventanas_usadas = ventanas_usadas or {}
    print("\nResumen por año (área = suma de las celdas marcadas; aproximada):")
    print(f"{'año':>6} {'celdas':>8} {'% celdas':>9} {'área ha':>10} {'sin dato':>9} {'dNBR medio':>11} {'ventana':>13}")
    for anio in sorted(resumenes):
        r = resumenes[anio]
        dn = f"{r['dnbr_medio']:.2f}" if r["dnbr_medio"] is not None else "-"
        vent = ventanas_usadas.get(anio)
        vent_txt = f"{vent[0]}/{vent[1]}" if vent else "-"
        print(
            f"{anio:>6} {r['n_quemadas']:>8} {100 * r['n_quemadas'] / n_celdas:>8.1f}% "
            f"{r['area_ha']:>10.0f} {r['n_sin_dato']:>9} {dn:>11} {vent_txt:>13}"
        )


def imprimir_sensibilidad(resultados, h3_ids, areas_ha, min_valido, umbral_fraccion):
    anios_ref = [a for a in sorted(set(REFERENCIA_AREA_HA) | set(REFERENCIA_PRESENCIA)) if a in resultados]
    if not anios_ref:
        return
    print("\nSensibilidad al umbral de dNBR en incendios de referencia (área detectada, ha):")
    print(f"{'año':>6} {'referencia':>16} " + " ".join(f"{u:>7.2f}" for u in UMBRALES_DNBR))
    for anio in anios_ref:
        ref = f"~{REFERENCIA_AREA_HA[anio]:,} ha" if anio in REFERENCIA_AREA_HA else "solo presencia"
        fila = []
        for u in UMBRALES_DNBR:
            est = calcular_estados({anio: resultados[anio]}, h3_ids, nombre_banda_umbral(u), min_valido, umbral_fraccion)
            fila.append(sum(areas_ha[h] for h, e in est[anio].items() if e == "quemada"))
        print(f"{anio:>6} {ref:>16} " + " ".join(f"{v:>7.0f}" for v in fila))
    for anio, nota in REFERENCIA_PRESENCIA.items():
        if anio in resultados:
            print(f"  ({anio}: {nota})")


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------

def escribir_neo4j(driver, resolucion, estados, resultados, por_celda, areas_ha, args, periodo, ventanas_usadas=None):
    ventanas_usadas = ventanas_usadas or {}
    res = int(resolucion)
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT evento_id IF NOT EXISTS "
            "FOR (e:EventoDisturbio) REQUIRE e.id IS UNIQUE"
        )

        for anio in sorted(estados):
            evento_id = f"incendio_landsat_{anio}"
            quemadas = [h for h, e in estados[anio].items() if e == "quemada"]
            area = sum(areas_ha[h] for h in quemadas)

            # Borrar relaciones previas de este evento en esta resolución
            # (por si se recalcula con otros umbrales)
            session.run(
                """
                MATCH (:CeldaH3 {resolucion: $res})-[r:AFECTADO_POR]->(:EventoDisturbio {id: $id})
                DELETE r
                """,
                res=res, id=evento_id,
            )

            if not quemadas:
                session.run(
                    f"""
                    MATCH (e:EventoDisturbio {{id: $id}})
                    SET e.area_ha_res{res} = 0, e.celdas_res{res} = 0
                    """,
                    id=evento_id,
                )
                continue

            vent = ventanas_usadas.get(anio)
            vent_txt = f"{vent[0]}_{vent[1]}" if vent else None

            session.run(
                f"""
                MERGE (e:EventoDisturbio {{id: $id}})
                SET e.tipo = 'incendio', e.anio = $anio, e.fuente = 'landsat_dnbr',
                    e.umbral_dnbr = $umbral, e.umbral_fraccion = $frac,
                    e.ventana_usada = $ventana,
                    e.area_ha_res{res} = $area, e.celdas_res{res} = $n
                """,
                id=evento_id, anio=anio, umbral=args.umbral_dnbr,
                frac=args.umbral_fraccion, ventana=vent_txt,
                area=round(area, 1), n=len(quemadas),
            )

            registros = [
                {
                    "h3_id": h,
                    "sev": resultados[anio][h].get("dnbr"),
                    "frac": resultados[anio][h].get(nombre_banda_umbral(args.umbral_dnbr)),
                }
                for h in quemadas
            ]
            for lote in chunks(registros, BATCH_NEO4J):
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: $res})
                    MATCH (e:EventoDisturbio {id: $id})
                    MERGE (c)-[r:AFECTADO_POR]->(e)
                    SET r.severidad = row.sev, r.fraccion_quemada = row.frac
                    """,
                    batch=lote, res=res, id=evento_id,
                )

        registros = [
            {
                "h3_id": h,
                "n": a["n_incendios"],
                "obs": a["anios_observados"],
                "freq": a["frecuencia"],
                "pr": a["periodo_retorno"],
                "ultimo": a["ultimo_anio"],
            }
            for h, a in por_celda.items()
        ]
        for lote in chunks(registros, BATCH_NEO4J):
            session.run(
                """
                UNWIND $batch AS row
                MATCH (c:CeldaH3 {h3_id: row.h3_id, resolucion: $res})
                SET c.n_incendios = row.n,
                    c.anios_observados = row.obs,
                    c.frecuencia_incendios_anual = row.freq,
                    c.periodo_retorno_anios = row.pr,
                    c.ultimo_incendio_anio = row.ultimo,
                    c.periodo_incendios = $periodo,
                    c.fuente_incendios = 'landsat_dnbr'
                """,
                batch=lote, res=res, periodo=periodo,
            )
    print(f"  {len(por_celda)} celdas actualizadas con frecuencia y periodo de retorno")


# ---------------------------------------------------------------------------

def parsear_ventana(texto: str) -> tuple[str, str]:
    partes = [p.strip() for p in texto.split(",")]
    if len(partes) != 2:
        raise SystemExit("--ventana debe ser 'MM-DD,MM-DD' (ej. 05-15,06-30)")
    return partes[0], partes[1]


def main():
    hoy = date.today()
    anio_fin_defecto = hoy.year if hoy >= date(hoy.year, 7, 16) else hoy.year - 1

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolucion", type=int, default=8, help="Resolución H3 (por defecto 8)")
    parser.add_argument(
        "--proyecto",
        default=os.getenv("GEE_PROJECT", "red-primavera"),
        help="ID del proyecto de Google Cloud para GEE. Por defecto lee GEE_PROJECT del .env.",
    )
    parser.add_argument("--anio-inicio", type=int, default=2000)
    parser.add_argument("--anio-fin", type=int, default=anio_fin_defecto)
    parser.add_argument("--ventana", default="05-15,06-30",
                        help="Ventana MM-DD,MM-DD que se compara entre años (fin de la temporada seca)")
    parser.add_argument("--umbral-dnbr", type=float, default=0.20,
                        help=f"Umbral de dNBR para marcar un píxel como quemado. Opciones: {UMBRALES_DNBR}")
    parser.add_argument("--umbral-fraccion", type=float, default=0.25,
                        help="Fracción mínima de la celda quemada para marcar la celda-año como quemada")
    parser.add_argument("--min-valido", type=float, default=0.5,
                        help="Fracción mínima de datos válidos (por celda) para contar el año como observado")
    parser.add_argument("--min-cobertura-anual", type=float, default=0.6,
                        help="Fracción mínima de celdas con dato válido para aceptar la ventana de ese año; "
                             "si no se alcanza, se reintenta con una ventana más ancha (ver --sin-adaptativo)")
    parser.add_argument("--sin-adaptativo", action="store_true",
                        help="Usa siempre --ventana tal cual, sin ensanchar por año con poca cobertura")
    parser.add_argument("--sin-offset", action="store_true", help="No restar la mediana del dNBR")
    parser.add_argument("--sin-cache", action="store_true", help="Ignorar la cache local en cache/")
    parser.add_argument("--dry-run", action="store_true", help="Calcula y muestra el resumen sin escribir en Neo4j")
    args = parser.parse_args()

    if args.umbral_dnbr not in UMBRALES_DNBR:
        raise SystemExit(f"--umbral-dnbr debe ser uno de {UMBRALES_DNBR}")
    if args.anio_inicio >= args.anio_fin:
        raise SystemExit("--anio-inicio debe ser menor que --anio-fin")

    ventana = parsear_ventana(args.ventana)
    clave_umbral = nombre_banda_umbral(args.umbral_dnbr)

    modo_ventana = (
        f"ventana fija {ventana[0]} a {ventana[1]} (--sin-adaptativo)" if args.sin_adaptativo
        else f"ventana adaptativa, base {ventana[0]} a {ventana[1]}, "
             f"cobertura mínima {args.min_cobertura_anual:.0%}"
    )
    print(f"Años: {args.anio_inicio}-{args.anio_fin} | {modo_ventana} | "
          f"umbral dNBR {args.umbral_dnbr} | fracción {args.umbral_fraccion} | "
          f"offset {'no' if args.sin_offset else 'sí'}")
    print(f"Proyecto GEE: {args.proyecto}")
    print("Inicializando Earth Engine...")
    inicializar_ee(args.proyecto)

    driver = get_driver(os.environ["NEO4J_URI"], os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"])

    print(f"Leyendo celdas H3 de resolución {args.resolucion} desde Neo4j...")
    h3_ids = leer_celdas(driver, args.resolucion)
    print(f"  {len(h3_ids)} celdas encontradas")
    if not h3_ids:
        print("No hay celdas para esta resolución. ¿Ya corriste el generador del grid H3?")
        driver.close()
        return

    areas_ha = {h: h3.cell_area(h, unit="km^2") * 100 for h in h3_ids}
    region = construir_region(h3_ids)

    candidatos_ventana = [ventana] if args.sin_adaptativo else construir_candidatos_ventana(ventana)

    resultados = {}
    ventanas_usadas = {}
    print("Detectando cicatrices año por año (Landsat, dNBR)...")
    for anio in range(args.anio_inicio, args.anio_fin + 1):
        for i, vent in enumerate(candidatos_ventana):
            datos_anio = obtener_resultados_anio(
                anio, h3_ids, region, vent, not args.sin_offset,
                args.resolucion, not args.sin_cache,
            )
            cobertura = sum(
                1 for h in h3_ids
                if datos_anio.get(h) and datos_anio[h].get("valido") is not None
                and datos_anio[h]["valido"] >= args.min_valido
            ) / len(h3_ids)

            es_ultima = i == len(candidatos_ventana) - 1
            if cobertura >= args.min_cobertura_anual or es_ultima:
                if i > 0:
                    print(f"    -> {anio}: ventana {vent[0]} a {vent[1]} aceptada "
                          f"(cobertura {cobertura:.0%})")
                resultados[anio] = datos_anio
                ventanas_usadas[anio] = vent
                break
            else:
                print(f"    {anio}: cobertura {cobertura:.0%} con ventana {vent[0]} a {vent[1]} "
                      f"(menor a {args.min_cobertura_anual:.0%}), probando una más ancha...")

    estados = calcular_estados(resultados, h3_ids, clave_umbral, args.min_valido, args.umbral_fraccion)
    por_celda = calcular_agregados(estados, h3_ids)
    resumenes = {a: resumir_anio(estados[a], resultados[a], areas_ha) for a in estados}

    imprimir_resumen(resumenes, len(h3_ids), ventanas_usadas)
    imprimir_sensibilidad(resultados, h3_ids, areas_ha, args.min_valido, args.umbral_fraccion)

    con_incendio = sum(1 for a in por_celda.values() if a["n_incendios"] > 0)
    print(f"\n{con_incendio} de {len(h3_ids)} celdas con al menos un incendio detectado.")

    if args.dry_run:
        print("\n--dry-run: no se escribió nada en Neo4j.")
        driver.close()
        return

    print("\nEscribiendo en Neo4j...")
    periodo = f"{args.anio_inicio}-{args.anio_fin}"
    escribir_neo4j(driver, args.resolucion, estados, resultados, por_celda, areas_ha, args, periodo, ventanas_usadas)
    driver.close()
    print("\n¡Listo!")


if __name__ == "__main__":
    main()