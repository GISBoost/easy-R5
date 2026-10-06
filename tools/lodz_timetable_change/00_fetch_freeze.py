"""Step 0 of S3: freeze the Lodz tidy + static GTFS release assets and record checksums.

    py -I 00_fetch_freeze.py            # fetch everything missing, refresh manifest + gap list

Stdlib + PyYAML only. Idempotent: existing non-empty files are kept (their SHA-256 is still
recorded). 404 means "no release/asset that day" and is logged as `missing`, never an error.
Writes <data_dir>/raw/<kind>/<file>, <data_dir>/fetch_manifest.jsonl and <data_dir>/gaps.txt.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
SRC, FETCH = CFG["source"], CFG["fetch"]
DATA = Path(CFG["data_dir"])


def tag_dates() -> list[str]:
    """Days that have a release tag, from `git ls-remote --tags` (no API, no auth)."""
    out = subprocess.run(
        ["git", "ls-remote", "--tags", f"https://github.com/{SRC['repo']}.git"],
        capture_output=True, text=True, check=True,
    ).stdout
    pat = re.compile(r"refs/tags/" + SRC["tag"].format(city=SRC["city"], date=r"(\d{4}-\d{2}-\d{2})") + r"$", re.M)
    return sorted(set(pat.findall(out)))


def url_for(kind: str, date: str) -> str:
    tag = SRC["tag"].format(city=SRC["city"], date=date)
    name = SRC["assets"][kind].format(city=SRC["city"], date=date)
    return f"https://github.com/{SRC['repo']}/releases/download/{tag}/{name}"


def fetch(url: str, dest: Path) -> tuple[str, str | None]:
    """Return (status, last_modified). Status: ok | cached | missing."""
    if dest.exists() and dest.stat().st_size > 0:
        return "cached", None
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, FETCH["retries"] + 1):
        try:
            with urllib.request.urlopen(url, timeout=FETCH["timeout_s"]) as resp, open(part, "wb") as f:
                lm = resp.headers.get("Last-Modified")
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
            part.replace(dest)
            return "ok", lm
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "missing", None
            if attempt == FETCH["retries"]:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == FETCH["retries"]:
                raise
        time.sleep(2 * attempt)
    return "missing", None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    days = tag_dates()
    start = FETCH["from"]
    end = FETCH["to"] or days[-1]
    days = [d for d in days if start <= d <= end]
    all_days = {(dt.date.fromisoformat(start) + dt.timedelta(n)).isoformat()
                for n in range((dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1)}
    gaps = sorted(all_days - set(days))

    for kind in SRC["assets"]:
        (DATA / "raw" / kind).mkdir(parents=True, exist_ok=True)

    rows = []
    for d in days:
        wd = dt.date.fromisoformat(d).weekday() < 5
        for kind in SRC["assets"]:
            if kind == "tidy" and not (wd and d >= FETCH["tidy_weekdays_from"]):
                continue
            dest = DATA / "raw" / kind / SRC["assets"][kind].format(city=SRC["city"], date=d)
            status, lm = fetch(url_for(kind, d), dest)
            row = {"date": d, "kind": kind, "status": status, "file": str(dest.relative_to(DATA)) if status != "missing" else None}
            if status != "missing":
                row.update(size=dest.stat().st_size, sha256=sha256(dest), last_modified=lm)
            rows.append(row)
            print(d, kind, status, row.get("size", ""))

    with open(DATA / "fetch_manifest.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    missing = [f"{r['date']} {r['kind']}" for r in rows if r["status"] == "missing"]
    (DATA / "gaps.txt").write_text(
        "# days without a release tag\n" + "\n".join(gaps) + "\n# tag exists, asset missing\n" + "\n".join(missing) + "\n",
        encoding="utf-8",
    )
    print(f"done: {len(rows)} entries, {len(gaps)} days without tag, {len(missing)} missing assets")


if __name__ == "__main__":
    main()
