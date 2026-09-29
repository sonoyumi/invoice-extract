"""Messages in Russian and Italian (`--lang ru|it`). The Excel report itself is always in Italian:
it goes to Italian accountants, and FatturaPA terms (Imponibile, Natura, ...) have no good translation."""

from __future__ import annotations

from decimal import Decimal

from invoice_extract.models import Issue

LANGS = ("ru", "it")

ISSUES = {
    "ru": {
        "unreadable": "файл не прочитан: {reason}",
        "supplier_no_vat": "у поставщика нет партиты IVA (IdFiscaleIVA)",
        "bad_vat": "неверная партита IVA {who}: {value} (контрольная цифра не сходится)",
        "bad_tax_code": "неверный codice fiscale {who}: {value}",
        "unknown_type": "неизвестный тип документа {value}",
        "currency": "валюта {value}, а не EUR: суммы в отчёте в этой валюте",
        "future_date": "дата счёта в будущем: {value}",
        "no_lines": "в счёте нет строк (DettaglioLinee)",
        "no_vat_summary": "в счёте нет сводки НДС (DatiRiepilogo)",
        "nature_missing": "строка {line}: ставка 0% без кода Natura",
        "nature_missing_summary": "сводка {rate}: ставка 0% без кода Natura",
        "taxable_mismatch": "ставка {rate}: сумма строк не равна базе в сводке (разница {diff} €)",
        "tax_mismatch": "ставка {rate}: НДС должен быть {expected} €, в счёте {found} €",
        "summary_missing": "для строк со ставкой {rate} нет сводки НДС",
        "total_mismatch": "итог документа {total} € не равен база + НДС = {computed} €",
        "payment_mismatch": "платежи {paid} € не равны сумме к оплате {due} €",
        "duplicate": "дубль счёта № {number} (первый: {first}), в итоги не вошёл",
    },
    "it": {
        "unreadable": "file non leggibile: {reason}",
        "supplier_no_vat": "il cedente non ha la partita IVA (IdFiscaleIVA)",
        "bad_vat": "partita IVA del {who} non valida: {value} (cifra di controllo errata)",
        "bad_tax_code": "codice fiscale del {who} non valido: {value}",
        "unknown_type": "tipo documento sconosciuto {value}",
        "currency": "divisa {value} invece di EUR: gli importi del report sono in questa divisa",
        "future_date": "data fattura nel futuro: {value}",
        "no_lines": "la fattura non ha righe (DettaglioLinee)",
        "no_vat_summary": "la fattura non ha il riepilogo IVA (DatiRiepilogo)",
        "nature_missing": "riga {line}: aliquota 0% senza codice Natura",
        "nature_missing_summary": "riepilogo {rate}: aliquota 0% senza codice Natura",
        "taxable_mismatch": "aliquota {rate}: somma delle righe diversa dall'imponibile (differenza {diff} €)",
        "tax_mismatch": "aliquota {rate}: l'imposta dovrebbe essere {expected} €, in fattura {found} €",
        "summary_missing": "manca il riepilogo IVA per le righe con aliquota {rate}",
        "total_mismatch": "totale documento {total} € diverso da imponibile + IVA = {computed} €",
        "payment_mismatch": "pagamenti {paid} € diversi dal netto a pagare {due} €",
        "duplicate": "fattura n. {number} duplicata (prima: {first}), esclusa dai totali",
    },
}

WHO = {
    "ru": {"supplier": "поставщика", "customer": "покупателя"},
    "it": {"supplier": "cedente", "customer": "cessionario"},
}

UI = {
    "ru": {
        "files": "Файлов: {files} · счетов: {invoices} · дублей: {duplicates} · не счета (пропущены): {skipped}",
        "issues": "Ошибок: {errors} · предупреждений: {warnings}",
        "see_sheet": "подробности на листе «Problemi»",
        "rate": "Ставка",
        "taxable": "База",
        "tax": "НДС",
        "total": "ИТОГО",
        "parties": "Контрагенты (топ-5 по сумме):",
        "count": "Счетов",
        "sum": "Сумма",
        "saved": "Отчёт сохранён: {path}",
        "csv_saved": "CSV сохранены в папку: {path}",
        "no_files": "Не найдено ни одного файла .xml, .p7m или .zip",
        "not_found": "Файл или папка не найдены: {path}",
        "no_invoices": "Ни один файл не удалось прочитать как счёт FatturaPA",
        "bad_vat_arg": "--my-vat: неверная партита IVA {value}",
        "out": "выставлен",
        "in": "получен",
    },
    "it": {
        "files": "File: {files} · fatture: {invoices} · duplicati: {duplicates} · non fatture (saltati): {skipped}",
        "issues": "Errori: {errors} · avvisi: {warnings}",
        "see_sheet": "dettagli nel foglio «Problemi»",
        "rate": "Aliquota",
        "taxable": "Imponibile",
        "tax": "IVA",
        "total": "TOTALE",
        "parties": "Controparti (prime 5 per importo):",
        "count": "Fatture",
        "sum": "Importo",
        "saved": "Report salvato: {path}",
        "csv_saved": "CSV salvati nella cartella: {path}",
        "no_files": "Nessun file .xml, .p7m o .zip trovato",
        "not_found": "File o cartella non trovati: {path}",
        "no_invoices": "Nessun file è stato letto come fattura FatturaPA",
        "bad_vat_arg": "--my-vat: partita IVA non valida {value}",
        "out": "emessa",
        "in": "ricevuta",
    },
}


MONEY_PARAMS = ("diff", "expected", "found", "total", "computed", "paid", "due")


def issue_text(issue: Issue, lang: str = "ru") -> str:
    params = dict(issue.params)
    for key in MONEY_PARAMS:
        if key in params:
            params[key] = params[key].replace(".", ",")  # 39.60 -> 39,60 in both languages
    if "who" in params:
        params["who"] = WHO[lang].get(params["who"], params["who"])
    return ISSUES[lang].get(issue.code, issue.code).format(**params)


def money(value: Decimal, lang: str = "ru") -> str:
    """1234.5 -> '1 234,50' (ru) or '1.234,50' (it)."""
    text = f"{value:,.2f}"  # '1,234.50'
    thousands = " " if lang == "ru" else "."
    return text.replace(",", "\0").replace(".", ",").replace("\0", thousands)
