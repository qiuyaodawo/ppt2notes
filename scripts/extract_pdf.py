#!/usr/bin/env python3
"""Extract a PDF into the shared intermediate JSON plus image assets.

Usage:
    python extract_pdf.py --input <file.pdf> --out-dir <work-dir> [--assets-subdir assets]
        [--quiet] [--print-json] [--no-images] [--image-threshold N]
        [--extract-selected-pages 1,3-5]

Behavior:
    - One output item per page
    - Page text becomes slide.text
    - notes is empty because PDFs do not carry speaker notes
    - Extracted images are written to <out-dir>/<assets-subdir>/slide{N}_img{M}.{ext}
    - The intermediate JSON is written to <out-dir>/intermediate.json
    - A compact extraction summary is printed to stdout by default
    - Full JSON is printed only when --print-json is passed

Exit codes:
    0  success
    1  argument error
    2  missing PyMuPDF
    3  file read or parse failure
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Allow both direct execution and local module import.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _schema import ImageRef, Intermediate, Slide, Source  # noqa: E402

BULLET_ONLY_RE = re.compile(r"^[\s\-–—•·●◦▪▫■□*]+$")
PAGE_NUMBER_RE = re.compile(
    r"^(?:page\s*)?\d+(?:\s*/\s*\d+)?$|^[-–—]\s*\d+\s*[-–—]$",
    re.IGNORECASE,
)
NOISE_WORDS = (
    "prof.",
    "professor",
    "instructor",
    "lecturer",
    "teacher",
    "copyright",
    "all rights reserved",
    "授课",
    "讲师",
    "教师",
)


def configure_utf8_stdio() -> None:
    """Avoid Windows GBK console crashes when output contains Unicode bullets."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_page_selection(spec: str | None, page_count: int) -> list[int]:
    """Return 0-based page indexes from a 1-based selection like '1,3-5'."""
    if not spec:
        return list(range(page_count))

    selected: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            raw_start, raw_end = part.split("-", 1)
            start = int(raw_start.strip())
            end = int(raw_end.strip())
            if start > end:
                raise ValueError(f"Invalid page range: {part}")
            numbers = range(start, end + 1)
        else:
            numbers = [int(part)]

        for page_no in numbers:
            if page_no < 1 or page_no > page_count:
                raise ValueError(
                    f"Page {page_no} is outside the document range 1-{page_count}"
                )
            selected.add(page_no - 1)

    if not selected:
        raise ValueError("Page selection did not include any pages")
    return sorted(selected)


def page_text_lines(page) -> list[dict[str, object]]:
    """Extract line-level text with font-size and position metadata."""
    try:
        data = page.get_text("dict")
    except Exception:
        return []

    lines: list[dict[str, object]] = []
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = normalize_line("".join(str(span.get("text", "")) for span in spans))
            if not text:
                continue
            sizes = [
                float(span.get("size", 0) or 0)
                for span in spans
                if str(span.get("text", "")).strip()
            ]
            bbox = line.get("bbox") or (0, 0, 0, 0)
            lines.append(
                {
                    "text": text,
                    "size": max(sizes) if sizes else 0.0,
                    "bbox": tuple(float(v) for v in bbox),
                }
            )
    return lines


