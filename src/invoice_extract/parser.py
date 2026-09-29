"""FatturaPA XML -> Invoice objects.

- Works with any namespace prefix (p:, ns2:, none): namespaces are stripped.
- One file may carry several invoices (a "lotto"): one Invoice per FatturaElettronicaBody.
- XML is parsed with defusedxml: files come from outside, entity tricks are refused.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml import DefusedXmlException
from defusedxml import ElementTree as SafeET

from invoice_extract.models import ZERO, Invoice, Line, Party, Payment, VatSummary


class InvoiceParseError(ValueError):
    pass


class NotAnInvoice(InvoiceParseError):
    """Valid XML, but something else: an SdI receipt, metadata file, etc."""


def _strip_namespaces(root: Element) -> None:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _text(node: Element | None, path: str = "") -> str:
    if node is None:
        return ""
    found = node.find(path) if path else node
    return (found.text or "").strip() if found is not None else ""


def _dec(node: Element | None, path: str) -> Decimal | None:
    raw = _text(node, path)
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise InvoiceParseError(f"{path}: not a number: {raw!r}") from None
    if not value.is_finite():
        raise InvoiceParseError(f"{path}: not a number: {raw!r}")
    return value


def _date(node: Element | None, path: str) -> date | None:
    raw = _text(node, path)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise InvoiceParseError(f"{path}: not a date: {raw!r}") from None


def _party(node: Element | None, role: str) -> Party:
    if node is None:
        raise InvoiceParseError(f"missing {role}")
    ana = node.find("DatiAnagrafici")
    name = _text(ana, "Anagrafica/Denominazione") or " ".join(
        part for part in (_text(ana, "Anagrafica/Nome"), _text(ana, "Anagrafica/Cognome")) if part
    )
    return Party(
        name=name,
        country=_text(ana, "IdFiscaleIVA/IdPaese").upper(),
        vat=_text(ana, "IdFiscaleIVA/IdCodice").upper(),
        tax_code=_text(ana, "CodiceFiscale").upper(),
    )


def _line(node: Element) -> Line:
    number = _text(node, "NumeroLinea")
    return Line(
        number=int(number) if number.isdigit() else 0,
        description=_text(node, "Descrizione"),
        quantity=_dec(node, "Quantita"),
        unit_price=_dec(node, "PrezzoUnitario") or ZERO,
        total=_dec(node, "PrezzoTotale") or ZERO,
        vat_rate=_dec(node, "AliquotaIVA") or ZERO,
        nature=_text(node, "Natura").upper(),
    )


def _summary(node: Element) -> VatSummary:
    return VatSummary(
        vat_rate=_dec(node, "AliquotaIVA") or ZERO,
        nature=_text(node, "Natura").upper(),
        taxable=_dec(node, "ImponibileImporto") or ZERO,
        tax=_dec(node, "Imposta") or ZERO,
        rounding=_dec(node, "Arrotondamento") or ZERO,
        chargeability=_text(node, "EsigibilitaIVA").upper(),
    )


def _payment(node: Element) -> Payment:
    return Payment(
        method=_text(node, "ModalitaPagamento"),
        due=_date(node, "DataScadenzaPagamento"),
        amount=_dec(node, "ImportoPagamento"),
        iban=_text(node, "IBAN").replace(" ", "").upper(),
    )


def _invoice(body: Element, source: str, supplier: Party, customer: Party) -> Invoice:
    doc = body.find("DatiGenerali/DatiGeneraliDocumento")
    if doc is None:
        raise InvoiceParseError("missing DatiGeneraliDocumento")
    doc_type, number, when = _text(doc, "TipoDocumento").upper(), _text(doc, "Numero"), _date(doc, "Data")
    if not doc_type or not number or when is None:
        raise InvoiceParseError("TipoDocumento, Numero and Data are required")

    return Invoice(
        source=source,
        doc_type=doc_type,
        currency=_text(doc, "Divisa").upper() or "EUR",
        number=number,
        date=when,
        supplier=supplier,
        customer=customer,
        total=_dec(doc, "ImportoTotaleDocumento"),
        lines=[_line(n) for n in body.findall("DatiBeniServizi/DettaglioLinee")],
        vat=[_summary(n) for n in body.findall("DatiBeniServizi/DatiRiepilogo")],
        payments=[_payment(n) for n in body.findall("DatiPagamento/DettaglioPagamento")],
        withholding=sum((_dec(n, "ImportoRitenuta") or ZERO for n in doc.findall("DatiRitenuta")), ZERO),
        stamp=_dec(doc, "DatiBollo/ImportoBollo") or ZERO,
        description=" ".join(_text(n) for n in doc.findall("Causale")),
    )


def parse_invoices(data: bytes, source: str) -> list[Invoice]:
    try:
        root = SafeET.fromstring(data)
    except SafeET.ParseError as exc:
        raise InvoiceParseError(f"not valid XML: {exc}") from None
    except DefusedXmlException:
        raise InvoiceParseError("XML contains forbidden constructs (entities/DTD)") from None

    _strip_namespaces(root)
    if root.tag != "FatturaElettronica":
        raise NotAnInvoice(f"root element is <{root.tag}>, not <FatturaElettronica>")

    header = root.find("FatturaElettronicaHeader")
    bodies = root.findall("FatturaElettronicaBody")
    if header is None or not bodies:
        raise InvoiceParseError("missing FatturaElettronicaHeader or FatturaElettronicaBody")

    supplier = _party(header.find("CedentePrestatore"), "CedentePrestatore")
    customer = _party(header.find("CessionarioCommittente"), "CessionarioCommittente")
    return [
        _invoice(body, source if len(bodies) == 1 else f"{source}#{i}", supplier, customer)
        for i, body in enumerate(bodies, 1)
    ]
