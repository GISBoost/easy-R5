"""End-to-end of the pieces DownloadRealizedGtfs orchestrates, without QGIS:
manifest fetch -> resolve asset -> download -> GTFS sniff.
run: py -m pytest easy_r5/test/test_realized_gtfs_flow.py -v"""

import functools
import http.server
import json
import threading
import zipfile

import pytest

from easy_r5.core import downloads
from easy_r5.core import gtfs_dashboard as gd


class _Feedback:
    def isCanceled(self):  # noqa: N802
        return False

    def setProgress(self, v):  # noqa: N802
        pass

    def pushInfo(self, m):  # noqa: N802
        pass


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "www"
    root.mkdir()

    # a real GTFS-shaped zip
    feed = root / "lodz_realized_2026-07-13_p50.zip"
    with zipfile.ZipFile(feed, "w") as z:
        for f in ("agency.txt", "stops.txt", "routes.txt", "trips.txt",
                  "stop_times.txt", "calendar.txt"):
            z.writestr("lodz_realized_2026-07-13/" + f, "header\n")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    base = "http://127.0.0.1:{}".format(srv.server_port)

    (root / "manifest.json").write_text(json.dumps({
        "generated_at": "2999-01-01T00:00:00Z",
        "cities": {
            "lodz": {
                "display_name": "Łódź",
                "days": [{
                    "date": "2026-07-13",
                    "status": "partial",
                    "assets": {
                        "p50": base + "/lodz_realized_2026-07-13_p50.zip",
                        "p85": None,
                        "static_gtfs": base + "/lodz_realized_2026-07-13_p50.zip",
                    },
                }],
            }
        },
    }), encoding="utf-8")

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    gd._MEMO.update(data=None, at=0.0, url=None)
    try:
        yield base, tmp_path
    finally:
        srv.shutdown()
        t.join(timeout=2)


def test_full_flow_downloads_a_valid_gtfs(server, tmp_path):
    base, work = server
    manifest = gd.fetch_manifest(url=base + "/manifest.json", cache_dir=work / "cache")

    assert gd.day_status(manifest, "lodz", "2026-07-13") == "partial"
    url = gd.resolve_asset(manifest, "lodz", "2026-07-13", "p50")

    dest_dir = work / "transit-recordings" / "lodz" / "2026-07-13" / "p50"
    dest = dest_dir / url.rsplit("/", 1)[-1]
    downloads.download_file(url, dest, feedback=_Feedback(), user_agent="test")

    assert dest.is_file()
    assert zipfile.ZipFile(dest).testzip() is None
    assert gd.zip_is_gtfs(dest)
    assert gd.zip_missing_gtfs(dest) == []


def test_full_flow_missing_variant_is_reported(server, tmp_path):
    base, work = server
    manifest = gd.fetch_manifest(url=base + "/manifest.json", cache_dir=work / "cache")
    with pytest.raises(gd.ManifestError, match="Available: p50, static_gtfs"):
        gd.resolve_asset(manifest, "lodz", "2026-07-13", "p85")