def find_repeated_noise_lines(doc, page_indexes: list[int]) -> set[str]:
    """Find repeated headers/footers, which are poor per-page titles."""
    if len(page_indexes) < 2:
        return set()

    counts: Counter[str] = Counter()
    for page_index in page_indexes:
        page = doc.load_page(page_index)
        page_height = float(page.rect.height or 0)
        seen_on_page: set[str] = set()
        for line in page_text_lines(page):
            text = str(line["text"])
            y0 = float(line["bbox"][1])
            if y0 > page_height * 0.2 and y0 < page_height * 0.8:
                continue
            norm = normalize_line(text).casefold()
            if norm:
                seen_on_page.add(norm)
        counts.update(seen_on_page)

    threshold = max(2, (len(page_indexes) + 1) // 2)
    return {line for line, count in counts.items() if count >= threshold}


def is_title_noise(text: str, bbox: tuple[float, float, float, float], page_height: float, repeated: set[str]) -> bool:
    stripped = normalize_line(text)
    folded = stripped.casefold()
    if not stripped or len(stripped) < 2:
        return True
    if BULLET_ONLY_RE.fullmatch(stripped):
        return True
    if PAGE_NUMBER_RE.fullmatch(stripped):
        return True
    if folded in repeated:
        return True
    if "@" in stripped or "http://" in folded or "https://" in folded:
        return True
    if any(word in folded for word in NOISE_WORDS):
        return True
    if bbox[1] > page_height * 0.82:
        return True
    return False


def title_from_page(page, fallback_text: str, repeated_lines: set[str]) -> str:
    """Prefer prominent PyMuPDF text spans over the first extracted text line."""
    page_height = float(page.rect.height or 0)
    lines = []
    for line in page_text_lines(page):
        text = str(line["text"])
        bbox = line["bbox"]  # type: ignore[assignment]
        if is_title_noise(text, bbox, page_height, repeated_lines):
            continue
        if len(text) > 100:
            continue
        lines.append(line)

    if lines:
        max_size = max(float(line["size"]) for line in lines)
        prominent = [
            line
            for line in lines
            if float(line["size"]) >= max(1.0, max_size * 0.85)
            and float(line["bbox"][1]) <= page_height * 0.55
        ]
        candidates = prominent or lines
        candidates.sort(key=lambda line: (-float(line["size"]), float(line["bbox"][1])))
        return str(candidates[0]["text"]).strip()

    for raw_line in fallback_text.splitlines():
        line = normalize_line(raw_line)
        if 0 < len(line) <= 60 and not BULLET_ONLY_RE.fullmatch(line):
            return line
    return ""


def image_position_and_coverage(page, xref: int) -> tuple[str, float]:
    try:
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        rects = page.get_image_rects(xref)
        if not rects:
            return "inset", 0.0
        img_area = max(rect.width * rect.height for rect in rects)
        coverage = img_area / page_area if page_area else 0.0
        if coverage > 0.7:
            return "full", coverage
        if coverage > 0.3:
            return "center", coverage
        return "inset", coverage
    except Exception:
        return "inset", 0.0


def extract(
    input_path: Path,
    out_dir: Path,
    assets_subdir: str = "",
    *,
    extract_images: bool = True,
    image_threshold: int = 100,
    selected_pages: list[int] | None = None,
    image_manifest: list[dict[str, object]] | None = None,
) -> Intermediate:
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
    if extract_images:
        assets_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

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

    page_indexes = selected_pages if selected_pages is not None else list(range(doc.page_count))
    repeated_lines = find_repeated_noise_lines(doc, page_indexes)

    for page_index in page_indexes:
        page = doc.load_page(page_index)
        slide_no = page_index + 1

        # Text in reading order
        text = page.get_text("text").strip()

        title = title_from_page(page, text, repeated_lines) if text else ""

        # Extract images
        images: list[ImageRef] = []
        img_list = []
        if extract_images:
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
            position, coverage = image_position_and_coverage(page, xref)

            img_id = f"slide{slide_no}_img{img_idx}"
            manifest_item = {
                "id": img_id,
                "page": slide_no,
                "width": width,
                "height": height,
                "position": position,
                "coverage": round(float(coverage), 4),
                "path": "",
                "decision": "skipped",
                "reason": "",
            }

            # Skip tiny images, which are usually decorative.
            if image_threshold > 0 and width and height and (
                width < image_threshold or height < image_threshold
            ):
                manifest_item["reason"] = "below_threshold"
                if image_manifest is not None:
                    image_manifest.append(manifest_item)
                continue

            filename = f"{img_id}.{ext}"
            (assets_dir / filename).write_bytes(blob)

            # Relative path used later in the generated note.
            rel_path = (
                f"{assets_subdir}/{filename}" if assets_subdir else filename
            )

            manifest_item["path"] = rel_path
            manifest_item["decision"] = "extracted"
            manifest_item["reason"] = "meets_threshold"
            if image_manifest is not None:
                image_manifest.append(manifest_item)

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


def image_manifest_payload(
    input_path: Path,
    extract_images: bool,
    image_threshold: int,
    selected_pages: list[int],
    images: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "source_path": str(input_path.resolve()),
        "images_extracted": extract_images,
        "image_threshold": image_threshold,
        "selected_pages": [page + 1 for page in selected_pages],
        "images": images,
    }


def print_summary(
    inter: Intermediate,
    json_path: Path,
    image_manifest_path: Path,
    *,
    stream,
) -> None:
    n_imgs = sum(len(s.images) for s in inter.slides)
    print(f"Intermediate JSON written to: {json_path}", file=stream)
    print(f"Pages: {len(inter.slides)}", file=stream)
    print(f"Extracted images: {n_imgs}", file=stream)
    print(f"Image manifest written to: {image_manifest_path}", file=stream)


def main() -> int:
    configure_utf8_stdio()
    ap = argparse.ArgumentParser(description="Extract a PDF into the ppt2notes intermediate JSON")
    ap.add_argument("--input", required=True, help="Input PDF path")
    ap.add_argument("--out-dir", required=True, help="Working directory for intermediate JSON and images")
    ap.add_argument(
        "--assets-subdir",
        default="",
        help="Optional subdirectory for extracted images relative to out-dir",
    )
    ap.add_argument("--quiet", action="store_true", help="Suppress the default summary output")
    ap.add_argument(
        "--print-json",
        action="store_true",
        help="Print the full intermediate JSON to stdout. By default only a summary is printed.",
    )
    ap.add_argument("--no-images", action="store_true", help="Do not extract PDF images")
    ap.add_argument(
        "--image-threshold",
        type=int,
        default=100,
        help="Minimum image width and height in pixels to extract; use 0 to disable",
    )
    ap.add_argument(
        "--extract-selected-pages",
        default="",
        help="Optional 1-based page selection such as '1,3-5'",
    )
    args = ap.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import fitz  # noqa: F401
    except ImportError:
        print(
            "Missing dependency: PyMuPDF. Install it with: pip install pymupdf",
            file=sys.stderr,
        )
        return 2

    try:
        doc = fitz.open(str(input_path))
        selected_pages = parse_page_selection(args.extract_selected_pages, doc.page_count)
        doc.close()
    except ValueError as exc:
        print(f"Invalid --extract-selected-pages value: {exc}", file=sys.stderr)
        return 1
    except Exception:
        selected_pages = None

    manifest_images: list[dict[str, object]] = []
    inter = extract(
        input_path,
        out_dir,
        args.assets_subdir,
        extract_images=not args.no_images,
        image_threshold=args.image_threshold,
        selected_pages=selected_pages,
        image_manifest=manifest_images,
    )

    # Write intermediate JSON
    json_path = out_dir / "intermediate.json"
    json_path.write_text(inter.to_json(), encoding="utf-8")
    selected_for_manifest = selected_pages if selected_pages is not None else list(range(inter.source.page_count))
    manifest_path = out_dir / "image_manifest.json"
    manifest_path.write_text(
        json.dumps(
            image_manifest_payload(
                input_path,
                not args.no_images,
                args.image_threshold,
                selected_for_manifest,
                manifest_images,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.print_json:
        print(inter.to_json())
        if not args.quiet:
            print_summary(inter, json_path, manifest_path, stream=sys.stderr)
    elif not args.quiet:
        print_summary(inter, json_path, manifest_path, stream=sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
