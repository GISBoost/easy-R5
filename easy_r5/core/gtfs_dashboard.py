"""Client for the ``gtfs-dashboard`` manifest — the index of realized / static
GTFS that ``easy-GTFS-RT`` publishes.

``gisboost.github.io/gtfs-dashboard/manifest.json`` is a plain static file on the
GitHub Pages CDN (not ``api.github.com``), so reading it is not subject to the
REST API's 60 req/h cap. It already carries fully-qualified release-asset URLs,
so the plugin never has to touch the Releases API or match tag patterns.

This module is the only thing that knows the manifest's shape. It has no ``qgis``
import — the algorithm passes the URL in (resolving any QSettings override on its
side) and maps ``ManifestError`` to ``QgsProcessingException``.

Manifest schema (the parts we keep after :func:`slim`)::

    {
      "generated_at": "2026-08-15T...Z",
      "cities": {
        "<key>": {
          "display_name": "Łódź",
          "days": [
            {"date": "2026-07-13", "status": "ok" | "partial",
             "assets": {"p50": "<url>|null", "p85": "...", "static_gtfs": "..."}}
          ]
        }
      }
    }
"""

from __future__ import annotations

import datetime
import json
import re
import time
import zipfile
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

from . import pins

MANIFEST_URL = "https://gisboost.github.io/gtfs-dashboard/manifest.json"
CACHE_FILENAME = "gtfs_dashboard_manifest.json"

# order = the dialog's default priority; also the algorithm's VARIANT enum order
VARIANTS = ("p50", "p85", "static_gtfs")
VARIANT_DIRNAME = {"p50": "p50", "p85": "p85", "static_gtfs": "static"}
VARIANT_LABELS = (
    "Realized — median (P50)",
    "Realized — conservative (P85)",
    "Scheduled (static GTFS for that day)",
)

_GTFS_REQUIRED = ("agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# in-process memo so the dialog's fetch and the algorithm's fetch share one round trip
_MEMO: "dict" = {"data": None, "at": 0.0, "url": None}


class ManifestError(RuntimeError):
    """The manifest could not be fetched, or is not in the expected shape."""


def fetch_manifest(*, url: "str | None" = None, cache_dir: "Path | None" = None,
                   max_age_s: int = 86400, feedback=None, force: bool = False) -> dict:
    """Return the slimmed manifest — from memory, the network, or the disk cache.

    On a network / parse failure, falls back to ``<cache_dir>/<CACHE_FILENAME>``
    if present, tagging the result ``{"_stale": True, "_error": "..."}``; with no
    cache, raises :class:`ManifestError` with a pointer to the Releases page.
    """
    url = url or MANIFEST_URL
    now = time.time()
    if (not force and _MEMO["data"] is not None and _MEMO["url"] == url
            and now - _MEMO["at"] < max_age_s):
        return _MEMO["data"]

    cache_file = Path(cache_dir) / CACHE_FILENAME if cache_dir else None
    try:
        data = slim(_http_get_json(url))
        _MEMO.update(data=data, at=now, url=url)
        if cache_file is not None:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(data), encoding="utf-8")
            except OSError:
                pass
        return data
    except (URLError, ValueError, TimeoutError, OSError) as exc:
        if cache_file is not None and cache_file.is_file():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                return {**cached, "_stale": True, "_error": str(exc)}
            except (OSError, ValueError):
                pass
        raise ManifestError(
            "Could not fetch the recordings list from gtfs-dashboard and there is "
            "no local copy ({}). Check your connection, or download a feed "
            "manually from https://github.com/GISBoost/easy-GTFS-RT/releases".format(exc)
        )


def _http_get_json(url: str) -> dict:
    req = urllib_request.Request(url, headers={"User-Agent": pins.USER_AGENT})
    with urllib_request.urlopen(req, timeout=30) as resp:  # nosec B310 — caller-supplied URL, parsed as JSON only
        return json.loads(resp.read().decode("utf-8"))


def slim(manifest: dict) -> dict:
    """Keep only what the plugin needs; idempotent so a cached slim reslims fine."""
    cities_in = manifest.get("cities")
    if not isinstance(cities_in, dict) or not cities_in:
        raise ManifestError(
            "The gtfs-dashboard manifest is empty or in an unknown format — "
            "report it at https://github.com/GISBoost/gtfs-dashboard/issues"
        )
    out = {}
    for key, city in cities_in.items():
        days_out = []
        for d in city.get("days", []):
            assets = d.get("assets") or {}
            days_out.append({
                "date": d.get("date"),
                "status": d.get("status", "ok"),
                "assets": {v: assets.get(v) for v in VARIANTS},
            })
        out[key] = {"display_name": city.get("display_name") or key, "days": days_out}
    return {"generated_at": manifest.get("generated_at"), "cities": out}


