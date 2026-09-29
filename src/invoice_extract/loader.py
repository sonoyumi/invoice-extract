"""Finding invoice files: single files, folders (recursively) and .zip archives.

Accountants usually get invoices as a zip from the Cassetto fiscale or from the
bookkeeping software, so archives are read directly, without unpacking to disk.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

INVOICE_SUFFIXES = (".xml", ".p7m")
# Real invoices are a few KB; anything this big is not an invoice (or is a zip bomb).
MAX_FILE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class Document:
    name: str  # shown in the report: "file.xml" or "archive.zip/file.xml"
    data: bytes = b""
    error: str = ""

    @property
    def signed(self) -> bool:
        return self.name.lower().endswith(".p7m")


def _is_invoice_name(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return not base.startswith((".", "~$")) and base.lower().endswith(INVOICE_SUFFIXES)


def collect_files(paths: Iterable[Path]) -> list[Path]:
    """Expands folders; raises FileNotFoundError for a missing path."""
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            files.extend(
                sorted(
                    p
                    for p in path.rglob("*")
                    if p.is_file() and (_is_invoice_name(p.name) or p.suffix.lower() == ".zip")
                )
            )
        else:
            files.append(path)
    unique: dict[Path, None] = dict.fromkeys(p.resolve() for p in files)
    return list(unique)


def _from_zip(path: Path) -> Iterator[Document]:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        yield Document(path.name, error="damaged zip archive")
        return
    with archive:
        for info in sorted(archive.infolist(), key=lambda i: i.filename):
            if info.is_dir() or not _is_invoice_name(info.filename):
                continue
            name = f"{path.name}/{info.filename}"
            if info.file_size > MAX_FILE_BYTES:
                yield Document(name, error="file too big")
                continue
            yield Document(name, archive.read(info))


def iter_documents(paths: Iterable[Path]) -> Iterator[Document]:
    for path in collect_files(paths):
        if path.suffix.lower() == ".zip":
            yield from _from_zip(path)
        elif path.stat().st_size > MAX_FILE_BYTES:
            yield Document(path.name, error="file too big")
        else:
            yield Document(path.name, path.read_bytes())
