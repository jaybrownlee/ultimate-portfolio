"""Compatibility CLI shim for the renamed ultimate_portfolio package."""

from ultimate_portfolio.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
