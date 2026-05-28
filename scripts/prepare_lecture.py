#!/usr/bin/env python3
"""Prepare a lecture directory for ppt2notes directory mode.

The script scans one lecture folder, classifies companion materials, extracts
supported slide/PDF inputs into a centralized work directory, and writes a
manifest plus coverage report that the skill can use for chapter planning.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import extract_pdf  # noqa: E402
import extract_pptx  # noqa: E402

SLIDE_EXTS = {".pdf", ".pptx", ".ppt"}
CODE_EXTS = {
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".hpp",
    ".py",
    ".java",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".sql",
}


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem)
    return stem.strip("._") or "material"


def classify_material(path: Path) -> str:
    name = path.stem.casefold()
    suffix = path.suffix.casefold()
    if suffix in CODE_EXTS:
        return "code_examples"
    if re.search(r"(^|[^a-z0-9])q\d|question|exercise|quiz|习题|题目|练习", name):
        return "questions"
    if re.search(r"lab|实验|assignment|作业|practical", name):
        return "labs"
    if suffix in SLIDE_EXTS:
        return "lecture_slides"
    return "companion_material"


def material_format(path: Path) -> str:
    suffix = path.suffix.casefold().lstrip(".")
    return suffix or "unknown"


def scan_materials(input_dir: Path) -> list[Path]:
    files = [
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and (path.suffix.casefold() in SLIDE_EXTS or path.suffix.casefold() in CODE_EXTS)
    ]
    return sorted(files, key=natural_key)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text_sample(path: Path, limit: int = 4000) -> tuple[str, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gbk", errors="replace")
    return text[:limit], len(text)


def extract_pdf_material(
    path: Path,
    work_dir: Path,
    *,
    no_images: bool,
    image_threshold: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    image_items: list[dict[str, object]] = []
    inter = extract_pdf.extract(
        path,
        work_dir,
        extract_images=not no_images,
        image_threshold=image_threshold,
        image_manifest=image_items,
    )
    intermediate_path = work_dir / "intermediate.json"
    image_manifest_path = work_dir / "image_manifest.json"
    intermediate_path.write_text(inter.to_json(), encoding="utf-8")
    write_json(
        image_manifest_path,
        extract_pdf.image_manifest_payload(
            path,
            not no_images,
            image_threshold,
            list(range(inter.source.page_count)),
            image_items,
        ),
    )
    char_count = sum(len(slide.text) + len(slide.notes) for slide in inter.slides)
    material_extra = {
        "intermediate_path": str(intermediate_path.resolve()),
        "image_manifest_path": str(image_manifest_path.resolve()),
    }
    coverage_extra = {
        "page_count": inter.source.page_count,
        "char_count": char_count,
        "intermediate_path": str(intermediate_path.resolve()),
        "image_count": sum(len(slide.images) for slide in inter.slides),
    }
    return material_extra, coverage_extra


def extract_pptx_material(path: Path, work_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    inter = extract_pptx.extract(path, work_dir)
    intermediate_path = work_dir / "intermediate.json"
    intermediate_path.write_text(inter.to_json(), encoding="utf-8")
    char_count = sum(len(slide.text) + len(slide.notes) for slide in inter.slides)
    material_extra = {"intermediate_path": str(intermediate_path.resolve())}
    coverage_extra = {
        "page_count": inter.source.page_count,
        "char_count": char_count,
        "intermediate_path": str(intermediate_path.resolve()),
        "image_count": sum(len(slide.images) for slide in inter.slides),
    }
    return material_extra, coverage_extra


def prepare(args: argparse.Namespace) -> tuple[Path, Path]:
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist or is not a directory: {input_dir}")

    course_root = (
        Path(args.course_root).expanduser().resolve()
        if args.course_root
        else input_dir.parent
    )
    memory_path = (
        Path(args.memory_path).expanduser().resolve()
        if args.memory_path
        else course_root / "course_memory.json"
    )
    base_work_dir = (
        Path(args.work_dir).expanduser().resolve()
        if args.work_dir
        else course_root / ".ppt2notes_work"
    )
    lecture_work_dir = base_work_dir / input_dir.name
    lecture_work_dir.mkdir(parents=True, exist_ok=True)

    materials: list[dict[str, Any]] = []
    coverage_sources: list[dict[str, Any]] = []

    for order, path in enumerate(scan_materials(input_dir), start=1):
        kind = classify_material(path)
        fmt = material_format(path)
        material_work_dir = lecture_work_dir / f"{order:02d}_{safe_stem(path)}"
        material_work_dir.mkdir(parents=True, exist_ok=True)

        material: dict[str, Any] = {
            "order": order,
            "source_path": str(path.resolve()),
            "relative_path": str(path.relative_to(input_dir)),
            "kind": kind,
            "format": fmt,
            "work_dir": str(material_work_dir.resolve()),
        }
        coverage: dict[str, Any] = {
            "order": order,
            "source_path": str(path.resolve()),
            "relative_path": str(path.relative_to(input_dir)),
            "kind": kind,
            "format": fmt,
            "included_in_plan": False,
            "planned_chapters": [],
        }

        if path.suffix.casefold() == ".pdf":
            material_extra, coverage_extra = extract_pdf_material(
                path,
                material_work_dir,
                no_images=args.no_images,
                image_threshold=args.image_threshold,
            )
            material.update(material_extra)
            coverage.update(coverage_extra)
        elif path.suffix.casefold() == ".pptx":
            material_extra, coverage_extra = extract_pptx_material(path, material_work_dir)
            material.update(material_extra)
            coverage.update(coverage_extra)
        elif path.suffix.casefold() == ".ppt":
            material["requires_conversion"] = True
            coverage.update({"page_count": 0, "char_count": 0, "image_count": 0})
        elif path.suffix.casefold() in CODE_EXTS:
            sample, char_count = read_text_sample(path)
            sample_path = material_work_dir / "code_sample.txt"
            sample_path.write_text(sample, encoding="utf-8")
            material["sample_path"] = str(sample_path.resolve())
            coverage.update({"page_count": 0, "char_count": char_count, "image_count": 0})
        else:
            coverage.update({"page_count": 0, "char_count": 0, "image_count": 0})

        materials.append(material)
        coverage_sources.append(coverage)

    manifest_path = lecture_work_dir / "lecture_manifest.json"
    coverage_path = lecture_work_dir / "coverage_report.json"

    manifest = {
        "schema_version": "1.0",
        "lecture_dir": str(input_dir),
        "course_root": str(course_root),
        "work_dir": str(lecture_work_dir.resolve()),
        "memory_path": str(memory_path),
        "coverage_report_path": str(coverage_path.resolve()),
        "materials": materials,
        "companion_types": [
            "lecture_slides",
            "questions",
            "code_examples",
            "labs",
            "companion_material",
        ],
    }
    coverage_report = {
        "schema_version": "1.0",
        "lecture_dir": str(input_dir),
        "sources": coverage_sources,
        "totals": {
            "source_count": len(coverage_sources),
            "page_count": sum(int(source.get("page_count", 0)) for source in coverage_sources),
            "char_count": sum(int(source.get("char_count", 0)) for source in coverage_sources),
            "image_count": sum(int(source.get("image_count", 0)) for source in coverage_sources),
        },
    }

    write_json(manifest_path, manifest)
    write_json(coverage_path, coverage_report)
    return manifest_path, coverage_path


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Prepare a ppt2notes lecture directory")
    parser.add_argument("--input-dir", required=True, help="Lecture directory to scan")
    parser.add_argument(
        "--course-root",
        default="",
        help="Course root for shared course_memory.json; defaults to input-dir parent",
    )
    parser.add_argument(
        "--memory-path",
        default="",
        help="Explicit course memory path; overrides --course-root default",
    )
    parser.add_argument(
        "--work-dir",
        default="",
        help="Centralized work directory; defaults to <course-root>/.ppt2notes_work",
    )
    parser.add_argument("--no-images", action="store_true", help="Do not extract images from PDFs")
    parser.add_argument(
        "--image-threshold",
        type=int,
        default=100,
        help="Minimum PDF image width and height in pixels to extract",
    )
    args = parser.parse_args()

    manifest_path, coverage_path = prepare(args)
    print(f"Lecture manifest written to: {manifest_path}")
    print(f"Coverage report written to: {coverage_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
