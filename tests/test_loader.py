import zipfile

import pytest
from factory import invoice_xml, p7m

from invoice_extract import loader
from invoice_extract.loader import collect_files, iter_documents


def test_folder_is_read_recursively_and_junk_skipped(tmp_path):
    (tmp_path / "2026" / "03").mkdir(parents=True)
    (tmp_path / "2026" / "03" / "a.xml").write_bytes(invoice_xml())
    (tmp_path / "b.xml.p7m").write_bytes(p7m(invoice_xml()))
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / ".hidden.xml").write_text("x")
    names = sorted(d.name for d in iter_documents([tmp_path]))
    assert names == ["a.xml", "b.xml.p7m"]


def test_zip_members_are_read_without_unpacking(tmp_path):
    archive = tmp_path / "marzo.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("fatture/a.xml", invoice_xml())
        z.writestr("fatture/b.xml.p7m", p7m(invoice_xml()))
        z.writestr("leggimi.pdf", b"%PDF")
    docs = list(iter_documents([archive]))
    assert [d.name for d in docs] == ["marzo.zip/fatture/a.xml", "marzo.zip/fatture/b.xml.p7m"]
    assert docs[1].signed and not docs[0].signed


def test_damaged_zip_becomes_an_error_document(tmp_path):
    bad = tmp_path / "x.zip"
    bad.write_bytes(b"not a zip")
    [doc] = iter_documents([bad])
    assert doc.error


def test_too_big_file_is_not_read(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 10)
    (tmp_path / "a.xml").write_bytes(invoice_xml())
    [doc] = iter_documents([tmp_path / "a.xml"])
    assert doc.error == "file too big" and doc.data == b""


def test_missing_path():
    with pytest.raises(FileNotFoundError):
        collect_files([__import__("pathlib").Path("/no/such/folder")])


def test_same_file_twice_is_read_once(tmp_path):
    (tmp_path / "a.xml").write_bytes(invoice_xml())
    assert len(collect_files([tmp_path, tmp_path / "a.xml"])) == 1
