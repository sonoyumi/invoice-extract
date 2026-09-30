# 🧾 Invoice Extract

<p>
  <a href="https://github.com/sonoyumi/invoice-extract/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/sonoyumi/invoice-extract/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white">
  <img alt="FatturaPA" src="https://img.shields.io/badge/FatturaPA-XML%20%7C%20p7m-009246">
  <img alt="openpyxl" src="https://img.shields.io/badge/Excel-openpyxl-217346?logo=microsoftexcel&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

**🇬🇧 [English](#en)** · **🇮🇹 [Italiano](#it)** · **🇺🇦 [Українська](#uk)** · **🇷🇺 [Русский](#ru)**

---

<a name="en"></a>

## 🇬🇧 English

A command-line tool for Italian **electronic invoices (FatturaPA)**. Point it at a folder or a zip
downloaded from the Cassetto fiscale: it reads plain `.xml` and signed `.xml.p7m` files, checks every
invoice and builds one Excel report for the business owner or the accountant: VAT summary by rate,
totals by supplier, payment deadlines and a list of problems.

### What it handles

- **Inputs:** `.xml`, signed `.xml.p7m` (binary or base64, including chunked BER envelopes), `.zip` archives
  and whole folders. SdI receipts and metadata files lying next to invoices are recognised and skipped.
- **Any XML flavour:** `p:`, `ns2:` or no namespace prefix; batch files with several invoices in one XML.
- **Checks:** partita IVA and codice fiscale check digits; line totals vs VAT summary; VAT amount vs rate;
  0% rate without a *Natura* code; document total vs taxable + VAT (virtual stamp duty accepted);
  installments vs net amount (after *ritenuta d'acconto*); future dates, unknown document types, foreign currency.
  Rounding up to 1 € is a warning, like the SdI tolerance; more than that is an error.
- **Duplicates:** the same invoice downloaded twice is reported once and excluded from totals.
- **Credit notes** (TD04, TD08) are negative everywhere, so every total and every Excel SUM is right.
- **`--my-vat`:** splits invoices into *issued* and *received*; VAT due and VAT deductible are shown separately.
- **Report sheets:** Fatture · Righe · Riepilogo IVA · Controparti · Scadenze · Problemi.
- **Money is `Decimal`,** never float. **XML is parsed with `defusedxml`** (entity-expansion attacks are refused).
  Text like `=HYPERLINK(...)` from someone else's invoice stays text in Excel and CSV.
- **CSV export** (`--csv DIR`) with `;` and decimal comma, ready for Italian Excel.
- **Automation:** `--strict` returns exit code 1 when errors are found; `--from`/`--to` filter by date.

### Example

```bash
invoice-extract examples/ --my-vat IT02345678904
```

```
Файлов: 8 · счетов: 6 · дублей: 1 · не счета (пропущены): 1
Ошибок: 3 · предупреждений: 2 — подробности на листе «Problemi»

Ставка             База     НДС
получен 22%    1 529,60  326,91
получен 10%      222,00   22,20
получен 4%       163,50    6,54
получен 0%        35,00    0,00
выставлен 10%    495,00   49,50

Контрагенты (топ-5 по сумме):  Счетов     Сумма
Studio Grafico Weiss                1  1 220,00
Mario Rossi                         1    544,50
Ortofrutta Bolzano Srl              2    486,95
Tipografia Alpina Srl               1    353,80
Idraulica Rossi                     1    245,00

Отчёт сохранён: report.xlsx
```

Console messages are in Russian by default; `--lang it` switches them to Italian. The Excel report is always in Italian.
The output above: 8 files, 6 invoices, 1 duplicate, 1 non-invoice skipped; 3 errors and 2 warnings; VAT by rate
for received (*получен*) and issued (*выставлен*) invoices; top-5 counterparties.

The [`examples/`](examples) folder is synthetic and shows every case: a signed `.p7m` fee note with withholding tax,
a credit note, a batch with 4%/10%/22% rates and two installments, an invoice issued to a private person,
an invoice with wrong VAT and a 0% line without *Natura*, a duplicate and an SdI receipt.

### Quick start

```bash
git clone https://github.com/sonoyumi/invoice-extract.git
cd invoice-extract
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
invoice-extract --help
```

Tests: `pytest` (58 tests: p7m envelopes, parser, every check, totals, Excel/CSV safety, end-to-end runs).

### Project structure

```
src/invoice_extract/
├── loader.py    # files, folders and zip archives (size limit per file)
├── p7m.py       # XML out of a signed .p7m: a tiny BER/DER reader, no extra libraries
├── parser.py    # FatturaPA XML -> Invoice objects (defusedxml, any namespace, batches)
├── models.py    # dataclasses; money is Decimal
├── checks.py    # partita IVA / codice fiscale, VAT arithmetic, totals, duplicates
├── analysis.py  # VAT summary, counterparties, deadlines (pure functions)
├── report.py    # Excel and CSV (formula-injection safe)
├── texts.py     # messages in Russian and Italian
└── cli.py       # command line and exit codes
```

### Author

**Vladyslav Shokun** ([@sonoyumi](https://github.com/sonoyumi)), Python developer: Telegram bots, web scraping, automation.

[![Telegram](https://img.shields.io/badge/Telegram-write%20me-2CA5E0?logo=telegram&logoColor=white)](https://t.me/sonoyumiii)
[![Email](https://img.shields.io/badge/Email-contact-EA4335?logo=gmail&logoColor=white)](mailto:sonoyumiii@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-profile-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/vladyslav-shokun/)

> 💼 Still copying invoices into Excel by hand? Get in touch, I'll automate it.

### License

MIT, see [LICENSE](LICENSE).

---

<a name="it"></a>

## 🇮🇹 Italiano

**[🇬🇧 English](#en)** · **🇮🇹 Italiano** · **[🇺🇦 Українська](#uk)** · **[🇷🇺 Русский](#ru)**

Uno strumento da riga di comando per le **fatture elettroniche (FatturaPA)**. Basta indicare una cartella o uno zip
scaricato dal Cassetto fiscale: legge i file `.xml` e quelli firmati `.xml.p7m`, controlla ogni fattura e crea
un unico report Excel per il titolare o per il commercialista: riepilogo IVA per aliquota, totali per fornitore,
scadenze di pagamento e l'elenco dei problemi.

### Cosa gestisce

- **Input:** `.xml`, `.xml.p7m` firmati (binari o base64, anche con buste BER a blocchi), archivi `.zip` e intere cartelle.
  Le ricevute SdI e i file di metadati accanto alle fatture vengono riconosciuti e saltati.
- **Qualsiasi XML:** prefisso `p:`, `ns2:` o nessun prefisso; file lotto con più fatture nello stesso XML.
- **Controlli:** cifra di controllo di partita IVA e codice fiscale; righe contro riepilogo IVA; imposta contro aliquota;
  aliquota 0% senza codice *Natura*; totale documento contro imponibile + IVA (bollo virtuale accettato);
  rate di pagamento contro netto a pagare (dopo la ritenuta d'acconto); date future, tipi documento sconosciuti, divisa estera.
  Un arrotondamento fino a 1 € è un avviso, come la tolleranza dello SdI; oltre è un errore.
- **Duplicati:** la stessa fattura scaricata due volte viene segnalata una volta ed esclusa dai totali.
- **Note di credito** (TD04, TD08) negative ovunque: ogni totale e ogni SOMMA in Excel è corretta.
- **`--my-vat`:** separa le fatture *emesse* e *ricevute*; IVA a debito e a credito sono mostrate a parte.
- **Fogli del report:** Fatture · Righe · Riepilogo IVA · Controparti · Scadenze · Problemi.
- **Gli importi sono `Decimal`,** mai float. **L'XML è letto con `defusedxml`** (gli attacchi con entità vengono rifiutati).
  Un testo come `=HYPERLINK(...)` nella fattura di un altro resta testo in Excel e nel CSV.
- **Esportazione CSV** (`--csv DIR`) con `;` e virgola decimale, pronta per Excel in italiano.
- **Automazione:** `--strict` restituisce il codice 1 se ci sono errori; `--from`/`--to` filtrano per data.

### Esempio

```bash
invoice-extract examples/ --my-vat IT02345678904
```

L'output è quello della sezione inglese. I messaggi sono in russo per impostazione predefinita; `--lang it` li mostra in italiano
(«Errori: 3 · avvisi: 2», «Aliquota / Imponibile / IVA», «Report salvato»). Il report Excel è sempre in italiano.
Nell'output: 8 file, 6 fatture, 1 duplicato, 1 file non fattura saltato; 3 errori e 2 avvisi; IVA per aliquota delle fatture
ricevute (*получен*) ed emesse (*выставлен*); le prime 5 controparti.

La cartella [`examples/`](examples) è sintetica e mostra tutti i casi: una parcella firmata `.p7m` con ritenuta, una nota di credito,
una fattura con aliquote 4%/10%/22% e due rate, una fattura emessa a un privato, una fattura con IVA errata e una riga
al 0% senza *Natura*, un duplicato e una ricevuta SdI.

### Avvio rapido

```bash
git clone https://github.com/sonoyumi/invoice-extract.git
cd invoice-extract
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
invoice-extract --help
```

Test: `pytest` (58 test: buste p7m, parser, ogni controllo, totali, sicurezza di Excel/CSV, esecuzioni end-to-end).

### Struttura del progetto

```
src/invoice_extract/
├── loader.py    # file, cartelle e archivi zip (limite di dimensione per file)
├── p7m.py       # XML da un .p7m firmato: un piccolo lettore BER/DER, senza librerie esterne
├── parser.py    # FatturaPA XML -> oggetti Invoice (defusedxml, qualsiasi namespace, lotti)
├── models.py    # dataclass; gli importi sono Decimal
├── checks.py    # partita IVA / codice fiscale, calcoli IVA, totali, duplicati
├── analysis.py  # riepilogo IVA, controparti, scadenze (funzioni pure)
├── report.py    # Excel e CSV (protetti dalla formula injection)
├── texts.py     # messaggi in russo e in italiano
└── cli.py       # riga di comando e codici di uscita
```

### Autore

**Vladyslav Shokun** ([@sonoyumi](https://github.com/sonoyumi)), sviluppatore Python: bot Telegram, web scraping, automazione.

[![Telegram](https://img.shields.io/badge/Telegram-write%20me-2CA5E0?logo=telegram&logoColor=white)](https://t.me/sonoyumiii)
[![Email](https://img.shields.io/badge/Email-contact-EA4335?logo=gmail&logoColor=white)](mailto:sonoyumiii@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-profile-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/vladyslav-shokun/)

> 💼 Copiate ancora le fatture in Excel a mano? Scrivetemi, lo automatizzo io.

### Licenza

MIT, vedi [LICENSE](LICENSE).

---

<a name="uk"></a>

## 🇺🇦 Українська

**[🇬🇧 English](#en)** · **[🇮🇹 Italiano](#it)** · **🇺🇦 Українська** · **[🇷🇺 Русский](#ru)**

Утиліта командного рядка для італійських **електронних рахунків (FatturaPA)**. Вказуєте папку або zip-архів
із Cassetto fiscale — програма читає звичайні `.xml` і підписані `.xml.p7m`, перевіряє кожен рахунок
і складає один Excel-звіт для власника бізнесу чи бухгалтера: ПДВ за ставками, суми за постачальниками,
терміни оплат і список проблем.

### З чим справляється

- **Вхідні файли:** `.xml`, підписані `.xml.p7m` (бінарні або base64, зокрема BER-конверти частинами), архіви `.zip`
  і цілі папки. Квитанції SdI та файли метаданих поруч із рахунками розпізнаються й пропускаються.
- **Будь-який XML:** префікс `p:`, `ns2:` або без префікса; «пакетні» файли з кількома рахунками в одному XML.
- **Перевірки:** контрольні цифри partita IVA та codice fiscale; сума рядків проти зведення ПДВ; ПДВ проти ставки;
  ставка 0% без коду *Natura*; підсумок документа проти бази + ПДВ (віртуальна марка bollo допускається);
  платежі проти суми до сплати (після ritenuta d'acconto); дати в майбутньому, невідомі типи документів, інша валюта.
  Розбіжність до 1 € — попередження, як допуск SdI; більше — помилка.
- **Дублікати:** той самий рахунок, завантажений двічі, позначається один раз і не входить у підсумки.
- **Кредит-ноти** (TD04, TD08) скрізь від'ємні — кожен підсумок і кожна СУМА в Excel правильні.
- **`--my-vat`:** ділить рахунки на *виставлені* й *отримані*; ПДВ до сплати й до відрахування показано окремо.
- **Аркуші звіту:** Fatture · Righe · Riepilogo IVA · Controparti · Scadenze · Problemi.
- **Гроші — `Decimal`,** ніколи не float. **XML читається через `defusedxml`** (атаки через сутності відхиляються).
  Текст на кшталт `=HYPERLINK(...)` із чужого рахунку залишається текстом в Excel і CSV.
- **Експорт CSV** (`--csv DIR`) з `;` і десятковою комою — для італійського Excel.
- **Автоматизація:** `--strict` повертає код 1, якщо є помилки; `--from`/`--to` — фільтр за датою.

### Приклад

```bash
invoice-extract examples/ --my-vat IT02345678904
```

Вивід — як в англійському розділі. Повідомлення за замовчуванням російською; `--lang it` перемикає на італійську.
Excel-звіт завжди італійською. У виводі: 8 файлів, 6 рахунків, 1 дубль, 1 файл не рахунок пропущено; 3 помилки
й 2 попередження; ПДВ за ставками для отриманих (*получен*) і виставлених (*выставлен*) рахунків; топ-5 контрагентів.

Папка [`examples/`](examples) синтетична й показує всі випадки: підписаний `.p7m` рахунок фрилансера з ritenuta,
кредит-ноту, рахунок зі ставками 4%/10%/22% і двома платежами, рахунок приватній особі, рахунок із неправильним ПДВ
і рядком 0% без *Natura*, дубль і квитанцію SdI.

### Швидкий старт

```bash
git clone https://github.com/sonoyumi/invoice-extract.git
cd invoice-extract
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
invoice-extract --help
```

Тести: `pytest` (58 тестів: конверти p7m, парсер, кожна перевірка, підсумки, безпека Excel/CSV, наскрізні запуски).

### Структура проєкту

```
src/invoice_extract/
├── loader.py    # файли, папки й zip-архіви (ліміт розміру файлу)
├── p7m.py       # XML із підписаного .p7m: маленький BER/DER-рідер без сторонніх бібліотек
├── parser.py    # FatturaPA XML -> об'єкти Invoice (defusedxml, будь-який namespace, пакети)
├── models.py    # dataclass-и; гроші — Decimal
├── checks.py    # partita IVA / codice fiscale, розрахунок ПДВ, підсумки, дублікати
├── analysis.py  # зведення ПДВ, контрагенти, терміни оплат (чисті функції)
├── report.py    # Excel і CSV (захист від formula injection)
├── texts.py     # повідомлення російською та італійською
└── cli.py       # командний рядок і коди виходу
```

### Автор

**Vladyslav Shokun** ([@sonoyumi](https://github.com/sonoyumi)) — Python-розробник: Telegram-боти, парсинг, автоматизація.

[![Telegram](https://img.shields.io/badge/Telegram-write%20me-2CA5E0?logo=telegram&logoColor=white)](https://t.me/sonoyumiii)
[![Email](https://img.shields.io/badge/Email-contact-EA4335?logo=gmail&logoColor=white)](mailto:sonoyumiii@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-profile-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/vladyslav-shokun/)

> 💼 Досі переносите рахунки в Excel вручну? Напишіть мені, автоматизую.

### Ліцензія

MIT — див. [LICENSE](LICENSE).

---

<a name="ru"></a>

## 🇷🇺 Русский

**[🇬🇧 English](#en)** · **[🇮🇹 Italiano](#it)** · **[🇺🇦 Українська](#uk)** · **🇷🇺 Русский**

Утилита командной строки для итальянских **электронных счетов (FatturaPA)**. Указываете папку или zip-архив
из Cassetto fiscale — программа читает обычные `.xml` и подписанные `.xml.p7m`, проверяет каждый счёт
и собирает один Excel-отчёт для владельца бизнеса или бухгалтера: НДС по ставкам, суммы по поставщикам,
сроки оплат и список проблем.

### С чем справляется

- **Входные файлы:** `.xml`, подписанные `.xml.p7m` (двоичные или base64, в том числе BER-конверты по частям), архивы `.zip`
  и целые папки. Квитанции SdI и файлы метаданных рядом со счетами распознаются и пропускаются.
- **Любой XML:** префикс `p:`, `ns2:` или без префикса; «пакетные» файлы с несколькими счетами в одном XML.
- **Проверки:** контрольные цифры partita IVA и codice fiscale; сумма строк против сводки НДС; НДС против ставки;
  ставка 0% без кода *Natura*; итог документа против базы + НДС (виртуальная марка bollo допускается);
  платежи против суммы к оплате (после ritenuta d'acconto); даты в будущем, неизвестные типы документов, другая валюта.
  Расхождение до 1 € — предупреждение, как допуск SdI; больше — ошибка.
- **Дубли:** один и тот же счёт, скачанный дважды, отмечается один раз и не входит в итоги.
- **Кредит-ноты** (TD04, TD08) везде отрицательные — каждый итог и каждая СУММ в Excel правильные.
- **`--my-vat`:** делит счета на *выставленные* и *полученные*; НДС к уплате и к вычету показан отдельно.
- **Листы отчёта:** Fatture · Righe · Riepilogo IVA · Controparti · Scadenze · Problemi.
- **Деньги — `Decimal`,** никогда не float. **XML читается через `defusedxml`** (атаки через сущности отклоняются).
  Текст вроде `=HYPERLINK(...)` из чужого счёта остаётся текстом в Excel и CSV.
- **Экспорт CSV** (`--csv DIR`) с `;` и десятичной запятой — для итальянского Excel.
- **Автоматизация:** `--strict` возвращает код 1, если есть ошибки; `--from`/`--to` — фильтр по дате.

### Пример

```bash
invoice-extract examples/ --my-vat IT02345678904
```

Вывод — как в английском разделе выше. Сообщения по умолчанию на русском, `--lang it` — на итальянском.
Excel-отчёт всегда на итальянском: он уходит итальянскому бухгалтеру.

Папка [`examples/`](examples) синтетическая и показывает все случаи: подписанный `.p7m` счёт фрилансера с ritenuta,
кредит-ноту, счёт со ставками 4%/10%/22% и двумя платежами, счёт частному лицу, счёт с неверным НДС и строкой 0%
без *Natura*, дубль и квитанцию SdI.

### Быстрый старт

```bash
git clone https://github.com/sonoyumi/invoice-extract.git
cd invoice-extract
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
invoice-extract --help
```

Тесты: `pytest` (58 тестов: конверты p7m, парсер, каждая проверка, итоги, безопасность Excel/CSV, сквозные запуски).

### Структура проекта

```
src/invoice_extract/
├── loader.py    # файлы, папки и zip-архивы (лимит размера файла)
├── p7m.py       # XML из подписанного .p7m: маленький BER/DER-ридер без сторонних библиотек
├── parser.py    # FatturaPA XML -> объекты Invoice (defusedxml, любой namespace, пакеты)
├── models.py    # dataclass-ы; деньги — Decimal
├── checks.py    # partita IVA / codice fiscale, расчёт НДС, итоги, дубли
├── analysis.py  # сводка НДС, контрагенты, сроки оплат (чистые функции)
├── report.py    # Excel и CSV (защита от formula injection)
├── texts.py     # сообщения на русском и итальянском
└── cli.py       # командная строка и коды выхода
```

### Автор

**Vladyslav Shokun** ([@sonoyumi](https://github.com/sonoyumi)) — Python-разработчик: Telegram-боты, парсинг, автоматизация.

[![Telegram](https://img.shields.io/badge/Telegram-write%20me-2CA5E0?logo=telegram&logoColor=white)](https://t.me/sonoyumiii)
[![Email](https://img.shields.io/badge/Email-contact-EA4335?logo=gmail&logoColor=white)](mailto:sonoyumiii@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-profile-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/vladyslav-shokun/)

> 💼 До сих пор переносите счета в Excel вручную? Напишите мне, автоматизирую.

### Лицензия

MIT — см. [LICENSE](LICENSE).
