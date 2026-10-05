"""M2: download the Lodz strategic noise map (immission bands) from the city's ArcGIS REST service.

The service has no pagination, so features are fetched by OBJECTID chunks. Output:
data/noise/<source>_<ind>.json (Esri JSON, EPSG:2180, fields LMIN, LMAX; readable by OGR). Plain system Python (urllib).
Source: Urzad Miasta Lodzi, InterSIT (mapa.lodz.pl), measurements 2022. Licence: not stated by the
service -- see docs/notes/apartment-finder-m0.md; must be confirmed before publishing.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://mapa.lodz.pl/3/rest/services/WOSIR/Akustyczna/MapServer"
LAYERS = {  # layer id -> (source, indicator)
    15: ("road", "lden"), 16: ("road", "ln"),
    17: ("tram", "lden"), 18: ("tram", "ln"),
    19: ("rail", "lden"), 20: ("rail", "ln"),
    21: ("industry", "lden"), 22: ("industry", "ln"),
}
HERE = Path(__file__).resolve().parents[1]
CHUNK = 20


def get(layer, **params):
    url = "%s/%d/query?%s" % (BASE, layer, urllib.parse.urlencode(params))
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def fetch_ids(layer, ids):
    """Esri JSON features for ids; halves the chunk when the server refuses (huge band polygons)."""
    try:
        r = get(layer, objectIds=",".join(map(str, ids)), outFields="LMIN,LMAX", outSR=2180,
                maxAllowableOffset=0.5, f="json")
        if "error" in r:
            raise RuntimeError(r["error"])
        return r
    except Exception:
        if len(ids) == 1:  # the service sometimes times out on a heavy polygon: retry with a pause
            for wait in (5, 15, 30, 60):
                time.sleep(wait)
                try:
                    r = get(layer, objectIds=str(ids[0]), outFields="LMIN,LMAX", outSR=2180, maxAllowableOffset=0.5, f="json")
                    if "error" not in r:
                        return r
                except Exception:
                    pass
            raise
        h = len(ids) // 2
        a, b = fetch_ids(layer, ids[:h]), fetch_ids(layer, ids[h:])
        a["features"] += b["features"]
        return a


def main():
    out = HERE / "data/noise"
    out.mkdir(parents=True, exist_ok=True)
    for layer, (src, ind) in LAYERS.items():
        if (out / ("%s_%s.json" % (src, ind))).exists():
            continue  # resumable
        ids = sorted(get(layer, where="1=1", returnIdsOnly="true", f="json")["objectIds"])
        doc = None
        for i in range(0, len(ids), CHUNK):
            part = fetch_ids(layer, ids[i:i + CHUNK])
            if doc is None:
                doc = part
            else:
                doc["features"] += part["features"]
        assert len(doc["features"]) == len(ids), (layer, len(doc["features"]), len(ids))
        (out / ("%s_%s.json" % (src, ind))).write_text(json.dumps(doc), encoding="utf-8")  # Esri JSON, EPSG:2180
        print(src, ind, len(ids), "features", file=sys.stderr)


if __name__ == "__main__":
    main()
