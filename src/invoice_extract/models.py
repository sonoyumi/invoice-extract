"""Plain data classes for a parsed invoice. Money is always Decimal, never float."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")

# Document types (TipoDocumento) that reduce amounts: credit notes.
CREDIT_NOTES = frozenset({"TD04", "TD08"})

DOC_TYPES = {
    "TD01": "Fattura",
    "TD02": "Acconto/anticipo su fattura",
    "TD03": "Acconto/anticipo su parcella",
    "TD04": "Nota di credito",
    "TD05": "Nota di debito",
    "TD06": "Parcella",
    "TD07": "Fattura semplificata",
    "TD08": "Nota di credito semplificata",
    "TD09": "Nota di debito semplificata",
    "TD16": "Integrazione reverse charge interno",
    "TD17": "Integrazione/autofattura servizi dall'estero",
    "TD18": "Integrazione acquisto beni intracomunitari",
    "TD19": "Integrazione/autofattura beni ex art.17 c.2",
    "TD20": "Autofattura per regolarizzazione",
    "TD21": "Autofattura per splafonamento",
    "TD22": "Estrazione beni da Deposito IVA",
    "TD23": "Estrazione beni da Deposito IVA con versamento IVA",
    "TD24": "Fattura differita (art.21 c.4 lett. a)",
    "TD25": "Fattura differita (art.21 c.4 terzo periodo lett. b)",
    "TD26": "Cessione di beni ammortizzabili",
    "TD27": "Autoconsumo o cessioni gratuite senza rivalsa",
    "TD28": "Acquisti da San Marino con IVA",
    "TD29": "Omessa o irregolare fatturazione",
}


@dataclass(frozen=True)
class Party:
    name: str
    country: str  # IdPaese, e.g. "IT"
    vat: str  # IdCodice: the partita IVA without the country prefix
    tax_code: str  # CodiceFiscale

    @property
    def key(self) -> str:
        """Stable identifier: country + VAT number, or the tax code for private persons."""
        return f"{self.country}{self.vat}" if self.vat else self.tax_code

    @property
    def fiscal_id(self) -> str:
        return self.key or "—"


@dataclass(frozen=True)
class Line:
    number: int
    description: str
    quantity: Decimal | None
    unit_price: Decimal
    total: Decimal
    vat_rate: Decimal
    nature: str  # Natura: why the VAT rate is 0 (N1..N7), empty otherwise


@dataclass(frozen=True)
class VatSummary:
    vat_rate: Decimal
    nature: str
    taxable: Decimal
    tax: Decimal
    rounding: Decimal
    chargeability: str  # EsigibilitaIVA: I immediate, D deferred, S split payment


@dataclass(frozen=True)
class Payment:
    method: str  # ModalitaPagamento, e.g. MP05 = bank transfer
    due: date | None
    amount: Decimal | None
    iban: str


@dataclass
class Invoice:
    source: str  # file name, with "#2" for the second invoice of a batch file
    doc_type: str
    currency: str
    number: str
    date: date
    supplier: Party
    customer: Party
    total: Decimal | None  # ImportoTotaleDocumento: optional in the XML
    lines: list[Line] = field(default_factory=list)
    vat: list[VatSummary] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    withholding: Decimal = ZERO  # ritenuta d'acconto
    stamp: Decimal = ZERO  # imposta di bollo
    description: str = ""

    @property
    def sign(self) -> int:
        """-1 for credit notes, so report totals are correct without special cases."""
        return -1 if self.doc_type in CREDIT_NOTES else 1

    @property
    def type_name(self) -> str:
        return DOC_TYPES.get(self.doc_type, self.doc_type)

    @property
    def taxable(self) -> Decimal:
        return sum((v.taxable for v in self.vat), ZERO)

    @property
    def tax(self) -> Decimal:
        return sum((v.tax for v in self.vat), ZERO)

    @property
    def gross(self) -> Decimal:
        """Document total: the declared one if present, otherwise taxable + VAT."""
        return self.total if self.total is not None else self.taxable + self.tax

    @property
    def to_pay(self) -> Decimal:
        return self.gross - self.withholding

    @property
    def key(self) -> tuple[str, str, str, date]:
        """Same supplier, type, number and date = the same invoice (a duplicate file)."""
        return (self.supplier.key, self.doc_type, self.number.strip().upper(), self.date)


@dataclass(frozen=True)
class Issue:
    source: str
    level: str  # "error" or "warning"
    code: str
    params: tuple[tuple[str, str], ...] = ()

    @classmethod
    def make(cls, source: str, level: str, code: str, **params: object) -> Issue:
        return cls(source, level, code, tuple((k, str(v)) for k, v in params.items()))
