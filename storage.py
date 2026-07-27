"""Small, dependency-free helpers for durable local JSON snapshots."""

import json
import os
import tempfile


def _atomic_write(path, writer, suffix):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", suffix=suffix, dir=directory)
    os.fchmod(fd, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            writer(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_json_dump(path, value, *, indent=1, sort_keys=False):
    """Write JSON beside its destination, then atomically replace the old file."""
    def write(f):
        json.dump(value, f, indent=indent, sort_keys=sort_keys)
        f.write("\n")

    _atomic_write(path, write, ".json")


def atomic_text_dump(path, value):
    """Atomically replace a UTF-8 text file."""
    _atomic_write(path, lambda f: f.write(value), ".txt")


def atomic_binary_dump(path, value):
    """Atomically replace a binary file."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", suffix=".bin", dir=directory)
    os.fchmod(fd, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
