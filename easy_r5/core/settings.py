"""QSettings access for Easy-R5.

Every key lives under the ``easy_r5/`` prefix. Easy-OTP's keys are never read
or written here — a user may have both plugins installed, one on Java 8 and one
on Java 21 (ADR-0002).

This is the only ``core`` module that imports Qt. Tests do not import it.
"""

from __future__ import annotations

from qgis.PyQt.QtCore import QSettings

_PREFIX = "easy_r5/"

# short name -> full QSettings key
_KEY = {
    "jdk_path": _PREFIX + "jdk_path",
    "jdk_version": _PREFIX + "jdk_version",
    "r5_jar_path": _PREFIX + "r5_jar_path",
    "r5_version": _PREFIX + "r5_version",
    "r5_jar_sha256": _PREFIX + "r5_jar_sha256",
    "runner_class_dir": _PREFIX + "runner_class_dir",
    "runner_mode": _PREFIX + "runner_mode",
    "runner_source_path": _PREFIX + "runner_source_path",
    "target_folder": _PREFIX + "target_folder",
    "cache_folder": _PREFIX + "cache_folder",
    "java_heap_gb": _PREFIX + "java_heap_gb",
}


def get(name, default=""):
    return QSettings().value(_KEY[name], default)


def set_(name, value):
    QSettings().setValue(_KEY[name], value)


def get_java_heap_gb():
    """Return the user's -Xmx override in GB as an int, or None if unset."""
    raw = QSettings().value(_KEY["java_heap_gb"], "")
    try:
        val = int(raw)
        return val if val > 0 else None
    except (TypeError, ValueError):
        return None


def all_settings():
    """Snapshot every Easy-R5 key as a plain dict (for java_env / diagnostics)."""
    s = QSettings()
    return {name: s.value(key, "") for name, key in _KEY.items()}


def clear_all():
    s = QSettings()
    for key in _KEY.values():
        s.remove(key)
