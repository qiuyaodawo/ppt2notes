#!/usr/bin/env python3
"""Build per-chapter drafting contexts from ppt2notes planning artifacts.

The script does not call an LLM. It turns chapter_plan.json plus extracted
materials into explicit chapter packages so deep_explanation_targets are part
of the drafting input instead of remaining passive metadata.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REVIEW_HEADINGS = {"复习要点", "思考题"}


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_title(title: str) -> str:
    title = re.sub(r"^\s*\d+(?:\.\d+)*[.)、]?\s*", "", title)
    return re.sub(r"\s+", " ", title).strip().casefold()


def load_slides(intermediate_paths: list[Path]) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for path in intermediate_paths:
        data = load_json(path)
        source = data.get("source", {})
        for slide in data.get("slides", []):
            if not isinstance(slide, dict) or not isinstance(slide.get("index"), int):
                continue
            item = dict(slide)
            item["source_path"] = source.get("path", "")
            slides.append(item)
    return slides


def load_image_decisions(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    data = load_json(path)
    decisions = data.get("decisions") if isinstance(data, dict) else data
    return [item for item in decisions if isinstance(item, dict)]


def kept_images_for_slides(
    source_material: list[dict[str, Any]],
    image_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    slide_image_ids = {
        str(image.get("id", ""))
        for slide in source_material
        for image in slide.get("images", [])
        if isinstance(image, dict)
    }
    kept = []
    for decision in image_decisions:
        if decision.get("decision") != "keep":
            continue
        image_id = str(decision.get("id", ""))
        if slide_image_ids and image_id not in slide_image_ids:
            continue
        kept.append(
            {
                "id": image_id,
                "path": decision.get("note_path") or decision.get("path") or "",
                "role": decision.get("role", ""),
                "brief": decision.get("brief", ""),
            }
        )
    return kept


def normalized_source(value: Any) -> str:
    return str(value or "").replace("\\", "/").casefold()


def source_matches(reference: Any, source_path: Any) -> bool:
    ref = normalized_source(reference)
    source = normalized_source(source_path)
    if not ref or not source:
        return False
    ref_name = Path(ref).name
    source_name = Path(source).name
    return ref == source or source.endswith(f"/{ref}") or ref_name == source_name


def slide_material(slide: dict[str, Any]) -> dict[str, Any]:
    return {
        "slide_index": slide.get("index"),
        "title": slide.get("title", ""),
        "text": slide.get("text", ""),
        "notes": slide.get("notes", ""),
        "images": slide.get("images", []),
        "source_path": slide.get("source_path", ""),
    }


def append_unique_slide(
    source_material: list[dict[str, Any]],
    seen: set[tuple[str, int]],
    slide: dict[str, Any],
) -> None:
    index = slide.get("index")
    if not isinstance(index, int):
        return
    key = (normalized_source(slide.get("source_path")), index)
    if key in seen:
        return
    seen.add(key)
    source_material.append(slide_material(slide))


def ref_indices(ref: dict[str, Any]) -> list[int]:
    raw = ref.get("slide_indices") or ref.get("slides") or []
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, int)]
    index = ref.get("slide_index") or ref.get("index")
    return [index] if isinstance(index, int) else []


def chapter_source_material(chapter: dict[str, Any], slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_refs = chapter.get("source_refs")
    if isinstance(source_refs, list):
        source_material: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for ref in source_refs:
            if not isinstance(ref, dict):
                continue
            source_ref = ref.get("source_path") or ref.get("relative_path") or ref.get("path")
            indices = set(ref_indices(ref))
            for slide in slides:
                if indices and slide.get("index") not in indices:
                    continue
                if source_matches(source_ref, slide.get("source_path")):
                    append_unique_slide(source_material, seen, slide)
        return source_material

    slide_refs = chapter.get("slide_refs")
    if isinstance(slide_refs, list):
        source_material = []
        seen = set()
        for ref in slide_refs:
            if not isinstance(ref, dict):
                continue
            source_ref = ref.get("source_path") or ref.get("relative_path") or ref.get("path")
            indices = set(ref_indices(ref))
            for slide in slides:
                if indices and slide.get("index") not in indices:
                    continue
                if source_matches(source_ref, slide.get("source_path")):
                    append_unique_slide(source_material, seen, slide)
        return source_material

    indices = chapter.get("slide_indices") or chapter.get("slides") or []
    source_material: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for index in indices:
        if not isinstance(index, int):
            continue
        for slide in slides:
            if slide.get("index") == index:
                append_unique_slide(source_material, seen, slide)
    return source_material


def normalize_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def render_source_material(source_material: list[dict[str, Any]]) -> str:
    if not source_material:
        return "- No extracted slide material was provided."
    blocks = []
    for slide in source_material:
        source_path = str(slide.get("source_path", ""))
        source_label = Path(source_path).name if source_path else ""
        blocks.append(
            "\n".join(
                [
                    f"- Source {source_label}, Slide/Page {slide.get('slide_index')}: {slide.get('title', '')}",
                    f"  Text: {slide.get('text', '')}",
                    f"  Notes: {slide.get('notes', '')}",
                ]
            )
        )
    return "\n".join(blocks)


def render_code_examples(code_examples: list[Any]) -> str:
    if not code_examples:
        return "- None."
    lines = []
    for item in code_examples:
        if isinstance(item, dict):
            path = item.get("path") or item.get("source_path") or "<unknown>"
            snippet = item.get("snippet") or item.get("sample") or item.get("text") or ""
            lines.append(f"- {path}\n  Key snippet:\n{snippet}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def render_question_prompts(prompts: list[Any]) -> str:
    if not prompts:
        return "- None."
    return "\n".join(f"- {item}" for item in prompts)


def render_kept_images(images: list[dict[str, Any]]) -> str:
    if not images:
        return "- None."
    return "\n".join(
        f"- {img.get('id')}: {img.get('path')} [{img.get('role')}] {img.get('brief')}"
        for img in images
    )


def build_draft_prompt(chapter: dict[str, Any], package: dict[str, Any]) -> str:
    targets = normalize_list(chapter.get("deep_explanation_targets"))
    target_text = "\n".join(f"- {target}" for target in targets) if targets else "- None."
    return f"""Draft this ppt2notes chapter in Chinese using the provided package.

