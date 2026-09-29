"""Validation: check digits, VAT arithmetic, totals, duplicates.

Levels:
- error   — the SdI would reject it or the numbers cannot be trusted;
- warning — worth a human look (rounding, unknown type, date in the future, ...).
The SdI tolerates up to 1 euro of rounding difference in the VAT summary; above a cent
we warn, above a euro we call it an error.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from decimal import Decimal

from invoice_extract.models import DOC_TYPES, ZERO, Invoice, Issue, Party

CENT = Decimal("0.01")
EURO = Decimal("1.00")

_CF_ODD = dict(
    zip(
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [
            1,
            0,
            5,
            7,
            9,
            13,
            15,
            17,
            19,
            21,
            1,
            0,
            5,
            7,
            9,
            13,
            15,
            17,
            19,
            21,
            2,
            4,
            18,
            20,
            11,
            3,
            6,
            8,
            12,
            14,
            16,
            10,
            22,
            25,
            24,
            23,
        ],
        strict=True,
    )
)
_CF_RE = re.compile(r"^[A-Z0-9]{16}$")


def partita_iva_ok(code: str) -> bool:
    """Italian VAT number: 11 digits, the last one is a Luhn-style check digit."""
    if len(code) != 11 or not code.isdigit():
        return False
    total = 0
    for i, ch in enumerate(code[:10]):
        n = int(ch)
        if i % 2:  # 2nd, 4th, ... digit is doubled
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10 == int(code[10])


def codice_fiscale_ok(code: str) -> bool:
    """Tax code: 16 characters for persons (check letter), or 11 digits for companies."""
    code = code.upper()
    if len(code) == 11:
        return partita_iva_ok(code)
    if not _CF_RE.match(code):
        return False
    total = 0
    for i, ch in enumerate(code[:15]):
        if i % 2 == 0:  # positions 1, 3, 5 ... (1-based) use the "odd" table
            total += _CF_ODD[ch]
        else:
            total += int(ch) if ch.isdigit() else ord(ch) - ord("A")
    return chr(ord("A") + total % 26) == code[15]


def _check_party(inv: Invoice, party: Party, who: str, issues: list[Issue]) -> None:
    if party.vat and party.country == "IT" and not partita_iva_ok(party.vat):
        issues.append(Issue.make(inv.source, "error", "bad_vat", who=who, value=party.vat))
    if party.tax_code and not codice_fiscale_ok(party.tax_code):
        issues.append(Issue.make(inv.source, "warning", "bad_tax_code", who=who, value=party.tax_code))


def _group_key(rate: Decimal, nature: str) -> tuple[Decimal, str]:
    return (rate.normalize() if rate else ZERO, nature)


def _rate_label(rate: Decimal, nature: str) -> str:
    return f"{rate.normalize():f}%" + (f" {nature}" if nature else "")


def check_invoice(inv: Invoice, today: date) -> list[Issue]:
    issues: list[Issue] = []
    src = inv.source

    if not inv.supplier.vat:
        issues.append(Issue.make(src, "error", "supplier_no_vat"))
    _check_party(inv, inv.supplier, "supplier", issues)
    _check_party(inv, inv.customer, "customer", issues)

    if inv.doc_type not in DOC_TYPES:
        issues.append(Issue.make(src, "warning", "unknown_type", value=inv.doc_type))
    if inv.currency != "EUR":
        issues.append(Issue.make(src, "warning", "currency", value=inv.currency))
    if inv.date > today:
        issues.append(Issue.make(src, "warning", "future_date", value=inv.date.isoformat()))
    if not inv.lines:
        issues.append(Issue.make(src, "error", "no_lines"))
    if not inv.vat:
        issues.append(Issue.make(src, "error", "no_vat_summary"))

    lines_by_rate: dict[tuple[Decimal, str], Decimal] = defaultdict(lambda: ZERO)
    for line in inv.lines:
        if line.vat_rate == 0 and not line.nature:
            issues.append(Issue.make(src, "error", "nature_missing", line=line.number))
        lines_by_rate[_group_key(line.vat_rate, line.nature)] += line.total

    summary_keys = set()
    for s in inv.vat:
        key = _group_key(s.vat_rate, s.nature)
        summary_keys.add(key)
        label = _rate_label(s.vat_rate, s.nature)
        if s.vat_rate == 0 and not s.nature:
            issues.append(Issue.make(src, "error", "nature_missing_summary", rate=label))

        diff = abs(lines_by_rate.get(key, ZERO) + s.rounding - s.taxable)
        if diff > CENT:
            level = "error" if diff > EURO else "warning"
            issues.append(Issue.make(src, level, "taxable_mismatch", rate=label, diff=f"{diff:.2f}"))

        expected_tax = (s.taxable * s.vat_rate / 100).quantize(CENT)
        diff = abs(expected_tax - s.tax)
        if diff > CENT:
            level = "error" if diff > EURO else "warning"
            issues.append(
                Issue.make(src, level, "tax_mismatch", rate=label, expected=f"{expected_tax:.2f}", found=f"{s.tax:.2f}")
            )

    for key in lines_by_rate.keys() - summary_keys:
        issues.append(Issue.make(src, "error", "summary_missing", rate=_rate_label(*key)))

    if inv.total is not None and inv.vat:
        diff = abs(inv.total - (inv.taxable + inv.tax))
        # A virtual stamp duty may be added to the total: that is fine.
        if diff > CENT and abs(diff - inv.stamp) > CENT:
            issues.append(
                Issue.make(
                    src, "warning", "total_mismatch", total=f"{inv.total:.2f}", computed=f"{inv.taxable + inv.tax:.2f}"
                )
            )

    amounts = [p.amount for p in inv.payments if p.amount is not None]
    if amounts:
        paid = sum(amounts, ZERO)
        if abs(paid - inv.to_pay) > CENT:
            issues.append(Issue.make(src, "warning", "payment_mismatch", paid=f"{paid:.2f}", due=f"{inv.to_pay:.2f}"))
    return issues


def split_duplicates(invoices: list[Invoice]) -> tuple[list[Invoice], list[Issue]]:
    """Keeps the first copy of each invoice; later copies become warnings and leave the totals."""
    seen: dict[tuple, Invoice] = {}
    unique: list[Invoice] = []
    issues: list[Issue] = []
    for inv in invoices:
        first = seen.get(inv.key)
        if first is None:
            seen[inv.key] = inv
            unique.append(inv)
        else:
            issues.append(Issue.make(inv.source, "warning", "duplicate", number=inv.number, first=first.source))
    return unique, issues
