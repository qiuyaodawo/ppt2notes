#!/usr/bin/env python3
"""Lint a generated ppt2notes Markdown file for structural quality.

This is intentionally a lightweight checker. It verifies the contract that is
cheap to check deterministically, leaving content quality to human/model review.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import PurePosixPath
from pathlib import Path

ALLOWED_IMAGE_ROLES = {"chart", "formula", "diagram", "screenshot", "photo"}
ALLOWED_DECISION_ROLES = ALLOWED_IMAGE_ROLES | {"decoration"}


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


def line_number_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def chapter_headings(lines: list[str]) -> list[str]:
    headings = []
    for line in lines:
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        if title in {"复习要点", "思考题"}:
            continue
        headings.append(title)
    return headings


def markdown_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((title, text[start:end].strip()))
    return sections


def chapter_sections(text: str) -> list[tuple[str, str]]:
    return [
        (title, body)
        for title, body in markdown_sections(text)
        if title not in {"复习要点", "思考题"}
    ]


def clean_image_target(raw_target: str) -> str:
    target = raw_target.strip().split("#", 1)[0].split("?", 1)[0]
    return target.replace("\\", "/")


def matching_image_targets(targets: list[str], decision: dict) -> list[str]:
    image_id = str(decision.get("id", "")).strip()
    raw_path = str(
        decision.get("note_path")
        or decision.get("path")
        or decision.get("image_path")
        or decision.get("relative_path")
        or ""
    ).strip()
    normalized_path = raw_path.replace("\\", "/")
    basename = PurePosixPath(normalized_path).name if normalized_path else ""

    matches: list[str] = []
    for target in targets:
        target_name = PurePosixPath(target).name
        if normalized_path and (target == normalized_path or target.endswith(f"/{normalized_path}")):
            matches.append(target)
            continue
        if basename and target_name == basename:
            matches.append(target)
            continue
        if image_id and image_id in target:
            matches.append(target)
    return matches


def lint_image_decisions(
    path: Path,
    image_targets: list[str],
    image_roles: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"Image decisions file does not exist: {path}"]
    if not path.is_file():
        return [f"Image decisions path is not a file: {path}"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Image decisions JSON is invalid: {exc}"]

    decisions = payload.get("decisions") if isinstance(payload, dict) else payload
    if not isinstance(decisions, list):
        return ["Image decisions must be a list or an object with a decisions list"]

    for decision in decisions:
        if not isinstance(decision, dict):
            errors.append("Image decision entries must be objects")
            continue
        image_id = str(decision.get("id", "")).strip() or "<missing id>"
        role = str(decision.get("role", "")).strip()
        if role and role not in ALLOWED_DECISION_ROLES:
            errors.append(f"Image decision has invalid role for {image_id}: {role}")
        if decision.get("decision") != "keep":
            continue
        if not role:
            errors.append(f"Kept image decision must include a role: {image_id}")
        elif role == "decoration":
            errors.append(f"Kept image decision cannot use role decoration: {image_id}")
        elif role not in ALLOWED_IMAGE_ROLES:
            errors.append(f"Kept image decision has invalid role for {image_id}: {role}")
        if not str(decision.get("brief", "")).strip():
            errors.append(f"Kept image decision must include a non-empty brief: {image_id}")
        if not str(decision.get("note_path", "")).strip():
            errors.append(f"Kept image decision must include note_path: {image_id}")

        matching_targets = matching_image_targets(image_targets, decision)
        if not matching_targets:
            image_path = str(decision.get("note_path") or decision.get("path") or "").strip()
            detail = f"{image_id} ({image_path})" if image_path else image_id
            errors.append(f"Kept image decision is not embedded in note: {detail}")
            continue

        if role in ALLOWED_IMAGE_ROLES:
            note_roles = sorted(
                {
                    note_role
                    for target in matching_targets
                    for note_role in image_roles.get(target, [])
                }
            )
            if note_roles and role not in note_roles:
                errors.append(
                    f"Kept image role mismatch for {image_id}: decision={role}, note={','.join(note_roles)}"
                )

    return errors


def image_manifest_warnings(path: Path) -> list[str]:
    if not path.exists():
        return [f"Image manifest file does not exist: {path}"]
    if not path.is_file():
        return [f"Image manifest path is not a file: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Image manifest JSON is invalid: {exc}"]
    if isinstance(payload, dict) and payload.get("images_extracted") is False:
        return ["未进行图像评估：image_manifest.json shows images_extracted: false"]
    return []


def review_point_count(text: str) -> int:
    if "## 复习要点" not in text:
        return 0
    review_section = text.split("## 复习要点", 1)[1]
    if "## 思考题" in review_section:
        review_section = review_section.split("## 思考题", 1)[0]
    return len(re.findall(r"(?m)^\s*[-*]\s+", review_section))


def is_dense_chapter(body: str) -> bool:
    compact_len = len(re.sub(r"\s+", "", body))
    dense_hits = len(
        re.findall(r"公式|算法|推导|执行模型|状态机|证明|复杂度|轨迹|容易混淆", body)
    )
    return compact_len >= 1800 or (compact_len >= 900 and dense_hits >= 3)


def lint_note(
    path: Path,
    min_chapters: int,
    max_chapters: int,
    image_decisions: Path | None = None,
) -> list[str]:
    errors: list[str] = []

    if not path.exists():
        return [f"Note file does not exist: {path}"]
    if not path.is_file():
        return [f"Note path is not a file: {path}"]

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"Note is not valid UTF-8: {exc}"]

    lines = text.splitlines()

    h1 = [line for line in lines if line.startswith("# ") and not line.startswith("## ")]
    if len(h1) != 1:
        errors.append(f"Expected exactly one top-level '# ' heading, found {len(h1)}")

    if "## 复习要点" not in text:
        errors.append("Missing required section: ## 复习要点")
    if "## 思考题" not in text:
        errors.append("Missing required section: ## 思考题")

    chapters = chapter_headings(lines)
    if not (min_chapters <= len(chapters) <= max_chapters):
        errors.append(
            f"Expected {min_chapters}-{max_chapters} chapter headings, found {len(chapters)}"
        )

    review_points = review_point_count(text)
    if chapters and review_points != len(chapters):
        errors.append(
            f"Review point count must match chapter count: found {review_points}, expected {len(chapters)}"
        )

    malformed_prompt = re.search(r"。[ \t]*(?:[*_]+)?提示", text)
    if malformed_prompt:
        line_no = line_number_for_offset(text, malformed_prompt.start())
        errors.append(f"Malformed prompt marker on line {line_no}: put 提示 on its own line")

    for title, body in chapter_sections(text):
        if is_dense_chapter(body) and not re.search(r"(?m)^###\s+", body):
            errors.append(f"Dense chapter should use ### subsections: {title}")

    question_section = text.split("## 思考题", 1)[1] if "## 思考题" in text else ""
    questions = re.findall(r"(?m)^\d+\.\s+", question_section)
    if not (5 <= len(questions) <= 10):
        errors.append(f"Expected 5-10 numbered review questions, found {len(questions)}")

    image_refs = list(re.finditer(r"!\[[^\]]*]\(([^)]+)\)", text))
    image_targets: list[str] = []
    for match in image_refs:
        raw_target = match.group(1).strip()
        target = clean_image_target(raw_target)
        image_targets.append(target)
        image_path = (path.parent / target).resolve()
        if not image_path.exists():
            line_no = line_number_for_offset(text, match.start())
            errors.append(f"Broken image reference on line {line_no}: {raw_target}")

    image_roles: dict[str, list[str]] = {}
    for i, line in enumerate(lines):
        if not line.startswith("!["):
            continue
        target_match = re.search(r"!\[[^\]]*]\(([^)]+)\)", line)
        target = clean_image_target(target_match.group(1)) if target_match else ""
        window = lines[max(0, i - 5) : i]
        joined = "\n".join(window)
        m = re.search(r"> \*\*图解\(图 [^)]+,([a-z]+)\):\*\*", joined)
        if not m:
            errors.append(f"Image on line {i + 1} is missing a nearby 图解 block")
            continue
        role = m.group(1)
        if role not in ALLOWED_IMAGE_ROLES:
            errors.append(f"Image on line {i + 1} has invalid role: {role}")
        elif target:
            image_roles.setdefault(target, []).append(role)

    bullet_lines = [line for line in lines if line.lstrip().startswith(("- ", "* ", "• "))]
    sentence_marks = text.count("。") + text.count("？") + text.count("！")
    if bullet_lines and len(bullet_lines) > sentence_marks:
        errors.append(
            "Output appears bullet-heavy; expected narrative prose with more sentence punctuation"
        )

    if image_decisions is not None:
        errors.extend(lint_image_decisions(image_decisions, image_targets, image_roles))

    return errors


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Lint a generated ppt2notes Markdown note")
    parser.add_argument("--note", required=True, help="Generated Markdown note path")
    parser.add_argument("--min-chapters", type=int, default=1, help="Minimum chapter count")
    parser.add_argument("--max-chapters", type=int, default=8, help="Maximum chapter count")
    parser.add_argument(
        "--image-decisions",
        default="",
        help="Optional image_decisions.json path; kept images must be embedded in the note",
    )
    parser.add_argument(
        "--image-manifest",
        default="",
        help="Optional image_manifest.json path; reports when images were not extracted/evaluated",
    )
    args = parser.parse_args()

    image_decisions = (
        Path(args.image_decisions).expanduser().resolve() if args.image_decisions else None
    )
    errors = lint_note(
        Path(args.note).expanduser().resolve(),
        args.min_chapters,
        args.max_chapters,
        image_decisions,
    )
    warnings = (
        image_manifest_warnings(Path(args.image_manifest).expanduser().resolve())
        if args.image_manifest
        else []
    )
    if errors:
        print("lint_note failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}")
    print("lint_note passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
