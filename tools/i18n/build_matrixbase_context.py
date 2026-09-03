"""Maintain the MatrixBase i18n context by hand.

pylupdate5 only extracts translation calls it recognises (tr, translate with
literal args). ``easy_r5/algorithms/_matrix_base.py`` routes its shared strings
through a module-level ``_tr(s)`` helper so they resolve under one stable
context ("MatrixBase") at runtime — but pylupdate can't see them.

This script scans ``_matrix_base.py`` for ``_tr("...")`` literals and merges a
``<context><name>MatrixBase</name>...`` block into ``easy_r5/i18n/easy_r5_pl.ts``,
preserving any translations already there. Run it after ``pylupdate5`` whenever
the shared strings change, then re-run ``lrelease``.

    py tools/i18n/build_matrixbase_context.py
"""
import ast
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "easy_r5" / "algorithms" / "_matrix_base.py"
TS = ROOT / "easy_r5" / "i18n" / "easy_r5_pl.ts"


def extract_tr_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_tr" and node.args):
            arg = node.args[0]
            try:
                val = ast.literal_eval(arg)
            except ValueError:
                continue
            if isinstance(val, str):
                out.append(val)
    seen: dict[str, None] = {}
    for s in out:
        seen.setdefault(s, None)
    return list(seen)


def existing_translations(ts_text: str) -> dict[str, str]:
    block = re.search(
        r"<context>\s*<name>MatrixBase</name>(.*?)</context>", ts_text, re.S)
    if not block:
        return {}
    pairs = re.findall(
        r"<source>((?:(?!</source>).)*)</source>\s*<translation[^>]*>(.*?)</translation>",
        block.group(1), re.S)
    return {html.unescape(s): html.unescape(t) for s, t in pairs}


def build_context(strings: list[str], known: dict[str, str]) -> str:
    lines = ["<context>", "    <name>MatrixBase</name>"]
    for s in strings:
        esc = html.escape(s, quote=False)
        tr = known.get(s, "")
        if tr:
            trans = "<translation>{}</translation>".format(html.escape(tr, quote=False))
        else:
            trans = '<translation type="unfinished"></translation>'
        lines += ["    <message>",
                  "        <source>{}</source>".format(esc),
                  "        {}".format(trans),
                  "    </message>"]
    lines.append("</context>")
    return "\n".join(lines)


def main() -> None:
    strings = extract_tr_literals(SRC)
    ts_text = TS.read_text(encoding="utf-8")
    known = existing_translations(ts_text)
    ctx = build_context(strings, known)

    if "<name>MatrixBase</name>" in ts_text:
        ts_text = re.sub(
            r"<context>\s*<name>MatrixBase</name>.*?</context>", ctx, ts_text, flags=re.S)
    else:
        ts_text = ts_text.replace("</TS>", ctx + "\n</TS>")
    TS.write_text(ts_text, encoding="utf-8")
    missing = sum(1 for s in strings if s not in known)
    print("MatrixBase: {} strings, {} still need translation".format(len(strings), missing))


if __name__ == "__main__":
    main()
