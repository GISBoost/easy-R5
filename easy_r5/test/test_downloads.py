"""Shared download / extraction plumbing. Pure Python (no qgis) —
run: py -m pytest easy_r5/test/test_downloads.py -v"""

import functools
import http.server
import threading
import zipfile

import pytest

from easy_r5.core.downloads import (
    DownloadCancelled,
    DownloadError,
    check_free_space,
    check_writable,
    download_file,
    safe_extract_zip,
)


class _Feedback:
    """Minimal stand-in for QgsProcessingFeedback."""

    def __init__(self, cancel_after=None):
        self.progress = []
        self._cancel_after = cancel_after
        self._checks = 0

    def isCanceled(self):  # noqa: N802 — Qt name
        self._checks += 1
        return self._cancel_after is not None and self._checks > self._cancel_after

    def setProgress(self, v):  # noqa: N802 — Qt name
        self.progress.append(v)

    def pushInfo(self, _):  # noqa: N802 — Qt name
        pass


@pytest.fixture
def http_server(tmp_path):
    """Serve tmp_path/srv over HTTP on a background thread; yields (base_url, srv_dir)."""
    srv_dir = tmp_path / "srv"
    srv_dir.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(srv_dir))
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield "http://127.0.0.1:{}".format(srv.server_port), srv_dir
    finally:
        srv.shutdown()
        t.join(timeout=2)


def test_download_file_writes_and_reports_progress(http_server, tmp_path):
    base, srv_dir = http_server
    (srv_dir / "payload.bin").write_bytes(b"x" * 500_000)
    dest = tmp_path / "out" / "payload.bin"
    dest.parent.mkdir()
    fb = _Feedback()

    download_file(base + "/payload.bin", dest, feedback=fb, user_agent="test")

    assert dest.read_bytes() == b"x" * 500_000
    assert not (dest.parent / "payload.bin.tmp").exists()
    assert fb.progress and fb.progress[-1] == 100


def test_download_file_expected_bytes_mismatch(http_server, tmp_path):
    base, srv_dir = http_server
    (srv_dir / "p").write_bytes(b"y" * 1000)
    with pytest.raises(DownloadError, match="expected"):
        download_file(base + "/p", tmp_path / "p", feedback=_Feedback(),
                      user_agent="test", expected_bytes=999_999)


def test_download_file_404_is_download_error(http_server, tmp_path):
    base, _ = http_server
    with pytest.raises(DownloadError):
        download_file(base + "/nope", tmp_path / "x", feedback=_Feedback(), user_agent="test")
    assert not (tmp_path / "x.tmp").exists()


def test_download_file_cancel_cleans_up(http_server, tmp_path):
    base, srv_dir = http_server
    (srv_dir / "big").write_bytes(b"z" * 5_000_000)
    with pytest.raises(DownloadCancelled):
        download_file(base + "/big", tmp_path / "big", feedback=_Feedback(cancel_after=0),
                      user_agent="test")
    assert not (tmp_path / "big.tmp").exists()
    assert not (tmp_path / "big").exists()


def test_safe_extract_zip_normal(tmp_path):
    src = tmp_path / "a.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("gtfs/stops.txt", "stop_id\n1\n")
        z.writestr("gtfs/routes.txt", "route_id\nA\n")
    out = tmp_path / "out"
    written = safe_extract_zip(src, out)
    assert (out / "gtfs" / "stops.txt").read_text().startswith("stop_id")
    assert set(written) == {"gtfs/stops.txt", "gtfs/routes.txt"}


def test_safe_extract_zip_skips_zip_slip(tmp_path):
    src = tmp_path / "evil.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("../escaped.txt", "pwned")
        z.writestr("ok.txt", "fine")
    out = tmp_path / "out"
    out.mkdir()
    safe_extract_zip(src, out)
    assert not (tmp_path / "escaped.txt").exists()
    assert (out / "ok.txt").read_text() == "fine"


def test_check_writable_and_free_space(tmp_path):
    check_writable(tmp_path)                      # no raise
    check_free_space(tmp_path, 1)                 # 1 MB always available
    with pytest.raises(DownloadError):
        check_writable(tmp_path / "does" / "not" / "exist")
    with pytest.raises(DownloadError):
        check_free_space(tmp_path, 10 ** 12)      # 1 PB — never available
