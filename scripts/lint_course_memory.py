#!/usr/bin/env python3
"""Lint ppt2notes course_memory.json files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def require_type(errors: list[str], obj: dict[str, Any], key: str, expected: type, path: str) -> None:
    if key not in obj:
        errors.append(f"Missing required field: {path}.{key}")
        return
    if not isinstance(obj[key], expected):
        errors.append(f"Expected {path}.{key} to be {expected.__name__}")


def lint_memory(path: Path) -> list[str]:
    errors: list[str] = []

    if not path.exists():
        return [f"Memory file does not exist: {path}"]
    if not path.is_file():
        return [f"Memory path is not a file: {path}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        return [f"Memory file is not valid UTF-8: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"Memory file is not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["Memory root must be a JSON object"]

    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")

    require_type(errors, data, "course", dict, "$")
    require_type(errors, data, "lectures", list, "$")
    require_type(errors, data, "terms", list, "$")
    require_type(errors, data, "symbols", list, "$")
    require_type(errors, data, "continuity", dict, "$")

    course = data.get("course")
    if isinstance(course, dict):
        for key in ("title", "language", "level", "topic_scope"):
            require_type(errors, course, key, str, "$.course")

    lectures = data.get("lectures")
    if isinstance(lectures, list):
        seen_sources: set[str] = set()
        for i, lecture in enumerate(lectures):
            if not isinstance(lecture, dict):
                errors.append(f"Expected $.lectures[{i}] to be object")
                continue
            for key in ("source_file", "note_file", "title", "summary"):
                require_type(errors, lecture, key, str, f"$.lectures[{i}]")
            require_type(errors, lecture, "key_takeaways", list, f"$.lectures[{i}]")

            source = lecture.get("source_file")
            if isinstance(source, str):
                if source in seen_sources:
                    errors.append(f"Duplicate lecture source_file: {source}")
                seen_sources.add(source)

            takeaways = lecture.get("key_takeaways")
            if isinstance(takeaways, list) and len(takeaways) > 8:
                errors.append(f"$.lectures[{i}].key_takeaways has more than 8 items")

    for list_name, required_fields in {
        "terms": ("zh", "definition"),
        "symbols": ("symbol", "meaning"),
    }.items():
        items = data.get(list_name)
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"Expected $.{list_name}[{i}] to be object")
                continue
            for key in required_fields:
                require_type(errors, item, key, str, f"$.{list_name}[{i}]")

    continuity = data.get("continuity")
    if isinstance(continuity, dict):
        require_type(errors, continuity, "last_lecture_summary", str, "$.continuity")
        require_type(errors, continuity, "open_threads", list, "$.continuity")
        require_type(errors, continuity, "avoid_repeating", list, "$.continuity")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a ppt2notes course_memory.json file")
    parser.add_argument("--memory", required=True, help="course_memory.json path")
    args = parser.parse_args()

    errors = lint_memory(Path(args.memory).expanduser().resolve())
    if errors:
        print("lint_course_memory failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("lint_course_memory passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
