#!/usr/bin/env python3
"""Convert an old `.ppt` file to `.pptx` using LibreOffice.

Usage:
    python convert_ppt_to_pptx.py --input <file.ppt> --output <file.pptx>

Behavior:
    - Runs `soffice --headless --convert-to pptx --outdir <dir> <file.ppt>`
    - Times out after 120 seconds
    - Moves the produced `.pptx` to the requested output path

Exit codes:
    0  success
    1  argument error
    2  LibreOffice (soffice) missing or unavailable
    3  conversion failure or timeout
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 120


def find_soffice() -> str | None:
    """Find soffice on PATH, then check a few common install locations."""
    for name in ("soffice", "soffice.exe"):
        p = shutil.which(name)
        if p:
            return p

    # Common install locations
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        # macOS
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        # Linux
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def convert(input_path: Path, output_path: Path) -> None:
    soffice = find_soffice()
    if not soffice:
        print(
            "LibreOffice (soffice) was not detected.\n"
            "  Option A: install LibreOffice from https://www.libreoffice.org/download/\n"
            "  Option B: open the .ppt file in PowerPoint or LibreOffice and resave it as .pptx or .pdf.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not input_path.exists():
        print(f"Input file does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cmd = [
            soffice,
            "--headless",
            "--convert-to",
            "pptx",
            "--outdir",
            str(tmp),
            str(input_path),
        ]
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            print(
                f"LibreOffice conversion timed out after {TIMEOUT_SECONDS}s. The file may be too large or damaged.",
                file=sys.stderr,
            )
            sys.exit(3)
        except Exception as e:
            print(f"Failed to invoke LibreOffice: {e}", file=sys.stderr)
            sys.exit(3)

        if r.returncode != 0:
            print(
                f"LibreOffice conversion failed (exit {r.returncode}):\n"
                f"  stdout: {r.stdout.strip()}\n"
                f"  stderr: {r.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(3)

        # LibreOffice usually writes a same-name .pptx into the temp directory.
        produced = tmp / (input_path.stem + ".pptx")
        if not produced.exists():
            # Fall back to any .pptx in the temp output directory.
            candidates = list(tmp.glob("*.pptx"))
            if not candidates:
                print(
                    f"Conversion finished but no .pptx output file was found. Temp directory: {tmp}",
                    file=sys.stderr,
                )
                sys.exit(3)
            produced = candidates[0]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced), str(output_path))


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert a .ppt file to .pptx using LibreOffice")
    ap.add_argument("--input", required=True, help="Input .ppt path")
    ap.add_argument("--output", required=True, help="Output .pptx path")
    args = ap.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    convert(input_path, output_path)
    print(f"Converted: {input_path} -> {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
