"""Offer layer, step 1: every investment of the city with active offers from deweloperuch.pl, saved as JSON.

One request through the deweloperuch-mcp CLI (`investments search <city> --limit 500 --json`), which keeps the service's
rate limit and STOP lock; nothing here talks to the service directly. Output data/offer/investments_raw.json:
{"fetched": date, "cli": command, "result": the CLI JSON}. An existing file is kept unless --refresh (do not re-ask the
community-run service without a reason). Asking prices of developers, not transactions; source: deweloperuch.pl
(developers' price reports published on dane.gov.pl).

  py scripts/offer_fetch.py [--refresh] [--cli PATH]
"""
import argparse
import datetime
import json
import os
import subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/offer.yaml", encoding="utf-8"))
OUT = HERE / "data/offer"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="fetch again even if investments_raw.json exists")
    ap.add_argument("--cli", help="path of the deweloperuch executable instead of config source.cli")
    a = ap.parse_args()
    path = OUT / "investments_raw.json"
    if path.exists() and not a.refresh:
        print("kept", path, "(use --refresh to fetch again)")
    else:
        S = cfg["source"]
        cmd = ([a.cli] if a.cli else S["cli"]) + ["investments", "search", S["city_slug"], "--limit", str(S["limit"]), "--json"]
        r = subprocess.run(cmd, capture_output=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode:   # 3 = STOP: do not retry, see the deweloperuch-mcp docs (stop status / stop clear)
            raise SystemExit("deweloperuch CLI exit %d: %s" % (r.returncode, r.stderr.strip()[-500:]))
        res = json.loads(r.stdout)
        assert not res["truncated"] and res["returned"] < S["limit"], "investment list truncated: raise source.limit"
        OUT.mkdir(parents=True, exist_ok=True)
        json.dump({"fetched": datetime.date.today().isoformat(), "cli": cmd, "result": res}, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    d = json.load(open(path, encoding="utf-8"))
    it = d["result"]["items"]
    print("fetched", d["fetched"], "investments:", len(it), "with coordinates:", sum(1 for i in it if i.get("lat") and i.get("lng")),
          "active offers:", sum(i.get("offers_active") or 0 for i in it))


if __name__ == "__main__":
    main()
