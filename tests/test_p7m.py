import base64

import pytest
from factory import invoice_xml, p7m, tlv

from invoice_extract.p7m import P7mError, extract_xml

XML = invoice_xml()


def test_plain_der_envelope():
    assert extract_xml(p7m(XML)) == XML


def test_chunked_ber_envelope_is_joined():
    # Some signing tools split the content into pieces with indefinite lengths.
    assert extract_xml(p7m(XML, chunked=True)) == XML


def test_base64_variant():
    encoded = base64.encodebytes(p7m(XML))  # with line breaks, as some portals send it
    assert extract_xml(encoded) == XML


def test_garbage_is_rejected():
    with pytest.raises(P7mError):
        extract_xml(b"hello, this is not a signed file")


def test_truncated_file_is_rejected():
    with pytest.raises(P7mError):
        extract_xml(p7m(XML)[:50])


def test_detached_signature_has_no_content():
    detached = tlv(
        0x30,
        tlv(0x06, b"\x2a") + tlv(0xA0, tlv(0x30, tlv(0x02, b"\x01") + tlv(0x31, b"") + tlv(0x30, tlv(0x06, b"\x2a")))),
    )
    with pytest.raises(P7mError, match="missing"):
        extract_xml(detached)


def test_signed_content_must_be_xml():
    with pytest.raises(P7mError, match="not XML"):
        extract_xml(p7m(b"%PDF-1.7 a signed pdf"))
