"""Entry points: `python -m invoice_extract` or the `invoice-extract` command."""

import sys

from invoice_extract.cli import main

if __name__ == "__main__":
    sys.exit(main())
