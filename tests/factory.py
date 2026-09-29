"""Builders for test invoices: FatturaPA XML text and a .p7m envelope around it."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
SUPPLIER_VAT = "01234567897"  # valid check digit
CUSTOMER_VAT = "02345678904"  # valid check digit


@dataclass
class L:
    description: str
    quantity: str
    price: str
    rate: str = "22.00"
    nature: str = ""

    @property
    def total(self) -> Decimal:
        return (Decimal(self.quantity) * Decimal(self.price)).quantize(Decimal("0.01"), ROUND_HALF_UP)


@dataclass
class Body:
    number: str = "1/A"
    date: str = "2026-03-10"
    doc_type: str = "TD01"
    lines: list[L] = field(default_factory=lambda: [L("Consulenza", "2", "50.00")])
    total: str | None = "auto"  # "auto" = computed, None = omit the element
    summary_override: dict[str, str] = field(default_factory=dict)  # rate -> taxable text
    tax_override: dict[str, str] = field(default_factory=dict)  # rate -> tax text
    payments: list[tuple[str, str]] | None = None  # (due date, amount); None = one payment of the total
    withholding: str = ""
    stamp: str = ""
    currency: str = "EUR"
    causale: str = ""


def _party(tag: str, name: str, vat: str, tax_code: str, country: str = "IT") -> str:
    vat_xml = f"<IdFiscaleIVA><IdPaese>{country}</IdPaese><IdCodice>{vat}</IdCodice></IdFiscaleIVA>" if vat else ""
    cf_xml = f"<CodiceFiscale>{tax_code}</CodiceFiscale>" if tax_code else ""
    return (
        f"<{tag}><DatiAnagrafici>{vat_xml}{cf_xml}<Anagrafica><Denominazione>{escape(name)}</Denominazione>"
        f"</Anagrafica><RegimeFiscale>RF01</RegimeFiscale></DatiAnagrafici>"
        f"<Sede><Indirizzo>Via Roma 1</Indirizzo><CAP>39100</CAP><Comune>Bolzano</Comune>"
        f"<Provincia>BZ</Provincia><Nazione>IT</Nazione></Sede></{tag}>"
    )


def _body(b: Body) -> str:
    groups: dict[tuple[str, str], Decimal] = {}
    lines_xml = []
    for i, line in enumerate(b.lines, 1):
        nature = f"<Natura>{line.nature}</Natura>" if line.nature else ""
        lines_xml.append(
            f"<DettaglioLinee><NumeroLinea>{i}</NumeroLinea><Descrizione>{escape(line.description)}</Descrizione>"
            f"<Quantita>{line.quantity}</Quantita><PrezzoUnitario>{line.price}</PrezzoUnitario>"
            f"<PrezzoTotale>{line.total}</PrezzoTotale><AliquotaIVA>{line.rate}</AliquotaIVA>{nature}</DettaglioLinee>"
        )
        groups[(line.rate, line.nature)] = groups.get((line.rate, line.nature), Decimal(0)) + line.total

    summaries, taxable_sum, tax_sum = [], Decimal(0), Decimal(0)
    for (rate, nature), taxable in groups.items():
        taxable = Decimal(b.summary_override.get(rate, taxable))
        tax = (taxable * Decimal(rate) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
        tax = Decimal(b.tax_override.get(rate, tax))
        taxable_sum += taxable
        tax_sum += tax
        nature_xml = f"<Natura>{nature}</Natura>" if nature else ""
        summaries.append(
            f"<DatiRiepilogo><AliquotaIVA>{rate}</AliquotaIVA>{nature_xml}<ImponibileImporto>{taxable:.2f}"
            f"</ImponibileImporto><Imposta>{tax:.2f}</Imposta><EsigibilitaIVA>I</EsigibilitaIVA></DatiRiepilogo>"
        )

    gross = taxable_sum + tax_sum
    total_xml = ""
    if b.total == "auto":
        total_xml = f"<ImportoTotaleDocumento>{gross:.2f}</ImportoTotaleDocumento>"
    elif b.total is not None:
        total_xml = f"<ImportoTotaleDocumento>{b.total}</ImportoTotaleDocumento>"
    ritenuta = (
        f"<DatiRitenuta><TipoRitenuta>RT01</TipoRitenuta><ImportoRitenuta>{b.withholding}</ImportoRitenuta>"
        f"<AliquotaRitenuta>20.00</AliquotaRitenuta><CausalePagamento>A</CausalePagamento></DatiRitenuta>"
        if b.withholding
        else ""
    )
    bollo = (
        f"<DatiBollo><BolloVirtuale>SI</BolloVirtuale><ImportoBollo>{b.stamp}</ImportoBollo></DatiBollo>"
        if b.stamp
        else ""
    )
    causale = f"<Causale>{escape(b.causale)}</Causale>" if b.causale else ""

    payments = b.payments
    if payments is None:
        to_pay = gross - (Decimal(b.withholding) if b.withholding else 0)
        payments = [("2026-04-30", f"{to_pay:.2f}")]
    pay_xml = "".join(
        f"<DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento><DataScadenzaPagamento>{due}"
        f"</DataScadenzaPagamento><ImportoPagamento>{amount}</ImportoPagamento>"
        f"<IBAN>IT60X0542811101000000123456</IBAN></DettaglioPagamento>"
        for due, amount in payments
    )
    pay_block = (
        f"<DatiPagamento><CondizioniPagamento>TP02</CondizioniPagamento>{pay_xml}</DatiPagamento>" if payments else ""
    )

    return (
        f"<FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>{b.doc_type}</TipoDocumento>"
        f"<Divisa>{b.currency}</Divisa><Data>{b.date}</Data><Numero>{b.number}</Numero>{ritenuta}{bollo}{total_xml}"
        f"{causale}</DatiGeneraliDocumento></DatiGenerali><DatiBeniServizi>{''.join(lines_xml)}{''.join(summaries)}"
        f"</DatiBeniServizi>{pay_block}</FatturaElettronicaBody>"
    )


def invoice_xml(
    *bodies: Body,
    supplier: str = "Tipografia Alpina Srl",
    supplier_vat: str = SUPPLIER_VAT,
    customer: str = "Bar Centrale Srl",
    customer_vat: str = CUSTOMER_VAT,
    customer_cf: str = "",
    prefix: str = "p",
) -> bytes:
    bodies = bodies or (Body(),)
    root = f"{prefix}:FatturaElettronica" if prefix else "FatturaElettronica"
    ns = f'xmlns:{prefix}="{NS}"' if prefix else f'xmlns="{NS}"'
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} versione="FPR12" {ns}>'
        f"<FatturaElettronicaHeader><DatiTrasmissione><IdTrasmittente><IdPaese>IT</IdPaese>"
        f"<IdCodice>{supplier_vat}</IdCodice></IdTrasmittente><ProgressivoInvio>00001</ProgressivoInvio>"
        f"<FormatoTrasmissione>FPR12</FormatoTrasmissione><CodiceDestinatario>0000000</CodiceDestinatario>"
        f"</DatiTrasmissione>"
        f"{_party('CedentePrestatore', supplier, supplier_vat, '')}"
        f"{_party('CessionarioCommittente', customer, customer_vat, customer_cf)}"
        f"</FatturaElettronicaHeader>{''.join(_body(b) for b in bodies)}</{root}>"
    )
    return xml.encode("utf-8")


# --- a minimal DER/BER encoder, enough to build a CMS SignedData envelope ---------------------


def _len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def tlv(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _len(len(content)) + content


def tlv_indefinite(tag: int, content: bytes) -> bytes:
    return bytes([tag, 0x80]) + content + b"\x00\x00"


OID_SIGNED_DATA = tlv(0x06, bytes.fromhex("2a864886f70d010702"))
OID_DATA = tlv(0x06, bytes.fromhex("2a864886f70d010701"))


def p7m(xml: bytes, chunked: bool = False) -> bytes:
    """SignedData with the XML inside (no real signature: the reader does not verify it)."""
    if chunked:  # BER: constructed OCTET STRING, indefinite length, 100-byte pieces
        pieces = b"".join(tlv(0x04, xml[i : i + 100]) for i in range(0, len(xml), 100))
        econtent = tlv_indefinite(0x24, pieces)
    else:
        econtent = tlv(0x04, xml)
    encap = tlv(0x30, OID_DATA + tlv(0xA0, econtent))
    digest_algs = tlv(0x31, tlv(0x30, tlv(0x06, bytes.fromhex("608648016503040201")) + b"\x05\x00"))
    signer_infos = tlv(0x31, b"")
    signed_data = tlv(0x30, tlv(0x02, b"\x01") + digest_algs + encap + signer_infos)
    return tlv(0x30, OID_SIGNED_DATA + tlv(0xA0, signed_data))
