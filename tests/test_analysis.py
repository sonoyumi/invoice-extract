from decimal import Decimal

from factory import CUSTOMER_VAT, Body, L, invoice_xml

from invoice_extract.analysis import IN, OUT, deadlines, direction, normalize_vat, party_totals, vat_totals
from invoice_extract.parser import parse_invoices

OTHER_VAT = "03456789019"


def inv(body=None, **kw):
    return parse_invoices(invoice_xml(body or Body(), **kw), "a.xml")[0]


def test_normalize_vat():
    assert normalize_vat(" it 0123 4567 897 ") == "01234567897"
    assert normalize_vat("01234567897") == "01234567897"


def test_direction():
    issued = inv(supplier_vat=CUSTOMER_VAT, customer_vat=OTHER_VAT)
    received = inv()
    assert direction(issued, CUSTOMER_VAT) == OUT
    assert direction(received, CUSTOMER_VAT) == IN
    assert direction(received, "") == ""


def test_credit_note_is_negative_in_vat_totals():
    invoice = inv(Body(lines=[L("A", "1", "100.00")]))
    credit = inv(Body(doc_type="TD04", number="NC1", lines=[L("Reso", "1", "40.00")]))
    [row] = vat_totals([invoice, credit])
    assert row.taxable == Decimal("60.00") and row.tax == Decimal("13.20") and row.invoices == 2


def test_party_totals_sorted_by_amount():
    small = inv(Body(lines=[L("A", "1", "10.00")]))
    big = inv(Body(lines=[L("A", "1", "500.00")]), supplier="Ortofrutta Srl", supplier_vat=OTHER_VAT)
    rows = party_totals([small, big])
    assert [r.name for r in rows] == ["Ortofrutta Srl", "Tipografia Alpina Srl"]
    assert rows[0].fiscal_id == f"IT{OTHER_VAT}"


def test_deadlines_only_for_received_invoices():
    received = inv(Body(payments=[("2026-05-31", "61.00"), ("2026-04-30", "61.00")]))
    issued = inv(supplier_vat=CUSTOMER_VAT, customer_vat=OTHER_VAT)
    rows = deadlines([received, issued], CUSTOMER_VAT)
    assert [str(r.due) for r in rows] == ["2026-04-30", "2026-05-31"]
    assert all(r.party == "Tipografia Alpina Srl" for r in rows)
    assert len(deadlines([received, issued])) == 3  # without my VAT: everything
