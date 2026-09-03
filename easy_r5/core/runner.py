"""Spawn EasyR5Runner as a child process and drive it.

Pure stdlib. No QGIS import at module level — ``run_job`` takes a duck-typed
``feedback`` (``pushInfo`` / ``pushWarning`` / ``reportError`` / ``pushDebugInfo``
/ ``isCanceled`` / ``setProgress``), so the parser and process handling are
unit-testable outside QGIS against a fake process.

The stdout protocol (PRD 3.2) is frozen. Later milestones add commands to the
Java side; they must not change these six verbs:

    INFO      <text>
    PROGRESS  <done> <total>
    WARN      <code> <text>
    ERROR     <code> <text>      -> runner exits 1
    RESULT    <key>=<value>
    DONE      <path> <rowcount>  -> success, last line, exit 0
"""

from __future__ import annotations

import re
import subprocess  # nosec B404 — cmd is built from our own recorded jdk/jar paths
import sys
from dataclasses import dataclass, field

from . import pins

_KNOWN_VERBS = ("INFO", "PROGRESS", "WARN", "ERROR", "RESULT", "DONE")
_CODE_RE = re.compile(r"^[A-Z][A-Z_]*$")
_LOG_TAIL_BYTES = 4096

# Stable error codes (PRD 3.2). English base strings; the Processing algorithm
# wraps the result in self.tr(). {text} is the raw engine detail; {r5} the R5
# version. map_message fills them in.
ERROR_MESSAGES = {
    "NETWORK_VERSION_MISMATCH": (
        "This network.dat was built with a different R5 version and cannot be "
        "read by R5 {r5}. Rebuild it with BuildNetwork (available from milestone "
        "M2). Engine detail: {text}"
    ),
    "NETWORK_READ_FAILED": (
        "R5 could not read the network file. It may be corrupt or truncated. "
        "Rebuild it with BuildNetwork. Engine detail: {text}"
    ),
    "OUT_OF_MEMORY": (
        "R5 ran out of memory. Increase the Java heap in the plugin settings, "
        "or analyse a smaller area. Engine detail: {text}"
    ),
    "NO_POINTS_LINKED": (
        "No origin/destination points could be linked to the street network. "
        "Check that your points fall within the OSM extent used to build the "
        "network. Engine detail: {text}"
    ),
    "DATE_NO_SERVICE": (
        "The GTFS feed has no trips running on the requested date. Pick a date "
        "with service. Engine detail: {text}"
    ),
    "BAD_JOB_SPEC": (
        "Internal error: the job sent to R5 was malformed ({text}). Please "
        "report this."
    ),
    "IO_ERROR": "R5 could not read or write a required file: {text}",
}


