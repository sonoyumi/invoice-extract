"""Excel report (always) and CSV files (optional).

Sheets: Fatture · Righe · Riepilogo IVA · Controparti · Scadenze · Problemi.
Credit notes are negative everywhere, so every SUM in Excel is correct as is.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from invoice_extract.analysis import IN, OUT, deadlines, direction, party_totals, vat_totals
from invoice_extract.models import Invoice, Issue
from invoice_extract.texts import issue_text

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="305496")
ERROR_FONT = Font(color="C00000")
MONEY_FORMAT = "#,##0.00"
DATE_FORMAT = "DD/MM/YYYY"
MAX_WIDTH = 60
DIRECTION_IT = {OUT: "Emessa", IN: "Ricevuta", "": ""}
LEVEL_IT = {"error": "ERRORE", "warning": "avviso"}

INVOICE_HEADER = [
    "Direzione",
    "Tipo",
    "Descrizione tipo",
    "Numero",
    "Data",
    "Fornitore",
    "P.IVA fornitore",
    "Cliente",
    "P.IVA / CF cliente",
    "Imponibile",
    "IVA",
    "Totale",
    "Ritenuta",
    "Bollo",
    "Netto a pagare",
    "Prima scadenza",
    "Causale",
    "File",
]
LINE_HEADER = [
    "Numero fattura",
    "Data",
    "Fornitore",
    "Riga",
    "Descrizione",
    "Quantità",
    "Prezzo unitario",
    "Totale riga",
    "Aliquota IVA %",
    "Natura",
    "File",
]
VAT_HEADER = ["Direzione", "Aliquota IVA %", "Natura", "Imponibile", "Imposta", "N. fatture"]
PARTY_HEADER = ["Controparte", "P.IVA / CF", "N. fatture", "Imponibile", "IVA", "Totale"]
DUE_HEADER = ["Scadenza", "Controparte", "Numero fattura", "Importo", "Modalità", "IBAN", "File"]
ISSUE_HEADER = ["Livello", "File", "Codice", "Messaggio"]


def _invoice_rows(invoices: list[Invoice], my_vat: str) -> list[list[Any]]:
    rows = []
    for inv in invoices:
        s = inv.sign
        first_due = min((p.due for p in inv.payments if p.due), default=None)
        rows.append(
            [
                DIRECTION_IT[direction(inv, my_vat)],
                inv.doc_type,
                inv.type_name,
                inv.number,
                inv.date,
                inv.supplier.name,
                inv.supplier.fiscal_id,
                inv.customer.name,
                inv.customer.fiscal_id,
                inv.taxable * s,
                inv.tax * s,
                inv.gross * s,
                inv.withholding * s,
                inv.stamp,
                inv.to_pay * s,
                first_due,
                inv.description,
                inv.source,
            ]
        )
    return rows


def _line_rows(invoices: list[Invoice]) -> list[list[Any]]:
    return [
        [
            inv.number,
            inv.date,
            inv.supplier.name,
            line.number,
            line.description,
            line.quantity,
            line.unit_price,
            line.total * inv.sign,
            line.vat_rate,
            line.nature,
            inv.source,
        ]
        for inv in invoices
        for line in inv.lines
    ]


def _set(cell, value: Any) -> None:
    cell.value = value
    # A description like "=HYPERLINK(...)" from someone else's invoice must stay text.
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"
    elif isinstance(value, Decimal):
        cell.number_format = MONEY_FORMAT
    elif isinstance(value, date):
        cell.number_format = DATE_FORMAT


def _fill(sheet: Worksheet, header: list[str], rows: Sequence[Sequence[Any]]) -> None:
    sheet.append(header)
    for cell in sheet[1]:
        cell.font, cell.fill, cell.alignment = HEADER_FONT, HEADER_FILL, Alignment(vertical="center")
    for values in rows:
        r = sheet.max_row + 1
        for c, value in enumerate(values, start=1):
            _set(sheet.cell(row=r, column=c), value)
    sheet.freeze_panes = "A2"
    if rows:
        sheet.auto_filter.ref = sheet.dimensions
    for index, column in enumerate(sheet.iter_cols(min_row=1, max_row=min(sheet.max_row, 500)), start=1):
        longest = max((len(str(c.value)) for c in column if c.value is not None), default=0)
        sheet.column_dimensions[get_column_letter(index)].width = min(max(longest, 8) + 2, MAX_WIDTH)


def write_excel(path: Path, invoices: list[Invoice], issues: list[Issue], my_vat: str = "", lang: str = "ru") -> Path:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Fatture"
    _fill(sheet, INVOICE_HEADER, _invoice_rows(invoices, my_vat))
    _fill(wb.create_sheet("Righe"), LINE_HEADER, _line_rows(invoices))
    _fill(
        wb.create_sheet("Riepilogo IVA"),
        VAT_HEADER,
        [
            [DIRECTION_IT[r.direction], r.vat_rate, r.nature, r.taxable, r.tax, r.invoices]
            for r in vat_totals(invoices, my_vat)
        ],
    )
    _fill(
        wb.create_sheet("Controparti"),
        PARTY_HEADER,
        [[r.name, r.fiscal_id, r.invoices, r.taxable, r.tax, r.gross] for r in party_totals(invoices, my_vat)],
    )
    _fill(
        wb.create_sheet("Scadenze"),
        DUE_HEADER,
        [[r.due, r.party, r.number, r.amount, r.method, r.iban, r.source] for r in deadlines(invoices, my_vat)],
    )
    problems = wb.create_sheet("Problemi")
    ordered = sorted(issues, key=lambda i: (i.level != "error", i.source))
    _fill(problems, ISSUE_HEADER, [[LEVEL_IT[i.level], i.source, i.code, issue_text(i, lang)] for i in ordered])
    for row in problems.iter_rows(min_row=2):
        if row[0].value == LEVEL_IT["error"]:
            for cell in row:
                cell.font = ERROR_FONT

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}".replace(".", ",")  # Italian Excel expects a decimal comma
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    # CSV injection: Excel runs cells starting with these characters as formulas.
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel opens UTF-8 correctly
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows([_csv_value(v) for v in row] for row in rows)


def write_csv(folder: Path, invoices: list[Invoice], issues: list[Issue], my_vat: str = "", lang: str = "ru") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "fatture.csv", INVOICE_HEADER, _invoice_rows(invoices, my_vat))
    _write_csv(folder / "righe.csv", LINE_HEADER, _line_rows(invoices))
    _write_csv(
        folder / "problemi.csv",
        ISSUE_HEADER,
        [[LEVEL_IT[i.level], i.source, i.code, issue_text(i, lang)] for i in issues],
    )
    return folder
