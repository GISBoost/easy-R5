"""Per-hex estate + nearest stop for the web page (lodz-dostepnosc-godzinowa/data/hexinfo.json).

    py scripts/export_hexinfo.py <path to mapy-analizy/lodz-dostepnosc-godzinowa/data>

Hex i = feature i of data/hex.geojson. Estate = OSM estate polygon containing the hex centre (-1 = none).
Stop = nearest GTFS stop post (straight line, EPSG:2180); tram if the post lies within TRAM_BUF m of a tram line, else bus.
Output: {estates:[name], stops:[[name, 1=tram|0=bus]], o:[estate idx per hex], s:[stop idx per hex], d:[distance m per hex]}.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

TRAM_BUF = 20
DANE = Path(__file__).resolve().parents[1] / "submission" / "dane"
web = Path(sys.argv[1])

hexes = gpd.read_file(web / "hex.geojson").to_crs(2180)
cen = gpd.GeoDataFrame(geometry=hexes.geometry.centroid, crs=2180)
osi = gpd.read_file(DANE / "hekso_osiedla.shp").to_crs(2180)
stops = gpd.read_file(DANE / "siec" / "siec_przystanki.shp").to_crs(2180)
lines = gpd.read_file(DANE / "siec" / "siec_linie.shp").to_crs(2180)

tram = lines[lines["rodzaj"].str.contains("tram", case=False)].union_all().buffer(TRAM_BUF)
stops["tram"] = stops.geometry.within(tram).astype(int)

names = sorted(osi["nazwa"])
j = gpd.sjoin(cen, osi[["nazwa", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
o = [names.index(n) if isinstance(n, str) else -1 for n in j["nazwa"].reindex(cen.index)]

near = gpd.sjoin_nearest(cen, stops[["nazwa", "tram", "geometry"]], how="left", distance_col="d")
near = near[~near.index.duplicated()].reindex(cen.index)
uniq = sorted({(r.nazwa, int(r.tram)) for r in near.itertuples()})
s = [uniq.index((r.nazwa, int(r.tram))) for r in near.itertuples()]

out = {"estates": names, "stops": [list(u) for u in uniq], "o": o, "s": s, "d": [int(round(d)) for d in near["d"]]}
(web / "hexinfo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(o), "hexes;", sum(x < 0 for x in o), "outside estates;", len(uniq), "stop entries;", "max d", max(out["d"]), "m;",
      sum(u[1] for u in uniq), "tram entries")
