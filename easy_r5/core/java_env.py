"""Locate and validate the Java 21 JDK and the R5 jar, compile the runner,
and pick a JVM heap size.

Pure stdlib. No QGIS / osgeo imports — unit-testable outside QGIS. QSettings is
read by the algorithms and passed in here as a plain dict, so this module never
touches Qt.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess  # nosec B404 — java/javac invoked by full recorded path
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import pins

_HASH_CHUNK = 1024 * 1024
_JAVA_VERSION_RE = re.compile(
    r'(?:java|openjdk)\s+version\s+"([^"]+)"', re.IGNORECASE
)
_MIN_HEAP_MB = 2048
_CAP_HEAP_MB = 12 * 1024
_FALLBACK_HEAP_MB = 4096


class JavaEnvError(RuntimeError):
    """The saved Java/R5 environment is incomplete or invalid."""


@dataclass
class ResolvedEnv:
    jdk_path: Path
    jar_path: Path
    runner_mode: str  # "compiled" | "source"
    runner_class_dir: Path
    runner_source_path: Path


# --- Java version -------------------------------------------------------------

def _major(version_str):
    """'21.0.5' -> 21, '1.8.0_402' -> 8, '21' -> 21."""
    m = re.match(r"(\d+)(?:\.(\d+))?", version_str)
    if not m:
        return None
    first = int(m.group(1))
    if first == 1 and m.group(2):
        return int(m.group(2))
    return first


def check_java_version(java_path):
    """Return ``(is_21_plus, version_str, error_msg)``. Never raises.

    Mirrors easy-OTP core.otp_server.check_java_version, threshold 21.
    """
    java_path = Path(java_path or "")
    if not java_path.name or not java_path.exists():
        return False, "", (
            "Java binary not found at '{}'. Run 'Download R5 engine and Java 21' "
            "first.".format(java_path)
        )
    try:
        proc = subprocess.run(  # nosec B603 — full path, fixed arg
            [str(java_path), "-version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "", "Could not run '{} -version': {}".format(java_path, exc)

    banner = (proc.stderr or proc.stdout or "").strip()
    first_line = banner.splitlines()[0] if banner else ""
    m = _JAVA_VERSION_RE.search(first_line)
    version = m.group(1) if m else ""
    major = _major(version) if version else None
    if major is not None and major >= pins.JDK_FEATURE_VERSION:
        return True, version, ""
    return False, version, (
        "R5 {} requires Java {}+ (a JDK). Detected '{}'. Run 'Download R5 engine "
        "and Java 21', or point the JDK path at a Temurin 21 install.".format(
            pins.R5_VERSION, pins.JDK_FEATURE_VERSION, version or "unknown"
        )
    )


# --- SHA-256 / jar sanity ----------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_HASH_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def verify_jar_sha256(path, expected):
    """Return ``(ok, computed_digest)``."""
    computed = sha256_file(path)
    return computed == expected.lower(), computed


def jar_sanity_ok(path):
    """Cheap structural check, in addition to (not instead of) the SHA-256."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return False
    if not pins.R5_JAR_MIN_BYTES <= size <= pins.R5_JAR_MAX_BYTES:
        return False
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path) as zf:
            return any(
                n.startswith("com/conveyal/r5/") for n in zf.namelist()[:5000]
            )
    except (OSError, zipfile.BadZipFile):
        return False


# --- RAM / heap ------------------------------------------------------------

