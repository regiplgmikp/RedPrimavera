"""Calibra --umbral-dnbr y --umbral-fraccion de etl_gee_incendios.py contra
áreas de referencia de incendios conocidos.

NO consulta Google Earth Engine ni Neo4j: trabaja solo con los archivos que
etl_gee_incendios.py ya guardó en cache/. Por eso hay que haber corrido antes
etl_gee_incendios.py (con --dry-run basta) en la misma resolución.

Qué hace:
    - Para cada año de referencia, repite la selección de ventana adaptativa
      igual que el script original (ventana base primero; si la cobertura no
      alcanza --min-cobertura-anual, la siguiente más ancha).
    - Prueba todas las combinaciones de umbral de dNBR (los 6 que guarda la
      cache) x umbral de fracción (FRACCIONES).
    - Para cada combinación calcula el área estimada por año (suma del área de
      las celdas marcadas como quemadas, igual que el script original) y el
      error contra la referencia.
    - Como las referencias son RANGOS, el error es 0 si la estimación cae
      dentro del rango y, si cae fuera, la distancia relativa al borde más
      cercano.
    - Ordena las combinaciones por error relativo medio (y luego por error
      máximo) e imprime una tabla completa.

Uso (desde la carpeta raíz del proyecto):
    python etls/calibrar_umbrales.py --resolucion 9
    python etls/calibrar_umbrales.py --resolucion 8
    python etls/calibrar_umbrales.py --resolucion 9 --incluir-2021
"""

import argparse
import json
import sys
from pathlib import Path

import h3

# Reutilizar exactamente la misma lógica del ETL original
sys.path.insert(0, str(Path(__file__).resolve().parent))
from etl_gee_incendios import (  # noqa: E402
    CACHE_DIR,
    UMBRALES_DNBR,
    calcular_estados,
    construir_candidatos_ventana,
    nombre_banda_umbral,
)

# Umbrales de fracción a probar (el ETL usa 0.25 por defecto)
FRACCIONES = [0.10, 0.15, 0.20, 0.25, 0.33, 0.50]

# Áreas de referencia como rangos (mínimo, máximo) en hectáreas.
# EDITA AQUÍ si encuentras mejores fuentes.
REFERENCIAS = {
    2005: (8080, 11439, "UdeG 26.5% del ANP / Castañeda-González et al. 2012"),
    2012: (7500, 8162, "AP 2012 / López García 2020 (Landsat)"),
    2018: (3057, 3057, "OPD Bosque La Primavera vía transparencia (Zona Docs 2022)"),
}
# 2021 solo tiene un mínimo y aún no se confirma la fecha del incendio;
# por eso queda fuera salvo que se pida con --incluir-2021.
REFERENCIA_2021 = (4926, None, "Las Canoas-Nejahuete-Pedernal (Jardel-Peláez et al. 2021), solo mínimo")


def ruta_cache(resolucion, ventana, con_offset, anio):
    tag = f"{ventana[0]}_{ventana[1]}"
    return CACHE_DIR / f"incendios_res{resolucion}_v{tag}_off{int(con_offset)}_{anio}.json"


def cargar_anio(resolucion, anio, candidatos, con_offset, min_valido, min_cobertura):
    """Repite la ventana adaptativa con la cache.

    Devuelve (datos, ventana, cobertura) o (None, ventana, mensaje) si falta
    algún archivo de cache.
    """
    for i, ventana in enumerate(candidatos):
        ruta = ruta_cache(resolucion, ventana, con_offset, anio)
        if not ruta.exists():
            return None, ventana, f"falta {ruta.name} (corre etl_gee_incendios.py --dry-run)"
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if not datos:
            return None, ventana, f"{ruta.name} está vacío"
        cobertura = sum(
            1 for d in datos.values()
            if d and d.get("valido") is not None and d["valido"] >= min_valido
        ) / len(datos)
        es_ultima = i == len(candidatos) - 1
        if cobertura >= min_cobertura or es_ultima:
            return datos, ventana, cobertura
    return None, candidatos[-1], "sin ventanas candidatas"


