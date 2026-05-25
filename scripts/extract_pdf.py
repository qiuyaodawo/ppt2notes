#!/usr/bin/env python3
"""Extract a PDF into the shared intermediate JSON plus image assets.

Usage:
    python extract_pdf.py --input <file.pdf> --out-dir <work-dir> [--assets-subdir assets]

Behavior:
    - One output item per page
    - Page text becomes slide.text
    - notes is empty because PDFs do not carry speaker notes
    - Extracted images are written to <out-dir>/<assets-subdir>/slide{N}_img{M}.{ext}
    - The intermediate JSON is written to <out-dir>/intermediate.json and printed to stdout

Exit codes:
    0  success
    1  argument error
    2  missing PyMuPDF
    3  file read or parse failure
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow both direct execution and local module import.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _schema import ImageRef, Intermediate, Slide, Source  # noqa: E402


def extract(input_path: Path, out_dir: Path, assets_subdir: str = "") -> Intermediate:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(
            "Missing dependency: PyMuPDF. Install it with: pip install pymupdf",
            file=sys.stderr,
        )
        sys.exit(2)

    if not input_path.exists():
        print(f"Input file does not exist: {input_path}", file=sys.stderr)
        sys.exit(3)

    try:
        doc = fitz.open(str(input_path))
    except Exception as e:
        print(f"Failed to open PDF: {e}", file=sys.stderr)
        sys.exit(3)

    # Prepare the image output directory.
    assets_dir = out_dir / assets_subdir if assets_subdir else out_dir
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Document metadata
    meta_title = (doc.metadata or {}).get("title", "") or input_path.stem

    inter = Intermediate(
        source=Source(
            path=str(input_path.resolve()),
            format="pdf",
            title=meta_title,
            page_count=doc.page_count,
        ),
        slides=[],
    )

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        slide_no = page_index + 1

        # Text in reading order
        text = page.get_text("text").strip()

        # Heuristic title: treat the first short line as a title.
        title = ""
        if text:
            first_line = text.split("\n", 1)[0].strip()
            if 0 < len(first_line) <= 60:
                title = first_line

        # Extract images
        images: list[ImageRef] = []
        try:
            img_list = page.get_images(full=True)
        except Exception:
            img_list = []

        for img_idx, img_info in enumerate(img_list, start=1):
            xref = img_info[0]
            try:
                img_data = doc.extract_image(xref)
            except Exception:
                continue
            ext = img_data.get("ext", "png")
            blob = img_data.get("image")
            if not blob:
                continue
            width = int(img_data.get("width", 0))
            height = int(img_data.get("height", 0))

            # Skip tiny images, which are usually decorative.
            if width and height and (width < 100 or height < 100):
                continue

            img_id = f"slide{slide_no}_img{img_idx}"
            filename = f"{img_id}.{ext}"
            (assets_dir / filename).write_bytes(blob)

            # Relative path used later in the generated note.
            rel_path = (
                f"{assets_subdir}/{filename}" if assets_subdir else filename
            )

            # Estimate position based on image rectangle(s) on the page.
            try:
                page_rect = page.rect
                page_area = page_rect.width * page_rect.height
                rects = page.get_image_rects(xref)
                if rects:
                    img_area = max(rect.width * rect.height for rect in rects)
                    coverage = img_area / page_area if page_area else 0
                    if coverage > 0.7:
                        position = "full"
                    elif coverage > 0.3:
                        position = "center"
                    else:
                        position = "inset"
                else:
                    position = "inset"
            except Exception:
                position = "inset"

            images.append(
                ImageRef(
                    id=img_id,
                    path=rel_path,
                    width=width,
                    height=height,
                    position=position,
                    context_text=text[:300],  # Truncate to avoid oversized JSON
                )
            )

        inter.slides.append(
            Slide(
                index=slide_no,
                title=title,
                text=text,
                notes="",
                images=images,
            )
        )

    doc.close()
    return inter


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract a PDF into the ppt2notes intermediate JSON")
    ap.add_argument("--input", required=True, help="Input PDF path")
    ap.add_argument("--out-dir", required=True, help="Working directory for intermediate JSON and images")
    ap.add_argument(
        "--assets-subdir",
        default="",
        help="Optional subdirectory for extracted images relative to out-dir",
    )
    args = ap.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    inter = extract(input_path, out_dir, args.assets_subdir)

    # Write intermediate JSON
    json_path = out_dir / "intermediate.json"
    json_path.write_text(inter.to_json(), encoding="utf-8")

    # Also print to stdout so an agent can read it directly.
    print(inter.to_json())
    print(f"\nIntermediate JSON written to: {json_path}", file=sys.stderr)
    print(f"  Pages: {len(inter.slides)}", file=sys.stderr)
    n_imgs = sum(len(s.images) for s in inter.slides)
    print(f"  Extracted images: {n_imgs}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
