"""Bootstrap for the one optional dependency Easy-R5 is allowed to fetch.

CLAUDE.md permits exactly one narrow pip-free exception: ``openpyxl``, and only
for ``PreparePopulationLayer`` / ``PopulationOverlay`` (PRD §4.8). This is a
copy of easy-OTP's mechanism — pure-python wheel via ``urllib``, SHA-256
verified, no ``pip``, no shared package. Do not generalise it.

No QGIS or Qt imports — safe to call before ``QgsApplication`` is initialised.
"""

import hashlib
import importlib
import json
import os
import subprocess  # nosec B404 — pip fallback only, all args literal / from PyPI
import sys
import tempfile
import urllib.request
import zipfile

_OPENPYXL_VERSION = "3.1.5"        # pure-python wheel; requires Python >=3.8
_ET_XMLFILE_VERSION = "2.0.0"      # openpyxl's sole dependency
_PYPI_JSON_URL = "https://pypi.org/pypi/{pkg}/{version}/json"
_WHEEL_USER_AGENT = "easy-R5/0.1 urllib"
_HASH_CHUNK = 1 * 1024 * 1024


def ensure_openpyxl() -> bool:
    """True if openpyxl is importable now."""
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def _get_python_executable() -> str:
    """The real interpreter, not the QGIS launcher (``qgis-bin.exe`` on Windows)."""
    exe = sys.executable
    if "python" in os.path.basename(exe).lower():
        return exe
    for name in ("python.exe", "python3.exe"):
        candidate = os.path.join(sys.exec_prefix, name)
        if os.path.isfile(candidate):
            return candidate
    for name in ("python3", "python"):
        candidate = os.path.join(sys.exec_prefix, "bin", name)
        if os.path.isfile(candidate):
            return candidate
    return exe


def _add_user_site_to_path() -> None:
    try:
        import site
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.insert(0, user_site)
    except (AttributeError, TypeError):
        pass


def _safe_zipextract(zf: zipfile.ZipFile, dest_path: str) -> None:
    """Extract, skipping any member that would escape ``dest_path`` (zip slip)."""
    dest_root = os.path.realpath(dest_path)
    prefix = dest_root + os.sep
    for member in zf.infolist():
        target = os.path.realpath(os.path.join(dest_root, member.filename))
        if target != dest_root and not target.startswith(prefix):
            continue
        zf.extract(member, dest_root)


def _writable_target_dir() -> str:
    try:
        import site
        user_site = site.getusersitepackages()
        if user_site and site.ENABLE_USER_SITE:
            os.makedirs(user_site, exist_ok=True)
            probe = os.path.join(user_site, ".easy_r5_write_test")
            with open(probe, "w"):
                pass
            os.remove(probe)
            return user_site
    except Exception:  # nosec B110 — best-effort probe; explicit fallback follows
        pass
    vendor = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_vendor")
    os.makedirs(vendor, exist_ok=True)
    return vendor


def _resolve_wheel(pkg: str, version: str) -> "tuple[str, str]":
    url = _PYPI_JSON_URL.format(pkg=pkg, version=version)
    req = urllib.request.Request(url, headers={"User-Agent": _WHEEL_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 — hardcoded HTTPS pypi.org
        data = json.loads(resp.read().decode())
    for entry in data.get("urls", []):
        if (entry.get("packagetype") == "bdist_wheel"
                and entry["filename"].endswith("-none-any.whl")):
            return entry["url"], entry["digests"]["sha256"]
    raise RuntimeError(
        "No pure-python wheel (-none-any.whl) for {}=={} on PyPI.".format(pkg, version)
    )


def _fetch_and_extract_wheel(pkg: str, version: str, target_dir: str) -> None:
    wheel_url, expected = _resolve_wheel(pkg, version)
    with tempfile.NamedTemporaryFile(dir=target_dir, suffix=".whl", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        req = urllib.request.Request(wheel_url, headers={"User-Agent": _WHEEL_USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310 — URL from PyPI JSON, SHA-256 checked
            h = hashlib.sha256()
            with open(tmp_path, "wb") as fh:
                while True:
                    chunk = resp.read(_HASH_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    h.update(chunk)
        if h.hexdigest().lower() != expected.lower():
            raise RuntimeError(
                "SHA-256 mismatch for {} wheel: expected {}, got {}.".format(
                    pkg, expected, h.hexdigest())
            )
        with zipfile.ZipFile(tmp_path) as zf:
            _safe_zipextract(zf, target_dir)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _install_openpyxl_via_urllib() -> "tuple[bool, str]":
    try:
        target = _writable_target_dir()
        for pkg, ver in [("et_xmlfile", _ET_XMLFILE_VERSION), ("openpyxl", _OPENPYXL_VERSION)]:
            _fetch_and_extract_wheel(pkg, ver, target)
        if target not in sys.path:
            sys.path.insert(0, target)
        importlib.invalidate_caches()
        if ensure_openpyxl():
            return True, "openpyxl installed via urllib into {}".format(target)
        return False, "Wheel extracted but openpyxl still not importable — restart QGIS."
    except Exception as exc:  # noqa: BLE001
        return False, "In-process urllib wheel install failed: {}".format(exc)


def install_openpyxl() -> "tuple[bool, str]":
    """Try to make openpyxl importable: urllib wheel, then ``pip --user``, then ``pip``."""
    ok, msg = _install_openpyxl_via_urllib()
    if ok:
        return True, msg

    python_exe = _get_python_executable()
    base_cmd = [python_exe, "-m", "pip", "install", "openpyxl"]
    for extra in (["--user"], []):
        try:
            result = subprocess.run(  # nosec B603
                base_cmd + extra, capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return False, "pip timed out after 120 s."
        except OSError as exc:
            return False, "Could not launch pip: {}".format(exc)
        if result.returncode == 0:
            _add_user_site_to_path()
            importlib.invalidate_caches()
            if ensure_openpyxl():
                return True, "openpyxl installed via pip."
    stderr = (result.stderr or "").strip()[-500:]
    return (
        False,
        "Could not install openpyxl automatically:\n\n{}\n\n"
        "Install manually from the OSGeo4W Shell:\n\n    python -m pip install openpyxl\n\n"
        "Then restart QGIS.".format(stderr),
    )
