"""Price layer, step 1: download RCN (Rejestr Cen Nieruchomosci) apartments from the GUGiK WFS and flatten to CSV.

WFS 2.0.0 `ms:lokale`, bbox of the city in EPSG:2180 (axis order NORTH, EAST), pages of 250 sorted by gid (without sortBy the server pages unstably: dropped + repeated rows), cached raw in
data/price/raw/ (resumable). Output data/price/rcn_lokale.csv: every ms:* attribute plus x (easting), y (northing).
No filtering here (price_clean.py does that); the bbox is only a pre-filter, TERYT is checked later.
Plain system Python (urllib). Source: GUGiK / county registers; reuse terms to be confirmed before publishing.

  py scripts/price_fetch.py [--report]
"""
import argparse
import csv
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "data/price"
RAW = OUT / "raw"
URL = "https://mapy.geoportal.gov.pl/wss/service/rcn"
BBOX = "423772,520735,443936,544060,urn:ogc:def:crs:EPSG::2180"   # N,E,N,E (Lodz, with margin)
PAGE = 250
NS_GML = "{http://www.opengis.net/gml/3.2}"


def get(start, tries=4):
    q = ("?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms:lokale&sortBy=gid&count=%d&startIndex=%d&bbox=%s"
         % (PAGE, start, BBOX))
    for k in range(tries):
        try:
            with urllib.request.urlopen(URL + q, timeout=180) as r:
                data = r.read()
            if b"<ExceptionReport" in data[:500] or b"ows:Exception" in data[:2000]:
                raise RuntimeError(data[:300])
            return data
        except Exception as e:   # noqa: BLE001 - transient server errors: retry
            if k == tries - 1:
                raise
            print("  retry", start, e)
            time.sleep(5 * (k + 1))


def total():
    with urllib.request.urlopen(URL + "?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms:lokale&resultType=hits&bbox=" + BBOX,
                                timeout=120) as r:
        return int(re.search(rb'numberMatched="(\d+)"', r.read()).group(1))


def parse(path):
    rows = []
    for m in ET.parse(path).getroot().iter("{http://mapserver.gis.umn.edu/mapserver}lokale"):
        row = {}
        for el in m:
            tag = el.tag.split("}")[1]
            if tag == "GEOMETRIA":
                pos = el.find(".//" + NS_GML + "pos")
                if pos is not None:
                    n, e = pos.text.split()[:2]   # GML axis order for EPSG:2180: northing, easting
                    row["x"], row["y"] = e, n
            elif tag != "boundedBy":
                row[tag] = "".join(el.itertext()).strip()   # DOK_DATA nests <gml:timePosition>
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="only print the counts from the existing CSV")
    a = ap.parse_args()
    csv_path = OUT / "rcn_lokale.csv"
    if not a.report:
        RAW.mkdir(parents=True, exist_ok=True)
        n = total()
        print("features in bbox:", n)
        for start in range(0, n, PAGE):
            p = RAW / ("p%06d.gml" % start)
            if p.exists():
                continue
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(get(start))
            tmp.replace(p)
            if (start // PAGE) % 20 == 0:
                print("  page", start // PAGE, "of", -(-n // PAGE), flush=True)
        rows = []
        for p in sorted(RAW.glob("p*.gml")):
            rows += parse(p)
        fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("gid", "TERYT"), k))
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print("wrote", csv_path, len(rows), "rows,", len(fields), "fields")
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    print("TERYT:", Counter(r.get("TERYT") for r in rows).most_common(6))
    print("function:", Counter(r.get("LOK_FUNKCJA") for r in rows).most_common(6))
    yr = Counter((r.get("DOK_DATA") or "")[:4] for r in rows if r.get("LOK_FUNKCJA") == "mieszkalna" and r.get("TERYT") == "1061")
    print("residential, TERYT 1061, by year:", sorted(yr.items()))
    dup = len(rows) - len({r.get("gid") for r in rows})
    assert dup == 0, "duplicate gid %d: paging unstable" % dup
    print("duplicate gid: 0")


if __name__ == "__main__":
    main()
