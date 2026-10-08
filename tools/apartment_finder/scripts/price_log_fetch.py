"""Price layer, ŁOG source: snapshots of the housing price map and the transaction map from the Łódź ArcGIS REST server.

Łódzki Ośrodek Geodezji (log.lodz.pl, Dział Monitoringu Rynku Nieruchomości) publishes, via mapa.lodz.pl/3/rest/services:
  RynekMieszkaniowy  200 m cells with a price CLASS per m2 (field SR_CENA, e.g. "6 501 - 7 500"), primary (RP) and secondary (RW) market,
                     one snapshot per year (II/III quarter): the only prices ŁOG exposes; no per-transaction prices exist on the server
  transakcje         one point per building address with a table of flat sales (date, area); no price
Both are written to data/price/log/ (EPSG:2180), restricted to snapshots/deeds from `log.from_year` (config/price.yaml).
Use of the data: permission from ŁOG (Michał, 2026-10-08); attribution "Łódzki Ośrodek Geodezji". No pagination on this server:
transactions are fetched in OBJECTID ranges. Plain system Python (urllib, osgeo).

  py scripts/price_log_fetch.py
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from osgeo import ogr, osr

ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/price.yaml", encoding="utf-8"))["log"]
OUT = HERE / "data/price/log"
BASE = "https://mapa.lodz.pl/3/rest/services/"


def get(url, **params):
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(url + "?" + q, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_class(s):
    """'6 501 - 7 500' -> (6501, 7500); '≥ 7 501' / 'powyżej 5000' -> (7501, None); 'poniżej 2500' -> (None, 2499)."""
    nums = [int(x.replace(" ", "").replace("\xa0", "")) for x in re.findall(r"\d[\d \xa0]*", s)]
    if "≥" in s or "powyżej" in s.lower():
        return nums[0], None
    if "poniżej" in s.lower():
        return None, nums[0]
    return (nums[0], nums[1]) if len(nums) >= 2 else (nums[0], None)


def ring_polygon(rings):
    mp = ogr.Geometry(ogr.wkbMultiPolygon)
    for ring in rings:
        r = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in ring:
            r.AddPoint_2D(x, y)
        p = ogr.Geometry(ogr.wkbPolygon)
        p.AddGeometry(r)
        mp.AddGeometry(p)
    return mp


def new_ds(name, geom, fields):
    path = OUT / name
    if path.exists():
        path.unlink()
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(2180)
    lyr = ds.CreateLayer(name.split(".")[0], srs, geom)
    for n, t in fields:
        lyr.CreateField(ogr.FieldDefn(n, t))
    return ds, lyr


def fetch_cells():
    ds, lyr = new_ds("log_cells.gpkg", ogr.wkbMultiPolygon, [("snapshot", ogr.OFTString), ("market", ogr.OFTString), ("class", ogr.OFTString),
                                                            ("lo", ogr.OFTInteger), ("hi", ogr.OFTInteger), ("layer_id", ogr.OFTInteger)])
    meta = []
    for snap in cfg["snapshots"]:
        for market, lid in (("RP", snap["rp"]), ("RW", snap["rw"])):
            d = get(BASE + "RynekMieszkaniowy/MapServer/%d/query" % lid, where="1=1", outFields="SR_CENA", outSR=2180, f="json")
            assert not d.get("exceededTransferLimit"), "layer %d truncated" % lid
            for f in d["features"]:
                ft = ogr.Feature(lyr.GetLayerDefn())
                cl = f["attributes"]["SR_CENA"].strip()
                lo, hi = parse_class(cl)
                ft.SetField("snapshot", snap["label"]); ft.SetField("market", market); ft.SetField("class", cl); ft.SetField("layer_id", lid)
                if lo is not None:
                    ft.SetField("lo", lo)
                if hi is not None:
                    ft.SetField("hi", hi)
                ft.SetGeometry(ring_polygon(f["geometry"]["rings"]))
                lyr.CreateFeature(ft)
            meta.append({"snapshot": snap["label"], "market": market, "layer_id": lid, "cells": len(d["features"])})
            print("  cells", snap["label"], market, len(d["features"]))
    ds = None
    return meta


def fetch_transactions():
    rows = []
    for a in range(0, 12000, 900):
        d = get(BASE + "transakcje/MapServer/0/query", where="OBJECTID>=%d AND OBJECTID<%d" % (a, a + 900), outFields="ADRES,OBREB,TRANSAKCJE", outSR=2180, f="json")
        assert "error" not in d, d.get("error")
        rows += d["features"]
    ds, lyr = new_ds("log_transactions.gpkg", ogr.wkbPoint, [("adres", ogr.OFTString), ("obreb", ogr.OFTString), ("data", ogr.OFTString), ("powierzchnia", ogr.OFTReal)])
    total = kept = 0
    for f in rows:
        for m in re.finditer(r"<td>(\d+)\.(\d+)\.(\d{4})</td><td>([\d.]+)</td>", f["attributes"]["TRANSAKCJE"]):
            total += 1
            dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if yy < cfg["from_year"]:
                continue
            ft = ogr.Feature(lyr.GetLayerDefn())
            ft.SetField("adres", f["attributes"]["ADRES"]); ft.SetField("obreb", f["attributes"]["OBREB"])
            ft.SetField("data", "%04d-%02d-%02d" % (yy, mm, dd)); ft.SetField("powierzchnia", float(m.group(4)))
            ft.SetGeometry(ogr.CreateGeometryFromWkt("POINT (%f %f)" % (f["geometry"]["x"], f["geometry"]["y"])))
            lyr.CreateFeature(ft)
            kept += 1
    ds = None
    print("  transactions: %d addresses, %d deals in total, %d from %d" % (len(rows), total, kept, cfg["from_year"]))
    return {"addresses": len(rows), "deals_all_years": total, "deals_kept": kept}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"source": "Łódzki Ośrodek Geodezji, mapa.lodz.pl/3/rest/services (RynekMieszkaniowy, transakcje)", "from_year": cfg["from_year"],
            "cells": fetch_cells(), "transactions": fetch_transactions()}
    json.dump(meta, open(OUT / "log_fetch.meta.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
