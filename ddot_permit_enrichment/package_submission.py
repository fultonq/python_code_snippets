"""
Create the DDOT submission zip.

Usage (Windows PowerShell or Command Prompt):

    python package_submission.py Jane Q Doe

Produces: Jane_Q_Doe_Python.zip in this directory.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE_NAMES = {".gitignore", ".gitkeep", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def build_zip_name(first: str, middle: str, last: str) -> str:
    middle_initial = middle.strip().rstrip(".").upper()[:1] or "X"
    return f"{first.strip()}_{middle_initial}_{last.strip()}_Python.zip"


def should_include(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return False
    if path.suffix in EXCLUDE_SUFFIXES:
        return False
    if path.name == "lrs_cache.csv" or path.name == "enrichment.log":
        return False
    return True


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Usage: python package_submission.py FirstName MiddleInitial LastName")
        return 1

    zip_name = build_zip_name(argv[1], argv[2], argv[3])
    zip_path = ROOT / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            if path.resolve() == zip_path.resolve():
                continue
            if not should_include(path):
                continue
            arcname = Path(ROOT.name) / path.relative_to(ROOT)
            zf.write(path, arcname.as_posix())

    print(f"Wrote {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