class RunnerError(RuntimeError):
    """The runner reported ERROR or exited non-zero. Carries the stable code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class RunnerCancelled(RuntimeError):
    """feedback.isCanceled() went True; the child was terminated."""


@dataclass
class RunnerEvent:
    kind: str
    text: str = ""
    code: str = ""
    done: int = 0
    total: int = 0
    key: str = ""
    value: str = ""
    path: str = ""
    rowcount: int = 0


@dataclass
class RunnerResult:
    results: dict = field(default_factory=dict)
    done_path: str = ""
    done_rowcount: int = 0
    warnings: list = field(default_factory=list)


def parse_line(line):
    """Parse one stdout line into a RunnerEvent, or None if it is not protocol.

    Raw Java logging (``WARNING: sun.misc.Unsafe...``, log4j ``WARN  c.c.r5 -``,
    stack traces, blanks) and a truncated final line all return None; the caller
    routes those to pushDebugInfo.
    """
    if not line or not line.strip():
        return None
    parts = line.split(None, 1)
    verb = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    if verb not in _KNOWN_VERBS:
        return None

    if verb == "INFO":
        return RunnerEvent("INFO", text=rest)

    if verb == "PROGRESS":
        bits = rest.split()
        if len(bits) != 2:
            return None
        try:
            return RunnerEvent("PROGRESS", done=int(bits[0]), total=int(bits[1]))
        except ValueError:
            return None

    if verb == "RESULT":
        key, sep, value = rest.partition("=")
        key = key.strip()
        if not sep or not key or " " in key:
            return None
        return RunnerEvent("RESULT", key=key, value=value.strip())

    if verb in ("WARN", "ERROR"):
        code, _, text = rest.partition(" ")
        if not _CODE_RE.match(code):
            # e.g. a log4j line "WARN  com.conveyal.r5... - message"
            return None
        return RunnerEvent(verb, code=code, text=text.strip())

    if verb == "DONE":
        head, _, tail = rest.rpartition(" ")
        try:
            rowcount = int(tail)
            path = head.strip()
        except ValueError:
            path, rowcount = rest, 0
        return RunnerEvent("DONE", path=path, rowcount=rowcount)

    return None  # pragma: no cover - all verbs handled above


def map_message(code, text, r5_version=pins.R5_VERSION):
    """Turn a stable error code + engine detail into a user-facing message."""
    template = ERROR_MESSAGES.get(code)
    if template is None:
        return text or "R5 runner failed (no detail provided)."
    return template.format(text=text or "(none)", r5=r5_version)


def _log(feedback, method, msg):
    if feedback is None:
        return
    try:
        getattr(feedback, method)(msg)
    except Exception:  # nosec B110 — feedback is best-effort
        pass


def _popen_kwargs():
    """Windows: keep the java.exe child in its own group and windowless."""
    if sys.platform == "win32":
        return {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        }
    return {}


def _log_tail(path, n=_LOG_TAIL_BYTES):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return "(log unavailable)"


def _terminate(proc, feedback=None):
    """Terminate proc; on Windows finish with taskkill /F /T as a tree-kill.

    The Java process must never be orphaned — this runs from run_job's finally,
    on cancel and on exception.
    """
    if proc.poll() is not None:
        return
    pid = proc.pid
    _log(feedback, "pushDebugInfo", "Terminating R5 process (pid={})...".format(pid))
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    except Exception:  # nosec B110 — escalation below
        pass

    if proc.poll() is None and sys.platform == "win32":
        try:
            subprocess.run(  # nosec B603 B607 — literal cmd, pid is our own child
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:  # nosec B110
            pass

    if proc.poll() is None:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:  # nosec B110
            pass

    if proc.poll() is None:
        _log(
            feedback,
            "pushWarning",
            "R5 process pid={} still alive after full kill attempt "
            "— end it manually in Task Manager.".format(pid),
        )


def run_job(cmd, feedback, *, cwd, stderr_log, r5_version=pins.R5_VERSION):
    """Run ``cmd``, stream its stdout protocol, return a RunnerResult.

    Raises RunnerCancelled if feedback.isCanceled() goes True, RunnerError on a
    reported ERROR or a non-zero exit. Never deletes anything it did not create;
    the caller owns ``cwd`` and ``stderr_log``.
    """
    _log(feedback, "pushDebugInfo", "$ " + subprocess.list2cmdline(cmd))

    result = RunnerResult()
    error = None  # (code, text)
    done_seen = False
    rc = -1
    err_fh = open(stderr_log, "wb")
    proc = None
    try:
        proc = subprocess.Popen(  # nosec B603 — cmd from our recorded jdk/jar paths
            cmd,
            stdout=subprocess.PIPE,
            stderr=err_fh,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=str(cwd),
            **_popen_kwargs(),
        )
        for raw in proc.stdout:
            if feedback is not None and feedback.isCanceled():
                _terminate(proc, feedback)
                raise RunnerCancelled("R5 run cancelled by user.")
            line = raw.rstrip("\r\n")
            ev = parse_line(line)
            if ev is None:
                _log(feedback, "pushDebugInfo", line)
                continue
            if ev.kind == "INFO":
                _log(feedback, "pushInfo", ev.text)
            elif ev.kind == "PROGRESS":
                if ev.total > 0:
                    _log(feedback, "setProgress", 100.0 * ev.done / ev.total)
            elif ev.kind == "WARN":
                result.warnings.append((ev.code, ev.text))
                _log(feedback, "pushWarning", map_message(ev.code, ev.text, r5_version))
            elif ev.kind == "RESULT":
                result.results[ev.key] = ev.value
            elif ev.kind == "ERROR":
                error = (ev.code, ev.text)
            elif ev.kind == "DONE":
                result.done_path = ev.path
                result.done_rowcount = ev.rowcount
                done_seen = True
                break
        # Loop ended on DONE, ERROR, or stdout EOF: the child is exiting on its
        # own. Give it a moment before force-killing (killing a cleanly exiting
        # process would report a spurious non-zero code).
        try:
            rc = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _terminate(proc, feedback)
            rc = proc.poll() if proc.poll() is not None else -1
    except RunnerCancelled:
        raise
    except BaseException:
        if proc is not None:
            _terminate(proc, feedback)
        raise
    finally:
        err_fh.close()
        if proc is not None and proc.poll() is None:
            _terminate(proc, feedback)

    if error is not None:
        code, text = error
        raise RunnerError(
            code,
            map_message(code, text, r5_version) + "\n\n" + _log_tail(stderr_log),
        )
    if rc != 0:
        tail = _log_tail(stderr_log)
        if "OutOfMemoryError" in tail:
            raise RunnerError("OUT_OF_MEMORY", map_message("OUT_OF_MEMORY", tail, r5_version))
        raise RunnerError(
            "",
            "R5 runner exited with code {}.\n\n{}".format(rc, tail),
        )
    if not done_seen:
        raise RunnerError("", "R5 runner finished without a DONE line.\n\n" + _log_tail(stderr_log))

    return result