def error_rango(estimado, minimo, maximo):
    """0 si cae dentro del rango; si no, distancia relativa al borde más cercano."""
    if estimado < minimo:
        return (minimo - estimado) / minimo
    if maximo is not None and estimado > maximo:
        return (estimado - maximo) / maximo
    return 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resolucion", type=int, default=9)
    parser.add_argument("--ventana", default="05-15,06-30", help="Ventana base (igual que en el ETL)")
    parser.add_argument("--min-valido", type=float, default=0.5)
    parser.add_argument("--min-cobertura-anual", type=float, default=0.6)
    parser.add_argument("--sin-offset", action="store_true", help="Usar la cache calculada sin offset")
    parser.add_argument("--incluir-2021", action="store_true", help="Agregar 2021 (solo mínimo, fecha sin confirmar)")
    parser.add_argument("--top", type=int, default=10, help="Cuántas combinaciones mostrar en el ranking")
    args = parser.parse_args()

    referencias = dict(REFERENCIAS)
    if args.incluir_2021:
        referencias[2021] = REFERENCIA_2021

    inicio, fin = [p.strip() for p in args.ventana.split(",")]
    candidatos = construir_candidatos_ventana((inicio, fin))
    con_offset = not args.sin_offset

    print(f"Resolución {args.resolucion} | offset {'sí' if con_offset else 'no'} | "
          f"min-valido {args.min_valido} | cobertura mínima {args.min_cobertura_anual:.0%}")
    print("\nAños de referencia y ventana usada (leídos de cache/):")

    datos_por_anio = {}
    for anio in sorted(referencias):
        datos, ventana, info = cargar_anio(
            args.resolucion, anio, candidatos, con_offset, args.min_valido, args.min_cobertura_anual
        )
        if datos is None:
            print(f"  {anio}: OMITIDO — {info}")
            continue
        datos_por_anio[anio] = datos
        lo, hi, fuente = referencias[anio]
        rango = f"{lo:,}–{hi:,} ha" if hi else f"≥ {lo:,} ha"
        print(f"  {anio}: ventana {ventana[0]}/{ventana[1]}, cobertura {info:.0%} | ref {rango} ({fuente})")

    if not datos_por_anio:
        raise SystemExit("\nNo hay datos en cache para ningún año de referencia. Corre primero el ETL con --dry-run.")

    # Área de cada celda (igual que el ETL: celda completa, en ha)
    todas = set()
    for datos in datos_por_anio.values():
        todas.update(datos)
    areas_ha = {h: h3.cell_area(h, unit="km^2") * 100 for h in todas}

    filas = []
    for u in UMBRALES_DNBR:
        clave = nombre_banda_umbral(u)
        for frac in FRACCIONES:
            areas, errores = {}, {}
            for anio, datos in datos_por_anio.items():
                h3_ids = list(datos)
                estados = calcular_estados({anio: datos}, h3_ids, clave, args.min_valido, frac)[anio]
                area = sum(areas_ha[h] for h, e in estados.items() if e == "quemada")
                lo, hi, _ = referencias[anio]
                areas[anio] = area
                errores[anio] = error_rango(area, lo, hi)
            filas.append({
                "umbral": u,
                "fraccion": frac,
                "areas": areas,
                "error_medio": sum(errores.values()) / len(errores),
                "error_max": max(errores.values()),
                "dentro": sum(1 for e in errores.values() if e == 0),
            })

    filas.sort(key=lambda r: (r["error_medio"], r["error_max"]))
    anios = sorted(datos_por_anio)

    # Ranking
    print(f"\nTop {args.top} combinaciones (error relativo al rango; 0 = dentro del rango):")
    encabezado = f"{'dNBR':>6} {'frac':>6} " + " ".join(f"{a:>9}" for a in anios) + f" {'err medio':>10} {'err máx':>8} {'dentro':>7}"
    print(encabezado)
    for r in filas[: args.top]:
        print(f"{r['umbral']:>6.2f} {r['fraccion']:>6.2f} "
              + " ".join(f"{r['areas'][a]:>9,.0f}" for a in anios)
              + f" {r['error_medio']:>10.1%} {r['error_max']:>8.1%} {r['dentro']:>4}/{len(anios)}")

    # Combinación actual, para comparar
    actual = next((r for r in filas if r["umbral"] == 0.15 and r["fraccion"] == 0.25), None)
    if actual:
        lugar = filas.index(actual) + 1
        print(f"\nCombinación actual (0.15 / 0.25): lugar {lugar} de {len(filas)} | "
              f"error medio {actual['error_medio']:.1%} | error máx {actual['error_max']:.1%} | "
              + " | ".join(f"{a}: {actual['areas'][a]:,.0f} ha" for a in anios))

    # Matriz de error medio (filas = umbral dNBR, columnas = fracción)
    print("\nMatriz de error medio (filas: umbral dNBR; columnas: umbral de fracción):")
    print(f"{'':>6} " + " ".join(f"{f:>7.2f}" for f in FRACCIONES))
    for u in UMBRALES_DNBR:
        celdas = []
        for frac in FRACCIONES:
            r = next(x for x in filas if x["umbral"] == u and x["fraccion"] == frac)
            celdas.append(f"{r['error_medio']:>7.1%}")
        print(f"{u:>6.2f} " + " ".join(celdas))

    print("\nOjo: con pocos años de referencia, varias combinaciones pueden empatar. "
          "Prefiere la que tenga error bajo Y vecinos también bajos en la matriz (zona estable), "
          "no un mínimo aislado.")


if __name__ == "__main__":
    main()