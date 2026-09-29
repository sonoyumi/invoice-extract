"""Точка входа: `python -m invoice_extract` или команда `invoice-extract`."""


def greet(name: str) -> str:
    return f"Привет, {name}!"


def main() -> None:
    print(greet("мир"))


if __name__ == "__main__":
    main()
