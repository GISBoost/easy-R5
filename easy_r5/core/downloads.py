"""Shared HTTP download + safe archive extraction for the Setup algorithms.

Lifted out of ``algorithms/download_r5.py`` so ``DownloadRealizedGtfs`` can reuse
the exact same plumbing. No ``qgis`` import: the functions take any object with
``isCanceled() / setProgress() / pushInfo()`` (a ``QgsProcessingFeedback`` fits,
``None`` also works) and raise plain exceptions the calling algorithm maps to
``QgsProcessingException``. Strings here are English literals — the algorithm
wraps the user-facing ones in ``tr()`` where it re-raises, the same split
``core/matrix.py`` uses.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

_CHUNK = 64 * 1024


class DownloadError(RuntimeError):
    """A download or extraction failed for a reason worth showing the user."""


class DownloadCancelled(RuntimeError):
    """The feedback object reported ``isCanceled()`` mid-download."""


def check_writable(path: Path) -> None:
    """Raise ``DownloadError`` unless a probe file can be created next to ``path``."""
    path = Path(path)
    parent = path if path.is_dir() else path.parent
    if not parent.is_dir():
        raise DownloadError(
            "Folder '{}' does not exist and neither does its parent.".format(path)
        )
    probe = parent / ".easy_r5_write_test"
    try:
        probe.touch()
        probe.unlink()
    except PermissionError:
        raise DownloadError(
            "Cannot write to '{}': administrator rights required. Choose a folder "
            "in your user profile.".format(parent)
        )
    except OSError as exc:
        raise DownloadError("Cannot write to '{}': {}".format(parent, exc))


def check_free_space(path: Path, need_mb: int) -> None:
    """Raise ``DownloadError`` if ``path``'s filesystem has less than ``need_mb`` free."""
    free_mb = shutil.disk_usage(path).free / (1024 * 1024)
    if free_mb < need_mb:
        raise DownloadError(
            "Not enough disk space in '{}'. Need ~{} MB, have {:.0f} MB.".format(
                path, need_mb, free_mb
            )
        )


def _rm(path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def download_file(url: str, dest, *, feedback, user_agent: str, timeout: int = 60,
                  expected_bytes: "int | None" = None) -> None:
    """GET ``url`` into ``dest``, atomically (write ``<dest>.tmp``, then replace).

    Progress is reported as ``feedback.setProgress(0..100)``. If ``feedback``
    reports ``isCanceled()`` the partial file is removed and ``DownloadCancelled``
    is raised. A network error, an empty body, or a ``Content-Length`` that
    contradicts ``expected_bytes`` raises ``DownloadError``.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    req = urllib_request.Request(url, headers={"User-Agent": user_agent})
    done = 0
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:  # nosec B310 — caller passes a fixed https URL
            total = int(resp.headers.get("Content-Length") or 0)
            if expected_bytes and total and abs(total - expected_bytes) > 1024:
                raise DownloadError(
                    "Server reports {} bytes for {}, expected about {}.".format(
                        total, url, expected_bytes
                    )
                )
            with open(tmp, "wb") as fh:
                while True:
                    if feedback is not None and feedback.isCanceled():
                        fh.close()
                        _rm(tmp)
                        raise DownloadCancelled()
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if total and feedback is not None:
                        feedback.setProgress(min(99, int(done * 100 / total)))
    except URLError as exc:
        _rm(tmp)
        raise DownloadError("Download failed ({}): {}".format(url, exc)) from exc
    if done == 0:
        _rm(tmp)
        raise DownloadError("Server returned an empty file: {}".format(url))
    os.replace(tmp, dest)
    if feedback is not None:
        feedback.setProgress(100)


def safe_extract_zip(zip_path, dest_dir) -> "list[str]":
    """Extract ``zip_path`` into ``dest_dir``, skipping any zip-slip member.

    Returns the list of member names actually written.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()
    prefix = str(dest_root) + os.sep
    written = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest_root / member.filename).resolve()
            if str(target) != str(dest_root) and not str(target).startswith(prefix):
                continue  # skip zip-slip
            zf.extract(member, dest_dir)
            written.append(member.filename)
    return written


def safe_extract_tar(tar_path, dest_dir) -> None:
    """Extract ``tar_path`` into ``dest_dir`` — ``filter='data'`` on 3.12+, a
    hand-rolled tar-slip / device / link guard on older Pythons (QGIS 3.22 = 3.9)."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path) as tf:
        if hasattr(tarfile, "data_filter"):  # Python 3.12+
            tf.extractall(dest_dir, filter="data")
            return
        dest_root = dest_dir.resolve()
        prefix = str(dest_root) + os.sep
        for member in tf.getmembers():
            if member.isdev() or member.issym() or member.islnk():
                continue
            target = (dest_root / member.name).resolve()
            if str(target) != str(dest_root) and not str(target).startswith(prefix):
                continue  # skip tar-slip
            tf.extract(member, dest_dir)
