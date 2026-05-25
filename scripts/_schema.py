"""Dataclasses and validation helpers for the intermediate representation.

All extract_*.py scripts emit the same JSON structure. This module defines the
Python representation and validates loaded intermediate.json files.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = "1.0"


@dataclass
class ImageRef:
    """Description of one extracted image in the intermediate JSON."""

    id: str  # for example "slide12_img1"
    path: str  # relative to the work directory, for example "slide12_img1.png"
    width: int
    height: int
    position: Literal["full", "center", "inset"] = "inset"
    context_text: str = ""  # nearby slide text used later for image judgment


@dataclass
class Slide:
    """One slide, or one PDF page when the source is a PDF."""

    index: int  # 1-based
    title: str = ""
    text: str = ""
    notes: str = ""  # speaker notes; empty for PDF input
    images: list[ImageRef] = field(default_factory=list)


@dataclass
class Source:
    path: str  # absolute source path
    format: Literal["pptx", "pdf"]
    title: str = ""  # extracted from metadata or the first page
    page_count: int = 0


@dataclass
class Intermediate:
    """The full intermediate representation."""

    schema_version: str = SCHEMA_VERSION
    source: Source = field(default_factory=lambda: Source(path="", format="pdf"))
    slides: list[Slide] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ---------- validation ----------


class SchemaError(ValueError):
    pass


def validate(data: dict[str, Any]) -> None:
    """Perform basic validation on a loaded intermediate dict."""
    if not isinstance(data, dict):
        raise SchemaError("Root object must be a dict")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError(
            f"schema_version mismatch: expected {SCHEMA_VERSION}, got {data.get('schema_version')!r}"
        )

    src = data.get("source")
    if not isinstance(src, dict):
        raise SchemaError("source must be a dict")
    if src.get("format") not in ("pptx", "pdf"):
        raise SchemaError(f"source.format must be 'pptx' or 'pdf', got {src.get('format')!r}")
    if not src.get("path"):
        raise SchemaError("source.path must not be empty")

    slides = data.get("slides")
    if not isinstance(slides, list):
        raise SchemaError("slides must be a list")
    if not slides:
        raise SchemaError("slides must not be empty (possible scanned PDF or failed extraction)")

    for i, sl in enumerate(slides):
        if not isinstance(sl, dict):
            raise SchemaError(f"slides[{i}] must be a dict")
        if "index" not in sl or not isinstance(sl["index"], int):
            raise SchemaError(f"slides[{i}].index must be an int")
        for k in ("title", "text", "notes"):
            if k in sl and not isinstance(sl[k], str):
                raise SchemaError(f"slides[{i}].{k} must be a string")
        imgs = sl.get("images", [])
        if not isinstance(imgs, list):
            raise SchemaError(f"slides[{i}].images must be a list")
        for j, img in enumerate(imgs):
            for k in ("id", "path"):
                if not img.get(k):
                    raise SchemaError(f"slides[{i}].images[{j}].{k} must not be empty")
            for k in ("width", "height"):
                if not isinstance(img.get(k), int) or img[k] < 0:
                    raise SchemaError(f"slides[{i}].images[{j}].{k} must be a non-negative int")


def load_and_validate(path: str | Path) -> dict[str, Any]:
    """Load and validate intermediate.json from disk, then return the dict."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    validate(data)
    return data
