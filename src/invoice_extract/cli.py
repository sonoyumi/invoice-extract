"""Command line: invoice-extract FILES_OR_FOLDERS [-o report.xlsx] [--csv DIR] [--my-vat ...]

Exit codes: 0 — report written; 1 — --strict and errors were found; 2 — wrong input.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from invoice_extract import __version__
from invoice_extract.analysis import normalize_vat, party_totals, vat_totals
from invoice_extract.checks import check_invoice, partita_iva_ok, split_duplicates
from invoice_extract.loader import iter_documents
from invoice_extract.models import Invoice, Issue
from invoice_extract.p7m import P7mError, extract_xml
from invoice_extract.parser import InvoiceParseError, NotAnInvoice, parse_invoices
from invoice_extract.report import write_csv, write_excel
from invoice_extract.texts import LANGS, UI, money


def _date_arg(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="invoice-extract",
        description="Italian e-invoices (FatturaPA .xml / .xml.p7m / .zip) -> checked data -> Excel report",
    )
    p.add_argument("inputs", nargs="+", type=Path, help="files or folders with .xml, .p7m or .zip")
    p.add_argument("-o", "--output", type=Path, default=Path("report.xlsx"), help="Excel report (default report.xlsx)")
    p.add_argument("--csv", type=Path, metavar="DIR", help="also write fatture.csv, righe.csv, problemi.csv here")
    p.add_argument("--my-vat", default="", help="your partita IVA: splits invoices into issued and received")
    p.add_argument("--from", dest="date_from", type=_date_arg, metavar="YYYY-MM-DD", help="only invoices from")
    p.add_argument("--to", dest="date_to", type=_date_arg, metavar="YYYY-MM-DD", help="only invoices up to")
    p.add_argument("--lang", choices=LANGS, default="ru", help="language of messages (report is in Italian)")
    p.add_argument("--strict", action="store_true", help="exit code 1 if any error is found (for automation)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def load(paths: list[Path]) -> tuple[list[Invoice], list[Issue], int, int]:
    """Reads every document; returns (invoices, read issues, documents seen, non-invoices skipped)."""
    invoices: list[Invoice] = []
    issues: list[Issue] = []
    seen = skipped = 0
    for doc in iter_documents(paths):
        seen += 1
        if doc.error:
            issues.append(Issue.make(doc.name, "error", "unreadable", reason=doc.error))
            continue
        try:
            xml = extract_xml(doc.data) if doc.signed else doc.data
            invoices.extend(parse_invoices(xml, doc.name))
        except NotAnInvoice:
            skipped += 1  # SdI receipts and metadata files often sit next to invoices
        except (InvoiceParseError, P7mError) as exc:
            issues.append(Issue.make(doc.name, "error", "unreadable", reason=exc))
    return invoices, issues, seen, skipped


def _table(rows: list[list[str]]) -> str:
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(
            cell.ljust(w) if i == 0 else cell.rjust(w) for i, (cell, w) in enumerate(zip(row, widths, strict=True))
        )
        for row in rows
    )


def format_summary(invoices: list[Invoice], my_vat: str, lang: str) -> str:
    t = UI[lang]
    rows = [[t["rate"], t["taxable"], t["tax"]]]
    taxable_total = tax_total = None
    for r in vat_totals(invoices, my_vat):
        label = f"{r.vat_rate:f}%" + (f" {r.nature}" if r.nature else "")
        if r.direction:
            label = f"{t[r.direction]} {label}"
        rows.append([label, money(r.taxable, lang), money(r.tax, lang)])
        taxable_total = r.taxable if taxable_total is None else taxable_total + r.taxable
        tax_total = r.tax if tax_total is None else tax_total + r.tax
    if taxable_total is not None and not my_vat:
        rows.append([t["total"], money(taxable_total, lang), money(tax_total, lang)])

    parties = [[t["parties"], t["count"], t["sum"]]]
    for p in party_totals(invoices, my_vat)[:5]:
        parties.append([p.name[:40], str(p.invoices), money(p.gross, lang)])
    return _table(rows) + "\n\n" + _table(parties)


def run(argv: Sequence[str] | None = None, today: date | None = None) -> int:
    args = build_parser().parse_args(argv)
    t = UI[args.lang]
    my_vat = normalize_vat(args.my_vat)
    if my_vat and not partita_iva_ok(my_vat):
        print(t["bad_vat_arg"].format(value=args.my_vat), file=sys.stderr)
        return 2

    try:
        invoices, issues, seen, skipped = load(args.inputs)
    except FileNotFoundError as exc:
        print(t["not_found"].format(path=exc.args[0]), file=sys.stderr)
        return 2
    if seen == 0:
        print(t["no_files"], file=sys.stderr)
        return 2
    if not invoices and not issues:
        print(t["no_invoices"], file=sys.stderr)
        return 2

    if args.date_from:
        invoices = [i for i in invoices if i.date >= args.date_from]
    if args.date_to:
        invoices = [i for i in invoices if i.date <= args.date_to]

    unique, duplicate_issues = split_duplicates(invoices)
    today = today or date.today()
    for inv in unique:
        issues.extend(check_invoice(inv, today))
    issues.extend(duplicate_issues)

    write_excel(args.output, unique, issues, my_vat, args.lang)
    if args.csv:
        write_csv(args.csv, unique, issues, my_vat, args.lang)

    errors = sum(i.level == "error" for i in issues)
    print(t["files"].format(files=seen, invoices=len(unique), duplicates=len(duplicate_issues), skipped=skipped))
    line = t["issues"].format(errors=errors, warnings=len(issues) - errors)
    print(line + (f" — {t['see_sheet']}" if issues else ""))
    if unique:
        print()
        print(format_summary(unique, my_vat, args.lang))
    print()
    print(t["saved"].format(path=args.output))
    if args.csv:
        print(t["csv_saved"].format(path=args.csv))
    return 1 if args.strict and errors else 0


def main() -> int:
    return run()
