# invoice-extract

Короткое описание: что делает проект и зачем.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # заполнить своими значениями
invoice-extract           # или: python -m invoice_extract
```

## Тесты и линтер

```bash
pytest
ruff check .
```

## Структура

```
src/invoice_extract/   код
tests/              тесты
```
