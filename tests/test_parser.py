from datetime import date
from decimal import Decimal

import pytest
from factory import CUSTOMER_VAT, SUPPLIER_VAT, Body, L, invoice_xml

from invoice_extract.parser import InvoiceParseError, NotAnInvoice, parse_invoices


def test_main_fields():
    body = Body(
        number="12/A",
        lines=[L("Volantini A5", "1000", "0.12"), L("Grafica", "1", "80.00")],
        withholding="16.00",
        causale="Stampa volantini",
    )
    [inv] = parse_invoices(invoice_xml(body), "a.xml")
    assert inv.number == "12/A" and inv.date == date(2026, 3, 10) and inv.doc_type == "TD01"
    assert inv.supplier.vat == SUPPLIER_VAT and inv.supplier.name == "Tipografia Alpina Srl"
    assert inv.customer.vat == CUSTOMER_VAT
    assert [line.total for line in inv.lines] == [Decimal("120.00"), Decimal("80.00")]
    assert inv.taxable == Decimal("200.00") and inv.tax == Decimal("44.00") and inv.gross == Decimal("244.00")
    assert inv.withholding == Decimal("16.00") and inv.to_pay == Decimal("228.00")
    assert inv.payments[0].due == date(2026, 4, 30) and inv.payments[0].iban.startswith("IT60")
    assert inv.description == "Stampa volantini"


@pytest.mark.parametrize("prefix", ["p", "ns2", ""])
def test_any_namespace_prefix(prefix):
    [inv] = parse_invoices(invoice_xml(prefix=prefix), "a.xml")
    assert inv.number == "1/A"


def test_batch_file_gives_one_invoice_per_body():
    invoices = parse_invoices(invoice_xml(Body(number="1"), Body(number="2")), "lotto.xml")
    assert [i.number for i in invoices] == ["1", "2"]
    assert [i.source for i in invoices] == ["lotto.xml#1", "lotto.xml#2"]


def test_missing_total_is_computed():
    [inv] = parse_invoices(invoice_xml(Body(total=None)), "a.xml")
    assert inv.total is None and inv.gross == Decimal("122.00")


def test_sdi_receipt_is_not_an_invoice():
    receipt = (
        b'<?xml version="1.0"?><ns3:RicevutaConsegna xmlns:ns3="x">'
        b"<IdentificativoSdI>1</IdentificativoSdI></ns3:RicevutaConsegna>"
    )
    with pytest.raises(NotAnInvoice):
        parse_invoices(receipt, "IT01234567897_00001_RC_001.xml")


def test_broken_xml():
    with pytest.raises(InvoiceParseError, match="not valid XML"):
        parse_invoices(b"<FatturaElettronica><oops>", "a.xml")


def test_entity_expansion_attack_is_refused():
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]><x>&b;</x>'
    with pytest.raises(InvoiceParseError, match="forbidden"):
        parse_invoices(bomb, "a.xml")


def test_bad_number_is_reported_with_the_field():
    xml = invoice_xml().replace(b"<PrezzoUnitario>50.00</PrezzoUnitario>", b"<PrezzoUnitario>50,00</PrezzoUnitario>")
    with pytest.raises(InvoiceParseError, match="PrezzoUnitario"):
        parse_invoices(xml, "a.xml")


def test_required_fields():
    xml = invoice_xml().replace(b"<Numero>1/A</Numero>", b"")
    with pytest.raises(InvoiceParseError, match="required"):
        parse_invoices(xml, "a.xml")
