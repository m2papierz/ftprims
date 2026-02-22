"""Command-line interface entry point."""

from __future__ import annotations


def main() -> None:
    """Run the ``devqubit`` CLI."""
    from ftprims.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
