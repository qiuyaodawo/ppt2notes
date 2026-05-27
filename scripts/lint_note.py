#!/usr/bin/env python3
"""Lint a generated ppt2notes Markdown file for structural quality.

This is intentionally a lightweight checker. It verifies the contract that is
cheap to check deterministically, leaving content quality to human/model review.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_IMAGE_ROLES = {"chart", "formula", "diagram", "screenshot", "photo"}


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


def lint_note(path: Path, min_chapters: int, max_chapters: int) -> list[str]:
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

    question_section = text.split("## 思考题", 1)[1] if "## 思考题" in text else ""
    questions = re.findall(r"(?m)^\d+\.\s+", question_section)
    if not (5 <= len(questions) <= 10):
        errors.append(f"Expected 5-10 numbered review questions, found {len(questions)}")

    image_refs = list(re.finditer(r"!\[[^\]]*]\(([^)]+)\)", text))
    for match in image_refs:
        raw_target = match.group(1).strip()
        target = raw_target.split("#", 1)[0].split("?", 1)[0]
        image_path = (path.parent / target).resolve()
        if not image_path.exists():
            line_no = line_number_for_offset(text, match.start())
            errors.append(f"Broken image reference on line {line_no}: {raw_target}")

    for i, line in enumerate(lines):
        if not line.startswith("!["):
            continue
        window = lines[max(0, i - 5) : i]
        joined = "\n".join(window)
        m = re.search(r"> \*\*图解\(图 [^)]+,([a-z]+)\):\*\*", joined)
        if not m:
            errors.append(f"Image on line {i + 1} is missing a nearby 图解 block")
            continue
        role = m.group(1)
        if role not in ALLOWED_IMAGE_ROLES:
            errors.append(f"Image on line {i + 1} has invalid role: {role}")

    bullet_lines = [line for line in lines if line.lstrip().startswith(("- ", "* ", "• "))]
    sentence_marks = text.count("。") + text.count("？") + text.count("！")
    if bullet_lines and len(bullet_lines) > sentence_marks:
        errors.append(
            "Output appears bullet-heavy; expected narrative prose with more sentence punctuation"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a generated ppt2notes Markdown note")
    parser.add_argument("--note", required=True, help="Generated Markdown note path")
    parser.add_argument("--min-chapters", type=int, default=1, help="Minimum chapter count")
    parser.add_argument("--max-chapters", type=int, default=8, help="Maximum chapter count")
    args = parser.parse_args()

    errors = lint_note(Path(args.note).expanduser().resolve(), args.min_chapters, args.max_chapters)
    if errors:
        print("lint_note failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("lint_note passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
