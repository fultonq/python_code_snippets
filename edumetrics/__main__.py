"""Allow `python3 -m edumetrics ...`."""

import sys

from edumetrics.cli import main

if __name__ == "__main__":
    sys.exit(main())
