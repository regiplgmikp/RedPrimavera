"""
Valida la reconstrucción de incendios (dNBR Landsat, ya en cache/) contra una fuente
independiente: el producto de área quemada MODIS MCD64A1 (500 m), disponible en GEE.

  python tests/validar_mcd64a1.py                      # tabla año por año (res 9)
  python tests/validar_mcd64a1.py --detalle 2012 2018 2021   # + acuerdo celda por celda (res 8)

Qué responde: ¿cuántas hectáreas quemadas ve MODIS dentro del ANP cada año, comparadas con
las que detecta nuestro método? Si en 2021 MODIS ve ~2,000 ha y nosotros ~9,000, hay
sobredetección; si ve ~8,000, el evento es real.

Cómo leerlo (importante):
  - MCD64A1 es burda (píxel de 500 m = 25 ha) y se le escapan quemas pequeñas o de baja
    severidad bajo dosel. Que MODIS NO vea algo no prueba que no hubo fuego; que SÍ lo vea
    con un área parecida es una confirmación fuerte.
  - Se compara en áreas y en acuerdo espacial a res 8 (las celdas de res 9 son más
    pequeñas que un píxel MODIS).
  - No escribe nada en Neo4j; usa solo cache/ y GEE (necesita ee autenticado y GEE_PROJECT).
"""
import argparse, glob, json, os, sys
from pathlib import Path

import ee
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
load_dotenv()
try:
    import h3
except ImportError:
    h3 = None

CACHE = RAIZ / "cache"
LIMITE = RAIZ / "data" / "boundary" / "La_Primavera.geojson"
AREA_FALLBACK_HA = {8: 73.7, 9: 10.5}


def quitar_z(coords):
    if isinstance(coords[0], (int, float)):
        return coords[:2]
    return [quitar_z(c) for c in coords]


def limite_ee():
    gj = json.load(open(LIMITE, encoding="utf-8"))
    feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
    geoms = [ee.Geometry({"type": f["geometry"]["type"],
                          "coordinates": quitar_z(f["geometry"]["coordinates"])}) for f in feats]
    return ee.FeatureCollection([ee.Feature(g) for g in geoms]).geometry()


def area_celda_ha(h3_id, res):
    return h3.cell_area(h3_id, unit="m^2") / 1e4 if h3 else AREA_FALLBACK_HA[res]


def archivo_cache(res, anio):
    """Entre los archivos de cache del año elige el de la ventana que dio más celdas válidas
    (así toma la ventana adaptativa cuando el año necesitó ensancharla). Ignora la ventana
    fija ancha 02-01_08-31 de las pruebas."""
    mejores = None
    for f in glob.glob(str(CACHE / f"incendios_res{res}_v*_off1_{anio}.json")):
        if "02-01_08-31" in f:
            continue
        d = json.load(open(f))
        n = sum(1 for v in d.values() if v.get("valido", 0) >= 0.5)
        if mejores is None or n > mejores[0]:
            mejores = (n, f, d)
    return mejores[2] if mejores else None


def quemadas_nuestras(res, anio, umbral, fraccion):
    d = archivo_cache(res, anio)
    if d is None:
        return None
    clave = f"q{round(umbral * 100):03d}"
    return {k for k, v in d.items() if v.get("valido", 0) >= 0.5 and v.get(clave, 0) >= fraccion}


def mcd_quemado(anio):
    col = (ee.ImageCollection("MODIS/061/MCD64A1")
           .filterDate(f"{anio}-01-01", f"{anio + 1}-01-01").select("BurnDate"))
    return col.max().gt(0).unmask(0).rename("quemado")


def area_mcd_ha(anio, geom):
    img = mcd_quemado(anio).multiply(ee.Image.pixelArea()).divide(1e4)
    v = img.reduceRegion(ee.Reducer.sum(), geom, 500, maxPixels=1e9).get("quemado")
    return ee.Number(v).getInfo() or 0.0


def celdas_mcd(anio, res, ids, fraccion):
    feats = []
    for h in ids:
        coords = [[lon, lat] for lat, lon in h3.cell_to_boundary(h)]
        feats.append(ee.Feature(ee.Geometry.Polygon([coords]), {"h3_id": h}))
    out = set()
    for i in range(0, len(feats), 400):
        fc = ee.FeatureCollection(feats[i:i + 400])
        r = mcd_quemado(anio).reduceRegions(fc, ee.Reducer.mean(), 500).getInfo()
        out |= {f["properties"]["h3_id"] for f in r["features"]
                if (f["properties"].get("mean") or 0) >= fraccion}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--proyecto", default=os.getenv("GEE_PROJECT", "red-primavera"))
    ap.add_argument("--anio-inicio", type=int, default=2001)
    ap.add_argument("--anio-fin", type=int, default=2025)
    ap.add_argument("--umbral-dnbr", type=float, default=0.15)
    ap.add_argument("--umbral-fraccion", type=float, default=0.25)
    ap.add_argument("--detalle", type=int, nargs="*", default=[])
    a = ap.parse_args()

    ee.Initialize(project=a.proyecto)
    geom = limite_ee()

    print(f"\nÁrea quemada dentro del ANP por año (ha)   [nuestro: dNBR>={a.umbral_dnbr}, fracción>={a.umbral_fraccion}, res 9]")
    print("año   MODIS_ha   nuestro_ha   nuestro/MODIS")
    for y in range(a.anio_inicio, a.anio_fin + 1):
        m = area_mcd_ha(y, geom)
        q = quemadas_nuestras(9, y, a.umbral_dnbr, a.umbral_fraccion)
        n = sum(area_celda_ha(c, 9) for c in q) if q is not None else float("nan")
        razon = f"{n / m:6.2f}" if m > 0 and q is not None else "   n/d"
        print(f"{y}  {m:9.0f}  {n:11.0f}   {razon}")

    if a.detalle:
        if h3 is None:
            raise SystemExit("--detalle necesita h3 (pip install h3)")
        print("\nAcuerdo celda por celda (res 8; celda quemada si >= fracción en ambos)")
        print("año   nuestras  MODIS  ambas  coincide_de_nuestras  coincide_de_MODIS")
        for y in a.detalle:
            ours = quemadas_nuestras(8, y, a.umbral_dnbr, a.umbral_fraccion)
            if ours is None:
                print(y, "sin cache res 8"); continue
            d8 = archivo_cache(8, y)
            mcd = celdas_mcd(y, 8, list(d8.keys()), a.umbral_fraccion)
            ambas = ours & mcd
            p = len(ambas) / len(ours) if ours else float("nan")
            r = len(ambas) / len(mcd) if mcd else float("nan")
            print(f"{y}  {len(ours):8d} {len(mcd):6d} {len(ambas):6d}  {p:19.0%}  {r:17.0%}")


if __name__ == "__main__":
    main()