def detect_ram_bytes():
    """Total physical RAM in bytes, or None if it cannot be determined."""
    try:
        if sys.platform == "win32":
            import ctypes

            class _MemStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MemStatusEx()
            stat.dwLength = ctypes.sizeof(_MemStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys)
            return None
        if sys.platform == "darwin":
            out = subprocess.run(  # nosec B603 B607 — fixed literal cmd
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            return int(out.stdout.strip())
        # linux and friends
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
        return None
    except Exception:  # nosec B110 — any failure means "unknown"
        return None


def heap_mb_for(ram_bytes, override_gb=None):
    """Return ``(xmx_mb, warning_or_None)``.

    Default: min(0.6 * RAM, 12 GB), floored at 2 GB (PRD 3.4). No RAM reading
    -> 4 GB + a warning.
    """
    if override_gb:
        return int(override_gb) * 1024, None
    if not ram_bytes:
        return _FALLBACK_HEAP_MB, (
            "Could not detect system RAM; defaulting the Java heap to 4 GB. "
            "Set a value in the plugin settings if R5 runs out of memory."
        )
    target_mb = int(min(0.6 * ram_bytes, _CAP_HEAP_MB * 1024 * 1024) / (1024 * 1024))
    return max(target_mb, _MIN_HEAP_MB), None


def xmx_arg(mb):
    return "-Xmx{}m".format(int(mb))


# --- runner compile + command ---------------------------------------------

def compile_runner(java_bin_dir, jar_path, source_path, class_dir):
    """javac the runner once. Return ``(mode, detail)``.

    ("compiled", class_dir) on success; ("source", source_path) if javac is
    unavailable or fails (the single-file source launcher then compiles on each
    run, ~0.8 s overhead — measured in the spike).
    """
    java_bin_dir = Path(java_bin_dir)
    class_dir = Path(class_dir)
    source_path = Path(source_path)
    class_dir.mkdir(parents=True, exist_ok=True)
    javac = java_bin_dir / ("javac.exe" if sys.platform == "win32" else "javac")
    if not javac.exists():
        return "source", "javac not found next to the JDK java binary"
    try:
        proc = subprocess.run(  # nosec B603 — full path, our own args
            [str(javac), "-cp", str(jar_path), "-d", str(class_dir), str(source_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "source", "javac could not be run: {}".format(exc)
    produced = class_dir / (pins.RUNNER_MAIN_CLASS + ".class")
    if proc.returncode == 0 and produced.exists():
        return "compiled", str(class_dir)
    return "source", (proc.stderr or proc.stdout or "javac failed").strip()[-1000:]


def resolve_env(settings_snapshot):
    """Build a validated ResolvedEnv from a ``settings.all_settings()`` dict."""
    jdk = Path(settings_snapshot.get("jdk_path", "") or "")
    jar = Path(settings_snapshot.get("r5_jar_path", "") or "")
    mode = settings_snapshot.get("runner_mode", "") or ""
    class_dir = Path(settings_snapshot.get("runner_class_dir", "") or "")
    source_path = Path(settings_snapshot.get("runner_source_path", "") or "")

    if not jdk.name or not jdk.exists():
        raise JavaEnvError(
            "No Java 21 JDK recorded. Run 'Download R5 engine and Java 21'."
        )
    if not jar.is_file():
        raise JavaEnvError(
            "No R5 jar recorded. Run 'Download R5 engine and Java 21'."
        )
    if mode == "compiled":
        if not (class_dir / (pins.RUNNER_MAIN_CLASS + ".class")).exists():
            raise JavaEnvError(
                "Compiled runner missing from '{}'. Re-run 'Download R5 engine "
                "and Java 21'.".format(class_dir)
            )
    elif mode == "source":
        if not source_path.is_file():
            raise JavaEnvError(
                "Runner source missing from '{}'. Reinstall the plugin.".format(
                    source_path
                )
            )
    else:
        raise JavaEnvError(
            "Runner not set up. Run 'Download R5 engine and Java 21'."
        )
    return ResolvedEnv(jdk, jar, mode, class_dir, source_path)


def build_java_command(env, xmx, job_json_path, extra_jvm_args=()):
    """Assemble the java command line for one runner invocation.

    ``extra_jvm_args`` (e.g. ``["-Djava.io.tmpdir=..."]``) go right after -Xmx.
    """
    jvm = [xmx, *extra_jvm_args]
    if env.runner_mode == "compiled":
        cp = "{}{}{}".format(env.jar_path, os.pathsep, env.runner_class_dir)
        return [str(env.jdk_path), *jvm, "-cp", cp, pins.RUNNER_MAIN_CLASS, str(job_json_path)]
    return [
        str(env.jdk_path), *jvm, "-cp", str(env.jar_path),
        str(env.runner_source_path), str(job_json_path),
    ]
