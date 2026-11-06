"""Entry point for The Tamworth Chase.

Run with::

    .venv/bin/python main.py
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from game.app import App

    app = App()
    try:
        return app.run()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
