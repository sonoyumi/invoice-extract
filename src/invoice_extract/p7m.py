"""Extract the invoice XML from a signed .p7m file (CAdES / CMS SignedData).

Invoices that went through the SdI are often signed: the XML sits inside a binary
ASN.1 envelope. We do not verify the signature (that is the SdI's job), we only take
the content out. A tiny BER/DER reader is enough for that and needs no extra libraries.

Structure we walk:
    ContentInfo ::= SEQUENCE { contentType OID, [0] EXPLICIT SignedData }
    SignedData  ::= SEQUENCE { version, digestAlgorithms SET, encapContentInfo, ... }
    encapContentInfo ::= SEQUENCE { eContentType OID, [0] EXPLICIT OCTET STRING }
The OCTET STRING may be "constructed": the XML split into chunks that must be joined.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass


class P7mError(ValueError):
    pass


@dataclass
class _Node:
    tag: int
    constructed: bool
    value: bytes  # raw content (primitive)
    children: list[_Node]


def _read_length(data: bytes, pos: int) -> tuple[int | None, int]:
    """Returns (length, new position); None length means indefinite (BER)."""
    if pos >= len(data):
        raise P7mError("truncated length")
    first = data[pos]
    pos += 1
    if first < 0x80:
        return first, pos
    if first == 0x80:
        return None, pos
    count = first & 0x7F
    if count > 4 or pos + count > len(data):
        raise P7mError("bad length")
    return int.from_bytes(data[pos : pos + count], "big"), pos + count


def _parse(data: bytes, pos: int, end: int, depth: int = 0) -> tuple[list[_Node], int]:
    """Parses TLV items in data[pos:end]; stops at end-of-contents (00 00) for indefinite forms."""
    if depth > 32:
        raise P7mError("nesting too deep")
    nodes: list[_Node] = []
    while pos < end:
        if data[pos] == 0 and pos + 1 < end and data[pos + 1] == 0:  # end-of-contents
            return nodes, pos + 2
        tag = data[pos]
        if tag & 0x1F == 0x1F:
            raise P7mError("multi-byte tags are not used in CMS")
        constructed = bool(tag & 0x20)
        length, pos = _read_length(data, pos + 1)
        if length is None:
            if not constructed:
                raise P7mError("indefinite length on a primitive value")
            children, pos = _parse(data, pos, end, depth + 1)
            nodes.append(_Node(tag, True, b"", children))
            continue
        if pos + length > end:
            raise P7mError("value longer than the file")
        content = data[pos : pos + length]
        children = _parse(content, 0, length, depth + 1)[0] if constructed else []
        nodes.append(_Node(tag, constructed, content, children))
        pos += length
    return nodes, pos


def _octets(node: _Node) -> bytes:
    """OCTET STRING content, joining chunks of a constructed one."""
    if not node.constructed:
        return node.value
    return b"".join(_octets(child) for child in node.children)


def _child(node: _Node, index: int, what: str) -> _Node:
    if index >= len(node.children):
        raise P7mError(f"missing {what}")
    return node.children[index]


def extract_xml(data: bytes) -> bytes:
    """Returns the XML carried by a .p7m file (binary DER/BER or base64 text)."""
    if data[:1] != b"\x30":  # not a SEQUENCE: maybe the base64 variant
        try:
            data = base64.b64decode(b"".join(data.split()), validate=True)
        except (binascii.Error, ValueError):
            raise P7mError("not a p7m file (neither binary nor base64)") from None
        if data[:1] != b"\x30":
            raise P7mError("not a p7m file")

    nodes, _ = _parse(data, 0, len(data))
    if not nodes:
        raise P7mError("empty file")
    content_info = nodes[0]
    signed_data = _child(_child(content_info, 1, "SignedData wrapper"), 0, "SignedData")
    encap = _child(signed_data, 2, "encapContentInfo")
    econtent = _child(_child(encap, 1, "signed content (detached signature?)"), 0, "eContent")
    xml = _octets(econtent)
    if not xml.lstrip().startswith(b"<"):
        raise P7mError("signed content is not XML")
    return xml
