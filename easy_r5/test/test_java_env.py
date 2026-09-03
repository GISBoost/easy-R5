"""java_env helpers: heap heuristic, SHA-256, java -version parsing, jar sanity,
command building. Pure Python — run: py -m pytest easy_r5/test/test_java_env.py -v
"""

import hashlib
import os
import zipfile

from easy_r5.core import java_env
from easy_r5.core.java_env import (
    ResolvedEnv,
    build_java_command,
    check_java_version,
    heap_mb_for,
    jar_sanity_ok,
    sha256_file,
    verify_jar_sha256,
    xmx_arg,
)


# --- heap heuristic ------------------------------------------------------

def test_heap_caps_at_12gb():
    mb, warn = heap_mb_for(64 * 2 ** 30)
    assert mb == 12 * 1024 and warn is None


def test_heap_scales_to_60pct():
    mb, warn = heap_mb_for(8 * 2 ** 30)
    assert mb == 4915 and warn is None


def test_heap_floors_at_2gb():
    mb, warn = heap_mb_for(2 * 2 ** 30)
    assert mb == 2048 and warn is None


def test_heap_no_ram_falls_back_with_warning():
    mb, warn = heap_mb_for(None)
    assert mb == 4096 and warn is not None


def test_heap_override_wins():
    assert heap_mb_for(8 * 2 ** 30, override_gb=16) == (16384, None)


def test_xmx_arg():
    assert xmx_arg(4096) == "-Xmx4096m"


# --- sha256 ------------------------------------------------------------

def test_sha256_file(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello r5")
    assert sha256_file(f) == hashlib.sha256(b"hello r5").hexdigest()


def test_verify_jar_sha256_match(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    digest = hashlib.sha256(b"x").hexdigest()
    assert verify_jar_sha256(f, digest) == (True, digest)


def test_verify_jar_sha256_mismatch(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    ok, computed = verify_jar_sha256(f, "0" * 64)
    assert ok is False and computed == hashlib.sha256(b"x").hexdigest()


# --- java -version parsing -------------------------------------------

def _patch_java(monkeypatch, banner, exists=True):
    monkeypatch.setattr(java_env.Path, "exists", lambda self: exists)

    class _Proc:
        stderr = banner
        stdout = ""

    monkeypatch.setattr(java_env.subprocess, "run", lambda *a, **k: _Proc())


def test_check_java_version_21(monkeypatch):
    _patch_java(monkeypatch, 'openjdk version "21.0.5" 2024-10-15 LTS')
    ok, ver, err = check_java_version("/x/bin/java")
    assert ok is True and ver == "21.0.5" and err == ""


def test_check_java_version_8_rejected(monkeypatch):
    _patch_java(monkeypatch, 'java version "1.8.0_402"')
    ok, ver, err = check_java_version("/x/bin/java")
    assert ok is False and ver == "1.8.0_402" and "21" in err


def test_check_java_version_17_rejected(monkeypatch):
    _patch_java(monkeypatch, 'openjdk version "17.0.9" 2023-10-17')
    ok, ver, err = check_java_version("/x/bin/java")
    assert ok is False and ver == "17.0.9"


def test_check_java_version_missing_file(monkeypatch):
    _patch_java(monkeypatch, "", exists=False)
    ok, ver, err = check_java_version("/x/bin/java")
    assert ok is False and ver == "" and err


# --- jar sanity -----------------------------------------------------

def _make_jar(path, entries, size_bytes):
    with zipfile.ZipFile(path, "w") as zf:
        for name in entries:
            zf.writestr(name, b"x")
    with open(path, "ab") as fh:
        fh.write(b"\0" * max(0, size_bytes - os.path.getsize(path)))


def test_jar_sanity_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(java_env.pins, "R5_JAR_MIN_BYTES", 10)
    monkeypatch.setattr(java_env.pins, "R5_JAR_MAX_BYTES", 10_000)
    jar = tmp_path / "r5.jar"
    _make_jar(jar, ["com/conveyal/r5/Foo.class", "META-INF/MANIFEST.MF"], 200)
    assert jar_sanity_ok(jar) is True


def test_jar_sanity_wrong_contents(monkeypatch, tmp_path):
    monkeypatch.setattr(java_env.pins, "R5_JAR_MIN_BYTES", 10)
    monkeypatch.setattr(java_env.pins, "R5_JAR_MAX_BYTES", 10_000)
    jar = tmp_path / "x.jar"
    _make_jar(jar, ["org/other/Thing.class"], 200)
    assert jar_sanity_ok(jar) is False


def test_jar_sanity_not_a_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(java_env.pins, "R5_JAR_MIN_BYTES", 10)
    monkeypatch.setattr(java_env.pins, "R5_JAR_MAX_BYTES", 10_000)
    f = tmp_path / "x.jar"
    f.write_bytes(b"not a zip file at all" * 20)
    assert jar_sanity_ok(f) is False


# --- command building ----------------------------------------------

def _env(mode):
    from pathlib import Path

    return ResolvedEnv(
        jdk_path=Path("/jdk/bin/java"),
        jar_path=Path("/e/r5.jar"),
        runner_mode=mode,
        runner_class_dir=Path("/e/rc"),
        runner_source_path=Path("/p/EasyR5Runner.java"),
    )


def test_build_command_compiled():
    cmd = build_java_command(_env("compiled"), "-Xmx4096m", "/tmp/job.json")
    assert cmd[0] == str(java_env.Path("/jdk/bin/java"))
    assert cmd[1] == "-Xmx4096m"
    assert cmd[3].count(os.pathsep) == 1
    assert cmd[4] == "EasyR5Runner"


def test_build_command_source():
    cmd = build_java_command(_env("source"), "-Xmx4096m", "/tmp/job.json")
    assert cmd[3] == str(java_env.Path("/e/r5.jar"))
    assert cmd[4].endswith(".java")