Chapter title: {chapter.get("title", "")}
Chapter summary: {chapter.get("summary", "")}

Source material:
{render_source_material(package["source_material"])}

Deep explanation targets:
{target_text}

Mandatory depth pattern for every deep target:
- 问题: state the concrete problem this target addresses.
- 直觉: give the learner's mental model before formal details.
- 步骤/推导: show the key steps, derivation, algorithm trace, or execution timeline.
- 例子/坑: include one concrete example, comparison, common mistake, or observed runtime symptom.
- 与上下文连接: connect the target to the previous/next lecture content or surrounding chapter topic.

Code examples:
{render_code_examples(package["code_examples"])}

For each code file that appears above, quote one key snippet, explain what concept it verifies, and name one common mistake or runtime phenomenon.

Question/lab prompts:
{render_question_prompts(package["question_prompts"])}

Turn each question PDF item into at least one worked prompt, checkpoint, or final 思考题 candidate.

Kept images:
{render_kept_images(package["kept_images"])}

Embed every kept image with a nearby `> **图解(...)**` block. Use `###` subsections when this chapter is dense."""


def extract_note_chapters(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    chapters: dict[str, str] = {}
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        if title in REVIEW_HEADINGS:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters[normalize_title(title)] = text[start:end].strip()
    return chapters


def build_enhance_prompt(chapter: dict[str, Any], existing_content: str) -> str:
    targets = normalize_list(chapter.get("deep_explanation_targets"))
    target_text = "\n".join(f"- {target}" for target in targets) if targets else "- None."
    return f"""Enhance the existing Chinese ppt2notes chapter without rewriting unrelated sections.

Chapter title: {chapter.get("title", "")}

Original chapter content (原章节现有内容):
{existing_content or "(No matching chapter content found.)"}

Deep explanation targets that must be added:
{target_text}

Append one or more blocks titled `### 深入理解：...` after the existing chapter material. Each block must include the concrete problem, intuition, steps/derivation or execution trace, one example or common pitfall, and the connection to surrounding lecture content."""


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    chapter_plan = load_json(Path(args.chapter_plan))
    chapters = normalize_list(chapter_plan.get("chapters"))
    intermediate_paths = [Path(path) for path in args.intermediate]
    slides = load_slides(intermediate_paths) if intermediate_paths else {}
    image_decisions = load_image_decisions(Path(args.image_decisions)) if args.image_decisions else []
    existing_chapters = (
        extract_note_chapters(Path(args.existing_note).read_text(encoding="utf-8"))
        if args.existing_note
        else {}
    )

    payload_chapters = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        source_material = chapter_source_material(chapter, slides)
        package = {
            "title": chapter.get("title", ""),
            "summary": chapter.get("summary", ""),
            "deep_explanation_targets": normalize_list(chapter.get("deep_explanation_targets")),
            "source_material": source_material,
            "kept_images": kept_images_for_slides(source_material, image_decisions),
            "code_examples": normalize_list(chapter.get("code_examples")),
            "question_prompts": normalize_list(chapter.get("question_prompts"))
            or normalize_list(chapter.get("questions")),
        }
        if args.mode == "enhance":
            existing_content = existing_chapters.get(normalize_title(str(chapter.get("title", ""))), "")
            package["existing_content"] = existing_content
            package["prompt"] = build_enhance_prompt(chapter, existing_content)
        else:
            package["prompt"] = build_draft_prompt(chapter, package)
        payload_chapters.append(package)

    return {"schema_version": "1.0", "mode": args.mode, "chapters": payload_chapters}


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Build per-chapter ppt2notes drafting contexts")
    parser.add_argument("--chapter-plan", required=True, help="chapter_plan.json path")
    parser.add_argument(
        "--intermediate",
        action="append",
        default=[],
        help="intermediate.json path; may be passed multiple times",
    )
    parser.add_argument("--image-decisions", default="", help="Optional image_decisions.json path")
    parser.add_argument("--existing-note", default="", help="Existing note path for enhance mode")
    parser.add_argument("--mode", choices=("draft", "enhance"), default="draft")
    parser.add_argument("--out", required=True, help="Output chapter_context.json path")
    args = parser.parse_args()

    payload = build_context(args)
    write_json(Path(args.out).expanduser().resolve(), payload)
    print(f"Chapter context written to: {Path(args.out).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
