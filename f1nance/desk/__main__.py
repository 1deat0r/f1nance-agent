"""Enable ``python -m f1nance.desk`` as the CLI entry point."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
