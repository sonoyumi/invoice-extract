from datetime import date

import pytest
from factory import Body, L, invoice_xml

from invoice_extract.checks import check_invoice, codice_fiscale_ok, partita_iva_ok, split_duplicates
from invoice_extract.parser import parse_invoices

TODAY = date(2026, 9, 29)


def one(body: Body | None = None, **kw):
    return parse_invoices(invoice_xml(body or Body(), **kw), "a.xml")[0]


def codes(inv):
    return {(i.level, i.code) for i in check_invoice(inv, TODAY)}


@pytest.mark.parametrize(
    ("code", "ok"), [("01234567897", True), ("01234567890", False), ("0123456789", False), ("0123456789A", False)]
)
def test_partita_iva(code, ok):
    assert partita_iva_ok(code) is ok


@pytest.mark.parametrize(
    ("code", "ok"),
    [
        ("RSSMRA85T10A562S", True),
        ("rssmra85t10a562s", True),
        ("RSSMRA85T10A562X", False),
        ("01234567897", True),
        ("SHORT", False),
    ],
)
def test_codice_fiscale(code, ok):
    assert codice_fiscale_ok(code) is ok


def test_clean_invoice_has_no_issues():
    body = Body(
        lines=[
            L("Pane", "10", "2.00", "4.00"),
            L("Caffè", "3", "10.00", "10.00"),
            L("Bollo", "1", "2.00", "0.00", "N1"),
        ]
    )
    assert check_invoice(one(body), TODAY) == []


def test_wrong_vat_check_digit():
    assert ("error", "bad_vat") in codes(one(supplier_vat="01234567890"))


def test_foreign_vat_is_not_checked_with_italian_rules():
    inv = one()
    inv.supplier = inv.supplier.__class__(inv.supplier.name, "DE", "123456789", "")
    assert ("error", "bad_vat") not in codes(inv)


def test_private_customer_with_bad_tax_code():
    assert ("warning", "bad_tax_code") in codes(one(customer_vat="", customer_cf="RSSMRA85T10A562X"))


def test_zero_rate_needs_nature():
    assert ("error", "nature_missing") in codes(one(Body(lines=[L("Esente", "1", "10.00", "0.00")])))


def test_small_rounding_difference_is_a_warning_big_one_an_error():
    assert ("warning", "taxable_mismatch") in codes(one(Body(summary_override={"22.00": "100.50"})))
    assert ("error", "taxable_mismatch") in codes(one(Body(summary_override={"22.00": "150.00"})))


def test_wrong_vat_amount():
    assert ("error", "tax_mismatch") in codes(one(Body(tax_override={"22.00": "20.00"})))


def test_total_mismatch_but_stamp_duty_is_accepted():
    assert ("warning", "total_mismatch") in codes(one(Body(total="130.00")))
    assert codes(one(Body(total="124.00", stamp="2.00", payments=[]))) == set()


def test_payments_must_match_net_amount():
    assert codes(one(Body(withholding="20.00"))) == set()  # 122 - 20 paid in one installment
    assert ("warning", "payment_mismatch") in codes(one(Body(payments=[("2026-04-30", "100.00")])))


def test_future_date_and_foreign_currency():
    found = codes(one(Body(date="2099-01-01", currency="USD")))
    assert {("warning", "future_date"), ("warning", "currency")} <= found


def test_duplicates_keep_first_copy():
    a = parse_invoices(invoice_xml(Body(number="7")), "a.xml")[0]
    b = parse_invoices(invoice_xml(Body(number="7")), "copy of a.xml")[0]
    c = parse_invoices(invoice_xml(Body(number="8")), "c.xml")[0]
    unique, issues = split_duplicates([a, b, c])
    assert unique == [a, c]
    assert [(i.source, i.code) for i in issues] == [("copy of a.xml", "duplicate")]
