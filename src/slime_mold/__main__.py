"""Module entry point: ``python -m slime_mold ...``."""

import sys

from .protocol import main

if __name__ == "__main__":
    sys.exit(main())