def is_stale(manifest: dict) -> bool:
    return bool(manifest.get("_stale"))


def generated_age_hours(manifest: dict) -> "float | None":
    raw = manifest.get("generated_at")
    if not raw:
        return None
    try:
        ts = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - ts).total_seconds() / 3600.0


def cities(manifest: dict) -> "list[tuple[str, str]]":
    """``[(key, display_name)]`` sorted by display name."""
    return sorted(
        ((k, c["display_name"]) for k, c in manifest["cities"].items()),
        key=lambda t: t[1].lower(),
    )


def _city(manifest: dict, city_key: str) -> dict:
    c = manifest["cities"].get(city_key)
    if c is None:
        raise ManifestError(
            "No recordings for city '{}'. Available: {} (use the key, not the "
            "display name).".format(city_key, ", ".join(sorted(manifest["cities"])))
        )
    return c


def months(manifest: dict, city_key: str) -> "list[str]":
    """``["2026-08", "2026-07", ...]`` newest first."""
    c = _city(manifest, city_key)
    return sorted({d["date"][:7] for d in c["days"] if d.get("date")}, reverse=True)


def days(manifest: dict, city_key: str, month: str) -> "list[dict]":
    """Day entries in ``month`` (``"yyyy-MM"``), newest first."""
    c = _city(manifest, city_key)
    return sorted(
        (d for d in c["days"] if (d.get("date") or "").startswith(month)),
        key=lambda d: d["date"], reverse=True,
    )


def _nearest(dates: "list[str]", target: str, k: int = 3) -> "list[str]":
    try:
        t = datetime.date.fromisoformat(target)
    except ValueError:
        return dates[:k]

    def dist(s):
        try:
            return abs((datetime.date.fromisoformat(s) - t).days)
        except ValueError:
            return 10 ** 9

    return sorted(dates, key=dist)[:k]


def resolve_asset(manifest: dict, city_key: str, date: str, variant: str) -> str:
    """Return the asset URL, or raise :class:`ManifestError` with a helpful list."""
    if variant not in VARIANTS:
        raise ManifestError(
            "Unknown variant '{}'; use one of {}.".format(variant, ", ".join(VARIANTS))
        )
    if not _DATE_RE.match(date or ""):
        raise ManifestError("Date must be yyyy-MM-dd; got '{}'.".format(date))
    c = _city(manifest, city_key)
    day = next((d for d in c["days"] if d.get("date") == date), None)
    if day is None:
        have = [d["date"] for d in c["days"] if d.get("date")]
        near = _nearest(have, date, 3)
        raise ManifestError(
            "{} has no recording for {}. Nearest: {}.".format(
                c["display_name"], date, ", ".join(near) or "none"
            )
        )
    url = (day.get("assets") or {}).get(variant)
    if not url:
        have = [v for v in VARIANTS if (day.get("assets") or {}).get(v)]
        raise ManifestError(
            "{} {}: no '{}' build. Available: {}.".format(
                c["display_name"], date, variant, ", ".join(have) or "none"
            )
        )
    return url


def day_status(manifest: dict, city_key: str, date: str) -> str:
    c = _city(manifest, city_key)
    day = next((d for d in c["days"] if d.get("date") == date), None)
    return (day or {}).get("status", "ok")


def _gtfs_check(names: "set[str]") -> "list[str]":
    """Given a set of file basenames, return the GTFS files that are missing."""
    missing = [f for f in _GTFS_REQUIRED if f not in names]
    if "calendar.txt" not in names and "calendar_dates.txt" not in names:
        missing.append("calendar.txt or calendar_dates.txt")
    return missing


def zip_missing_gtfs(zip_path) -> "list[str]":
    """The GTFS files absent from ``zip_path`` (by basename, any nesting). Empty = OK.

    ``BuildNetwork`` takes a *folder of .zip feeds*, so ``DownloadRealizedGtfs``
    keeps the downloaded archive as-is; this only sanity-checks that it is a
    GTFS feed and not, say, an error page saved with a .zip name.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = {Path(n).name for n in zf.namelist()}
    except zipfile.BadZipFile:
        return list(_GTFS_REQUIRED)
    return _gtfs_check(names)


def zip_is_gtfs(zip_path) -> bool:
    return not zip_missing_gtfs(zip_path)
