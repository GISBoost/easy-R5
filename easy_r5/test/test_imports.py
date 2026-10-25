"""Every relative ``from .x import name`` in the plugin resolves — including the
lazy ones inside ``processAlgorithm``, which nothing imports until a user runs
the algorithm (PreparePopulationLayer shipped importing a removed helper).
Static (AST only), so no QGIS is needed.
run: py -m pytest easy_r5/test/test_imports.py -v"""

import ast
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parent.parent
_SOURCES = [p for p in _PKG_ROOT.rglob("*.py")
            if not {"test", "_vendor"} & set(p.relative_to(_PKG_ROOT).parts)]


def _top_level_names(path: Path) -> set:
    names = set()
    stack = list(ast.parse(path.read_text(encoding="utf-8")).body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.If, ast.Try)):
            for field in ("body", "orelse", "finalbody", "handlers"):
                stack.extend(getattr(node, field, []))
        elif isinstance(node, ast.ExceptHandler):
            stack.extend(node.body)
    return names


def _relative_imports():
    for path in _SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                target = base.joinpath(*node.module.split(".")) if node.module else base
                for alias in node.names:
                    yield pytest.param(target, alias.name,
                                       id="{}:{}".format(path.name, alias.name))


@pytest.mark.parametrize("target,name", list(_relative_imports()))
def test_relative_import_resolves(target, name):
    if target.is_dir():
        if (target / "{}.py".format(name)).is_file() or (target / name).is_dir():
            return  # `from . import submodule`
        target = target / "__init__.py"
    else:
        target = target.with_suffix(".py")
    assert target.is_file(), "module {} does not exist".format(target)
    assert name in _top_level_names(target), "{} has no {!r}".format(target.name, name)
