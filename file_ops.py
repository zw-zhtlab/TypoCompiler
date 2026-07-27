"""Bounded text-file IO with encoding fidelity and atomic persistence."""

from __future__ import annotations

import codecs
import locale
import os
import stat
import tempfile
from dataclasses import dataclass
from typing import Optional

MAX_FILE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class TextDocument:
    """Editable text plus the disk representation needed for a faithful save."""

    text: str
    encoding: str = "utf-8"
    newline: str = "\n"
    bom: bool = False


def _read_bounded(path: str, max_bytes: int) -> bytes:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    try:
        size = os.path.getsize(path)
    except OSError:
        size = None
    if size is not None and size > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes}-byte safety limit")
    with open(path, "rb") as source:
        raw = source.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes}-byte safety limit")
    return raw


def _decode(raw: bytes) -> tuple[str, str, bool]:
    if raw.startswith(codecs.BOM_UTF8):
        return raw[len(codecs.BOM_UTF8) :].decode("utf-8"), "utf-8", True
    if raw.startswith(codecs.BOM_UTF32_LE):
        return raw[len(codecs.BOM_UTF32_LE) :].decode("utf-32-le"), "utf-32-le", True
    if raw.startswith(codecs.BOM_UTF32_BE):
        return raw[len(codecs.BOM_UTF32_BE) :].decode("utf-32-be"), "utf-32-be", True
    if raw.startswith(codecs.BOM_UTF16_LE):
        return raw[len(codecs.BOM_UTF16_LE) :].decode("utf-16-le"), "utf-16-le", True
    if raw.startswith(codecs.BOM_UTF16_BE):
        return raw[len(codecs.BOM_UTF16_BE) :].decode("utf-16-be"), "utf-16-be", True

    encodings = ("utf-8", locale.getpreferredencoding(False), "gb18030")
    seen = set()
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in encodings:
        key = (encoding or "").casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            return raw.decode(encoding), encoding, False
        except UnicodeDecodeError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    return raw.decode("utf-8"), "utf-8", False


def _detect_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\n" in text:
        return "\n"
    if "\r" in text:
        return "\r"
    return "\n"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_document(path: str, max_bytes: int = MAX_FILE_BYTES) -> TextDocument:
    raw = _read_bounded(path, max_bytes)
    decoded, encoding, bom = _decode(raw)
    newline = _detect_newline(decoded)
    return TextDocument(
        text=_normalize_newlines(decoded),
        encoding=encoding,
        newline=newline,
        bom=bom,
    )


def read_text_utf8(path: str, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Compatibility wrapper that now strips BOMs and enforces a size limit."""
    return read_document(path, max_bytes=max_bytes).text


def _bom_for_encoding(encoding: str) -> bytes:
    normalized = encoding.lower().replace("_", "-")
    return {
        "utf-8": codecs.BOM_UTF8,
        "utf-16-le": codecs.BOM_UTF16_LE,
        "utf-16-be": codecs.BOM_UTF16_BE,
        "utf-32-le": codecs.BOM_UTF32_LE,
        "utf-32-be": codecs.BOM_UTF32_BE,
    }.get(normalized, b"")


def _fsync_directory(path: str) -> None:
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write(path: str, payload: bytes) -> None:
    target = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(target) or os.curdir
    os.makedirs(parent, exist_ok=True)
    existing_mode: Optional[int]
    try:
        existing_mode = stat.S_IMODE(os.stat(target).st_mode)
    except OSError:
        existing_mode = None

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(target)}.", suffix=".tmp", dir=parent
    )
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
        if existing_mode is not None:
            try:
                os.chmod(temporary_path, existing_mode)
            except OSError:
                pass
        os.replace(temporary_path, target)
        _fsync_directory(parent)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def write_document(
    path: str, text: str, metadata: Optional[TextDocument] = None
) -> TextDocument:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    encoding = metadata.encoding if metadata is not None else "utf-8"
    newline = metadata.newline if metadata is not None else "\n"
    bom = metadata.bom if metadata is not None else False
    if newline not in ("\n", "\r\n", "\r"):
        raise ValueError("Unsupported newline convention")

    normalized = _normalize_newlines(text)
    on_disk = normalized if newline == "\n" else normalized.replace("\n", newline)
    payload = on_disk.encode(encoding)
    if bom:
        marker = _bom_for_encoding(encoding)
        if not marker:
            raise ValueError(f"BOM preservation is unsupported for {encoding}")
        payload = marker + payload
    _atomic_write(path, payload)
    return TextDocument(text=normalized, encoding=encoding, newline=newline, bom=bom)


def write_text_utf8(path: str, text: str) -> None:
    """Compatibility wrapper for an atomic UTF-8 save without a BOM."""
    write_document(path, text)
