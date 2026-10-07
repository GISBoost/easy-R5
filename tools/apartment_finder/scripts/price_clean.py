"""Price layer, step 2: RCN rows (price_fetch.py) -> clean apartment transactions with price per m2.

Rules in config/price.yaml. Price of a flat = LOK_CENA_BRUTTO; when empty, TRAN_CENA_BRUTTO only if the deed
contains exactly one row (otherwise the deed price covers several premises and cannot be attributed).
Dedup on deed id + premises id + date + price. Output data/price/price_clean.gpkg layer rcn_mieszkania (EPSG:2180)
with source=rcn, kind=transakcja, plus price_clean.meta.json (rule counts). System Python (osgeo).

  py scripts/price_clean.py
"""
import csv
import json
from collections import Counter
from pathlib import Path

import yaml
from osgeo import ogr, osr

ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/price.yaml", encoding="utf-8"))
OUT = HERE / "data/price"


def num(s):
    try:
        return float(str(s).replace(",", "."))
    except ValueError:
        return None


def main():
    rows = list(csv.DictReader(open(OUT / "rcn_lokale.csv", encoding="utf-8")))
    per_deed = Counter(r["TRAN_LOKALNY_ID_IIP"] for r in rows)
    drop = Counter()
    keep, seen = [], set()
    for r in rows:
        why = None
        if r["TERYT"] != cfg["teryt"]:
            why = "teryt"
        elif r["LOK_FUNKCJA"] != cfg["function"]:
            why = "function"
        elif not (r["DOK_DATA"] >= cfg["window"]["from"]):
            why = "before window"
        elif r["TRAN_RODZAJ_TRANS"] not in cfg["transaction_types"]:
            why = "transaction type"
        elif r["NIER_UDZIAL"] not in ("", cfg["share"]):
            why = "share"
        elif not r.get("x"):
            why = "no geometry"
        else:
            area = num(r["LOK_POW_UZYT"])
            price, src = num(r["LOK_CENA_BRUTTO"]), "lok"
            if price is None and per_deed[r["TRAN_LOKALNY_ID_IIP"]] == 1:
                price, src = num(r["TRAN_CENA_BRUTTO"]), "tran"
            if price is None or not area:
                why = "no price/area"
            elif not (cfg["area_m2"][0] <= area <= cfg["area_m2"][1]):
                why = "area"
            elif not (cfg["price_m2"][0] <= price / area <= cfg["price_m2"][1]):
                why = "price per m2"
            else:
                k = (r["TRAN_LOKALNY_ID_IIP"], r["LOK_ID_LOKALU"], r["DOK_DATA"], price)
                if k in seen:
                    why = "duplicate"
                else:
                    seen.add(k)
                    keep.append((r, area, price, src))
        if why:
            drop[why] += 1

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(2180)
    path = OUT / "price_clean.gpkg"
    if path.exists():
        path.unlink()
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    lyr = ds.CreateLayer("rcn_mieszkania", srs, ogr.wkbPoint)
    for name, t in (("tran_id", ogr.OFTString), ("lok_id", ogr.OFTString), ("data", ogr.OFTString), ("rynek", ogr.OFTString),
                    ("powierzchnia", ogr.OFTReal), ("cena", ogr.OFTReal), ("cena_m2", ogr.OFTReal), ("izby", ogr.OFTInteger),
                    ("cena_z", ogr.OFTString), ("zrodlo", ogr.OFTString), ("rodzaj", ogr.OFTString)):
        lyr.CreateField(ogr.FieldDefn(name, t))
    for r, area, price, src in keep:
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("tran_id", r["TRAN_LOKALNY_ID_IIP"]); f.SetField("lok_id", r["LOK_ID_LOKALU"]); f.SetField("data", r["DOK_DATA"])
        f.SetField("rynek", r["TRAN_RODZAJ_RYNKU"] or "brak"); f.SetField("powierzchnia", area); f.SetField("cena", price)
        f.SetField("cena_m2", round(price / area, 1)); f.SetField("cena_z", src); f.SetField("zrodlo", "rcn"); f.SetField("rodzaj", "transakcja")
        if r["LOK_LICZBA_IZB"].isdigit():
            f.SetField("izby", int(r["LOK_LICZBA_IZB"]))
        f.SetGeometry(ogr.CreateGeometryFromWkt("POINT (%s %s)" % (r["x"], r["y"])))
        lyr.CreateFeature(f)
    ds = None
    vals = sorted(p / a for _, a, p, _ in keep)
    q = lambda p: round(vals[int(p * (len(vals) - 1))])
    months = Counter(r["DOK_DATA"][:7] for r, *_ in keep)
    meta = {"price_version": cfg["price_version"], "window_from": cfg["window"]["from"], "rows_in": len(rows), "kept": len(keep),
            "dropped": dict(drop), "price_from_deed": sum(1 for *_, s in keep if s == "tran"),
            "date_min": min(r["DOK_DATA"] for r, *_ in keep), "date_max": max(r["DOK_DATA"] for r, *_ in keep),
            "price_m2_pct": {p: q(p / 100) for p in (5, 25, 50, 75, 95)}, "by_month": dict(sorted(months.items()))}
    json.dump(meta, open(OUT / "price_clean.meta.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != "by_month"}, indent=1, ensure_ascii=False))
    print("by month:", dict(sorted(months.items())))


if __name__ == "__main__":
    main()
