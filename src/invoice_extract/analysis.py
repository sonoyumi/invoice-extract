"""Totals for the report: pure functions over parsed invoices (no files, easy to test)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invoice_extract.models import ZERO, Invoice, Party

OUT, IN = "out", "in"  # invoice issued by me / received by me


def normalize_vat(value: str) -> str:
    """'IT 012 345 678 97' -> '01234567897' (country prefix and spaces removed)."""
    cleaned = "".join(value.split()).upper()
    return cleaned[2:] if cleaned[:2].isalpha() else cleaned


def direction(inv: Invoice, my_vat: str) -> str:
    if not my_vat:
        return ""
    if inv.supplier.vat == my_vat:
        return OUT
    if my_vat in (inv.customer.vat, inv.customer.tax_code):
        return IN
    return ""


def counterparty(inv: Invoice, my_vat: str) -> Party:
    """Who the invoice is with: the customer for my issued invoices, the supplier otherwise."""
    return inv.customer if direction(inv, my_vat) == OUT else inv.supplier


@dataclass(frozen=True)
class VatRow:
    direction: str
    vat_rate: Decimal
    nature: str
    taxable: Decimal
    tax: Decimal
    invoices: int


def vat_totals(invoices: list[Invoice], my_vat: str = "") -> list[VatRow]:
    groups: dict[tuple[str, Decimal, str], list] = defaultdict(lambda: [ZERO, ZERO, set()])
    for inv in invoices:
        for s in inv.vat:
            g = groups[(direction(inv, my_vat), s.vat_rate.normalize(), s.nature)]
            g[0] += s.taxable * inv.sign
            g[1] += s.tax * inv.sign
            g[2].add(id(inv))
    rows = [VatRow(d, rate, nature, t, x, len(ids)) for (d, rate, nature), (t, x, ids) in groups.items()]
    return sorted(rows, key=lambda r: (r.direction, -r.vat_rate, r.nature))


@dataclass(frozen=True)
class PartyRow:
    name: str
    fiscal_id: str
    invoices: int
    taxable: Decimal
    tax: Decimal
    gross: Decimal


def party_totals(invoices: list[Invoice], my_vat: str = "") -> list[PartyRow]:
    groups: dict[str, list] = {}
    for inv in invoices:
        party = counterparty(inv, my_vat)
        g = groups.setdefault(party.key or party.name, [party, 0, ZERO, ZERO, ZERO])
        g[1] += 1
        g[2] += inv.taxable * inv.sign
        g[3] += inv.tax * inv.sign
        g[4] += inv.gross * inv.sign
    rows = [PartyRow(p.name, p.fiscal_id, n, t, x, g) for p, n, t, x, g in groups.values()]
    return sorted(rows, key=lambda r: (-r.gross, r.name))


@dataclass(frozen=True)
class DueRow:
    due: date | None
    party: str
    number: str
    amount: Decimal
    method: str
    iban: str
    source: str


def deadlines(invoices: list[Invoice], my_vat: str = "") -> list[DueRow]:
    """Payments to make: every installment of received invoices (all invoices if my VAT is unknown)."""
    rows = []
    for inv in invoices:
        if my_vat and direction(inv, my_vat) != IN:
            continue
        for p in inv.payments:
            amount = p.amount if p.amount is not None else inv.to_pay
            rows.append(
                DueRow(
                    p.due, counterparty(inv, my_vat).name, inv.number, amount * inv.sign, p.method, p.iban, inv.source
                )
            )
    return sorted(rows, key=lambda r: (r.due or date.max, r.party))
