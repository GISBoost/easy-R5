"""openpyxl bootstrap. Pure Python (no pip, no qgis) —
run: py -m pytest easy_r5/test/test_dependencies.py -v"""

import zipfile

from easy_r5.core.dependencies import _safe_zipextract


def _make_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_safe_zipextract_writes_normal_members(tmp_path):
    src = _make_zip(tmp_path / "a.zip", {"pkg/__init__.py": "x = 1", "pkg/mod.py": "y = 2"})
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(src) as zf:
        _safe_zipextract(zf, str(dest))
    assert (dest / "pkg" / "__init__.py").read_text() == "x = 1"
    assert (dest / "pkg" / "mod.py").read_text() == "y = 2"


def test_safe_zipextract_skips_parent_traversal(tmp_path):
    src = _make_zip(tmp_path / "evil.zip", {"../escaped.py": "pwned", "ok.py": "fine"})
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(src) as zf:
        _safe_zipextract(zf, str(dest))
    assert not (tmp_path / "escaped.py").exists()   # never written outside dest
    assert (dest / "ok.py").read_text() == "fine"


def test_safe_zipextract_skips_absolute_path(tmp_path):
    src = _make_zip(tmp_path / "abs.zip", {"/tmp/abs_escaped.py": "pwned", "ok.py": "fine"})
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(src) as zf:
        _safe_zipextract(zf, str(dest))
    assert (dest / "ok.py").read_text() == "fine"
