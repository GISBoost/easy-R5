"""Build the QGIS-plugin-repository ZIP: `py tools/build_plugin_zip.py`.

Writes `builds/easy_r5-<version>.zip` with the layout plugins.qgis.org wants —
a single top-level `easy_r5/` folder, no test code, no caches, no build junk.
Version is read from `easy_r5/metadata.txt`.
"""

from __future__ import annotations

import configparser
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "easy_r5"
OUT_DIR = ROOT / "builds"

# Anything matching these is kept out of the ZIP.
EXCLUDE_DIRS = {"test", "__pycache__", "_vendor", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".pyd"}


def _version() -> str:
    cp = configparser.ConfigParser()
    cp.read(SRC / "metadata.txt", encoding="utf-8")
    return cp["general"]["version"]


def _wanted(path: pathlib.Path) -> bool:
    rel = path.relative_to(SRC)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    return path.suffix not in EXCLUDE_SUFFIXES


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"easy_r5-{_version()}.zip"
    files = sorted(p for p in SRC.rglob("*") if p.is_file() and _wanted(p))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, pathlib.Path("easy_r5") / f.relative_to(SRC))
    size_kb = out.stat().st_size / 1024
    print(f"{out.relative_to(ROOT)}  —  {len(files)} files, {size_kb:.0f} KB")
    assert size_kb < 20 * 1024, "ZIP exceeds the 20 MB plugin-repo limit"


if __name__ == "__main__":
    main()
