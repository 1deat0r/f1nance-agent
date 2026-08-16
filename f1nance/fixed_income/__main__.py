"""Enable ``python -m f1nance.fixed_income`` as the CLI entry point."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
