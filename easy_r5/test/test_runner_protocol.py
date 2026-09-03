"""stdout protocol parser + run_job against a fake process (no Java).

Run: py -m pytest easy_r5/test/test_runner_protocol.py -v
"""

import sys
import textwrap

import pytest

from easy_r5.core import runner
from easy_r5.core.runner import (
    RunnerCancelled,
    RunnerError,
    parse_line,
    run_job,
)


# --- parse_line ------------------------------------------------------------

def test_parse_info():
    ev = parse_line("INFO Loading network: C:/x/net.dat")
    assert ev.kind == "INFO" and ev.text == "Loading network: C:/x/net.dat"


def test_parse_result():
    ev = parse_line("RESULT stops=1619")
    assert ev.kind == "RESULT" and ev.key == "stops" and ev.value == "1619"


def test_parse_result_value_with_equals():
    ev = parse_line("RESULT bounds=18.3,54.2,18.9,54.5")
    assert ev.key == "bounds" and ev.value == "18.3,54.2,18.9,54.5"


def test_parse_progress():
    ev = parse_line("PROGRESS 3 10")
    assert ev.done == 3 and ev.total == 10


def test_parse_progress_bad_returns_none():
    assert parse_line("PROGRESS soon") is None


def test_parse_done():
    ev = parse_line("DONE C:/x/net.dat 0")
    assert ev.kind == "DONE" and ev.path == "C:/x/net.dat" and ev.rowcount == 0


def test_parse_done_path_with_spaces():
    ev = parse_line("DONE /tmp/a b/net.dat 5")
    assert ev.path == "/tmp/a b/net.dat" and ev.rowcount == 5


def test_parse_error_with_code():
    ev = parse_line("ERROR NETWORK_VERSION_MISMATCH nv4 != nv5")
    assert ev.kind == "ERROR" and ev.code == "NETWORK_VERSION_MISMATCH"
    assert ev.text == "nv4 != nv5"


def test_parse_warn_with_code():
    ev = parse_line("WARN NO_POINTS_LINKED 3 of 900 unlinked")
    assert ev.kind == "WARN" and ev.code == "NO_POINTS_LINKED"


def test_ignores_raw_java_log():
    assert parse_line(
        "WARNING: sun.misc.Unsafe::arrayBaseOffset has been called by "
        "com.esotericsoftware.kryo.unsafe.UnsafeUtil"
    ) is None


def test_ignores_logback_line():
    # logback default console line: verb-like token "2026-09-02" is not known.
    assert parse_line(
        "2026-09-02 20:47:56,814 [main] INFO  c.c.r.k.KryoNetworkSerializer - "
        "Reading transport network..."
    ) is None


def test_ignores_log4j_style_warn_line():
    # "WARN" verb but the next token is not an ALL_CAPS code -> not protocol.
    assert parse_line("WARN  c.c.r5.kryo.KryoNetworkSerializer - something") is None


def test_truncated_final_line():
    assert parse_line("RES") is None
    assert parse_line("") is None


# --- run_job against a fake process --------------------------------------

class _Feedback:
    def __init__(self, cancel_after=None):
        self.info = []
        self.warn = []
        self.debug = []
        self.progress = []
        self._cancel_after = cancel_after
        self._checks = 0

    def pushInfo(self, m):
        self.info.append(m)

    def pushWarning(self, m):
        self.warn.append(m)

    def pushDebugInfo(self, m):
        self.debug.append(m)

    def reportError(self, m):
        self.info.append(m)

    def setProgress(self, p):
        self.progress.append(p)

    def isCanceled(self):
        self._checks += 1
        if self._cancel_after is not None and self._checks > self._cancel_after:
            return True
        return False


def _fake_proc(tmp_path, body):
    script = tmp_path / "fake_runner.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return [sys.executable, str(script)]


def _run(tmp_path, body, feedback=None):
    fb = feedback or _Feedback()
    cmd = _fake_proc(tmp_path, body)
    return run_job(
        cmd, fb, cwd=tmp_path, stderr_log=tmp_path / "stderr.log"
    ), fb


def test_run_job_happy_path(tmp_path):
    result, fb = _run(tmp_path, """
        print("INFO loading")
        print("RESULT stops=1619")
        print("RESULT timezone=Europe/Warsaw")
        print("DONE net.dat 0")
    """)
    assert result.results == {"stops": "1619", "timezone": "Europe/Warsaw"}
    assert result.done_path == "net.dat"
    assert "loading" in fb.info


def test_run_job_routes_java_noise_to_debug(tmp_path):
    result, fb = _run(tmp_path, """
        print("2026-09-02 20:47:56,814 [main] INFO  c.c.r.k.X - Reading...")
        print("WARNING: sun.misc.Unsafe::arrayBaseOffset has been called")
        print("RESULT stops=5")
        print("DONE net.dat 0")
    """)
    assert result.results == {"stops": "5"}
    assert any("Unsafe" in d for d in fb.debug)
    assert fb.warn == []


def test_run_job_error_line(tmp_path):
    with pytest.raises(RunnerError) as exc:
        _run(tmp_path, """
            import sys
            print("ERROR NETWORK_VERSION_MISMATCH nv4 requires nv5")
            sys.exit(1)
        """)
    assert exc.value.code == "NETWORK_VERSION_MISMATCH"
    assert "different R5 version" in str(exc.value)


def test_run_job_oom_from_exit_code(tmp_path):
    with pytest.raises(RunnerError) as exc:
        _run(tmp_path, """
            import sys
            sys.stderr.write("java.lang.OutOfMemoryError: Java heap space\\n")
            sys.exit(1)
        """)
    assert exc.value.code == "OUT_OF_MEMORY"


def test_run_job_no_done_line(tmp_path):
    with pytest.raises(RunnerError, match="without a DONE line"):
        _run(tmp_path, """
            print("INFO x")
            print("RES")
        """)


def test_run_job_cancel(tmp_path):
    fb = _Feedback(cancel_after=1)
    with pytest.raises(RunnerCancelled):
        _run(tmp_path, """
            import time
            print("INFO one", flush=True)
            print("INFO two", flush=True)
            time.sleep(5)
            print("DONE net.dat 0")
        """, feedback=fb)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows creationflags only")
def test_popen_kwargs_windowless():
    import subprocess

    kw = runner._popen_kwargs()
    flags = kw["creationflags"]
    assert flags & subprocess.CREATE_NO_WINDOW
    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
