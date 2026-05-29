#!/usr/bin/env python3
"""Lint ppt2notes output for deep-explanation coverage.

This checker complements lint_note.py. It uses chapter_plan.json as the source
of truth for topics that require careful explanation and fails when the final
Markdown only summarizes those topics shallowly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePath
from typing import Any


REVIEW_HEADINGS = {"复习要点", "思考题"}
GENERIC_TARGET_PREFIXES = ("理解", "掌握", "了解", "熟悉", "介绍", "概述")
CONCRETE_MARKERS = (
    "用",
    "通过",
    "给出",
    "画出",
    "推导",
    "比较",
    "解释",
    "说明",
    "时间线",
    "执行轨迹",
    "代码",
    "错误",
    "例子",
    "示例",
    "顺序",
    "计算",
    "证明",
)
STOPWORDS = {
    "为什么",
    "如何",
    "说明",
    "解释",
    "理解",
    "掌握",
    "通过",
    "一个",
    "以及",
    "和",
    "与",
    "的",
    "了",
    "用",
}
HIGH_SIGNAL_TERMS = (
    "死锁",
    "发散",
    "共享内存",
    "访存",
    "时间线",
    "执行轨迹",
    "reduction",
    "warp",
    "MPI",
    "Send",
    "Recv",
)
ELEMENT_PATTERNS = {
    "problem": (r"问题", r"目标", r"要解决", r"瓶颈", r"为什么"),
    "intuition": (r"直觉", r"可以把", r"直观", r"心智模型", r"想成"),
    "steps": (r"步骤", r"推导", r"第一步", r"第二步", r"时间线", r"执行轨迹", r"trace"),
    "example": (r"例子", r"示例", r"比如", r"常见错误", r"易错点", r"坑"),
    "connection": (r"联系", r"连接", r"承接", r"前面", r"后面", r"上下文"),
}
DENSE_FLAGS = {"formula", "algorithm", "execution_model", "dense", "derivation"}


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


def normalize_title(title: str) -> str:
    title = re.sub(r"^\s*\d+(?:\.\d+)*[.)、]?\s*", "", title)
    return re.sub(r"\s+", " ", title).strip().casefold()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_note_chapters(text: str) -> dict[str, str]:
    headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    chapters: dict[str, str] = {}
    for i, match in enumerate(headings):
        title = match.group(1).strip()
        if title in REVIEW_HEADINGS:
            continue
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        chapters[normalize_title(title)] = body
        chapters[title.strip().casefold()] = body
    return chapters


def is_broad_target(target: str) -> bool:
    clean = target.strip()
    if len(clean) <= 18:
        return True
    starts_generic = clean.startswith(GENERIC_TARGET_PREFIXES)
    concrete_count = sum(1 for marker in CONCRETE_MARKERS if marker in clean)
    has_specific_artifact = bool(re.search(r"[A-Za-z][A-Za-z0-9_+-]*|错误|死锁|时间线|代码|顺序|轨迹", clean))
    if starts_generic and concrete_count < 2:
        return True
    if concrete_count == 0 and not has_specific_artifact:
        return True
    return False


def tokens_from_target(target: str) -> list[str]:
    ascii_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}", target)
    chinese_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", target)
    split_tokens: list[str] = []
    for token in chinese_tokens:
        parts = re.split(r"[，、。；：！？和与的了在是把被及或并中]", token)
        split_tokens.extend(part for part in parts if len(part) >= 2)
    tokens = ascii_tokens + split_tokens
    deduped: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token or token in STOPWORDS:
            continue
        if token not in deduped:
            deduped.append(token)
    return deduped


def target_is_covered(target: str, body: str) -> bool:
    if target and target in body:
        return True
    tokens = tokens_from_target(target)
    if not tokens:
        return False
    required_high_signal = [
        term for term in HIGH_SIGNAL_TERMS if re.search(re.escape(term), target, flags=re.I)
    ]
    if required_high_signal and not any(
        re.search(re.escape(term), body, flags=re.I) for term in required_high_signal
    ):
        return False
    matches = 0
    for token in tokens:
        if re.search(re.escape(token), body, flags=re.IGNORECASE):
            matches += 1
    required = min(6, max(3, (len(tokens) + 1) // 2))
    return matches >= required


def count_explanation_elements(body: str) -> int:
    count = 0
    for patterns in ELEMENT_PATTERNS.values():
        if any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in patterns):
            count += 1
    return count


def paragraph_count(body: str) -> int:
    paras = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    return len(paras)


def textual_length(body: str) -> int:
    return len(re.sub(r"\s+", "", body))


def has_code_block(body: str) -> bool:
    return bool(re.search(r"```[A-Za-z0-9_+-]*\n[\s\S]+?```", body))


def code_blocks(body: str) -> list[str]:
    return re.findall(r"```[A-Za-z0-9_+-]*\n([\s\S]+?)```", body)


def item_basename(item: Any) -> str:
    if isinstance(item, dict):
        raw = item.get("path") or item.get("source_path") or item.get("relative_path") or ""
    else:
        raw = str(item)
    return PurePath(str(raw).replace("\\", "/")).name


def item_snippet(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    raw = item.get("snippet") or item.get("sample") or item.get("text") or ""
    lines = [line.strip() for line in str(raw).splitlines() if line.strip()]
    return lines[0] if lines else ""


def material_name(material: dict[str, Any]) -> str:
    raw = (
        material.get("relative_path")
        or material.get("source_path")
        or material.get("path")
        or material.get("name")
        or ""
    )
    return PurePath(str(raw).replace("\\", "/")).name


def nearby_line_level_explanation(body: str, name: str) -> bool:
    if not name:
        return False
    explanation = r"关键片段|逐行|第\s*\d+\s*行|这段代码|验证|常见错误|运行现象|输出"
    escaped = re.escape(name)
    return bool(
        re.search(rf"{escaped}[\s\S]{{0,120}}(?:{explanation})", body)
        or re.search(rf"(?:{explanation})[\s\S]{{0,120}}{escaped}", body)
    )


def uncovered_code_examples(body: str, examples: list[Any]) -> list[str]:
    if not examples:
        return []
    blocks = code_blocks(body)
    missing = []
    for item in examples:
        name = item_basename(item)
        snippet = item_snippet(item)
        name_in_code = bool(name and any(name in block for block in blocks))
        snippet_in_note = bool(snippet and snippet in body)
        explained_near_name = bool(name and name in body and nearby_line_level_explanation(body, name))
        if not (name_in_code or snippet_in_note or explained_near_name):
            missing.append(name or "<unknown>")
    return missing


def question_material_present(chapter: dict[str, Any]) -> bool:
    for key in ("question_prompts", "questions"):
        value = chapter.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def question_material_covered(body: str) -> bool:
    return bool(
        re.search(
            r"worked prompt|思考题|检查点|练习|题目|小题|判断|给定|答案思路|解题思路",
            body,
            re.I,
        )
    )


def planned_code_example_names(chapters: list[Any]) -> set[str]:
    names: set[str] = set()
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        examples = chapter.get("code_examples")
        if not isinstance(examples, list):
            continue
        for item in examples:
            name = item_basename(item)
            if name:
                names.add(name)
    return names


def planned_question_text(chapters: list[Any]) -> str:
    parts: list[str] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        for key in ("question_prompts", "questions", "question_sources"):
            items = chapter.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    parts.extend(
                        str(item.get(field, ""))
                        for field in ("path", "source_path", "relative_path", "prompt", "text")
                    )
                else:
                    parts.append(str(item))
    return "\n".join(parts)


def lint_manifest_companion_coverage(
    chapters: list[Any],
    lecture_manifest_path: Path | None,
) -> list[str]:
    if lecture_manifest_path is None:
        return []
    if not lecture_manifest_path.exists():
        return [f"Lecture manifest file does not exist: {lecture_manifest_path}"]

    manifest = load_json(lecture_manifest_path)
    materials = manifest.get("materials")
    if not isinstance(materials, list):
        return ["lecture_manifest.json must contain a materials list"]

    planned_code = planned_code_example_names(chapters)
    planned_questions = planned_question_text(chapters)
    errors: list[str] = []
    for material in materials:
        if not isinstance(material, dict):
            continue
        kind = material.get("kind")
        name = material_name(material)
        if not name:
            continue
        if kind == "code_examples" and name not in planned_code:
            errors.append(f"Companion material missing from chapter_plan code_examples: {name}")
        if kind == "questions" and name not in planned_questions:
            errors.append(f"Companion material missing from chapter_plan questions: {name}")
    return errors


def needs_trace_or_example(chapter: dict[str, Any]) -> bool:
    flags = set(chapter.get("content_flags") or chapter.get("flags") or [])
    if flags & DENSE_FLAGS:
        return True
    target_text = " ".join(str(item) for item in chapter.get("deep_explanation_targets", []))
    return bool(re.search(r"算法|执行模型|推导|公式|状态机|grammar|MPI|CUDA|warp|reduction", target_text, re.I))


def has_trace_or_example(body: str) -> bool:
    return bool(
        re.search(
            r"例子|示例|比如|执行轨迹|时间线|第一步|第二步|输入|输出|trace|case|步骤",
            body,
            re.I,
        )
    )


def source_page_count(chapter: dict[str, Any]) -> int:
    for key in ("source_page_count", "page_count"):
        value = chapter.get(key)
        if isinstance(value, int):
            return value
    indices = chapter.get("slide_indices")
    if isinstance(indices, list):
        return len(indices)
    return 0


def lint_depth(
    note_path: Path,
    chapter_plan_path: Path,
    lecture_manifest_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if not note_path.exists():
        return [f"Note file does not exist: {note_path}"]
    if not chapter_plan_path.exists():
        return [f"Chapter plan file does not exist: {chapter_plan_path}"]

    text = note_path.read_text(encoding="utf-8")
    plan = load_json(chapter_plan_path)
    note_chapters = extract_note_chapters(text)

    chapters = plan.get("chapters")
    if not isinstance(chapters, list):
        return ["chapter_plan.json must contain a chapters list"]

    errors.extend(lint_manifest_companion_coverage(chapters, lecture_manifest_path))

    for index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            errors.append(f"Chapter plan entry {index} must be an object")
            continue
        title = str(chapter.get("title", f"chapter {index}"))
        body = note_chapters.get(normalize_title(title)) or note_chapters.get(title.casefold(), "")
        if not body:
            errors.append(f"Chapter not found in note: {title}")
            continue

        targets = [str(item).strip() for item in chapter.get("deep_explanation_targets", []) if str(item).strip()]
        for target in targets:
            if is_broad_target(target):
                errors.append(f"Deep target too broad in {title}: {target}")
            if not target_is_covered(target, body):
                errors.append(f"Deep target not covered in {title}: {target}")

        if targets and count_explanation_elements(body) < 4:
            errors.append(
                f"Chapter lacks deep explanation elements in {title}: expected at least four of 问题/直觉/步骤/例子/易错点/联系"
            )

        pages = source_page_count(chapter)
        if pages >= 20 and (paragraph_count(body) <= 3 or textual_length(body) < 1200):
            errors.append(
                f"Chapter too short for source volume in {title}: {pages} source pages but only {paragraph_count(body)} paragraphs"
            )

        code_examples = chapter.get("code_examples", [])
        missing_code_examples = (
            uncovered_code_examples(body, code_examples) if isinstance(code_examples, list) else []
        )
        if missing_code_examples:
            errors.append(
                f"Chapter with code_examples lacks a key snippet or line-level explanation in {title}: {', '.join(missing_code_examples)}"
            )

        if question_material_present(chapter) and not question_material_covered(body):
            errors.append(
                f"Chapter with question material lacks a worked prompt, checkpoint, or thinking question in {title}"
            )

        if needs_trace_or_example(chapter) and not has_trace_or_example(body):
            errors.append(
                f"Dense formula/algorithm/execution-model chapter lacks an example or execution trace in {title}"
            )

    return errors


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Lint ppt2notes deep explanation coverage")
    parser.add_argument("--note", required=True, help="Generated Markdown note path")
    parser.add_argument("--chapter-plan", required=True, help="chapter_plan.json path")
    parser.add_argument(
        "--lecture-manifest",
        default="",
        help="Optional lecture_manifest.json path; verifies code/question materials enter chapter_plan.json",
    )
    args = parser.parse_args()

    errors = lint_depth(
        Path(args.note).expanduser().resolve(),
        Path(args.chapter_plan).expanduser().resolve(),
        Path(args.lecture_manifest).expanduser().resolve() if args.lecture_manifest else None,
    )
    if errors:
        print("lint_depth failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("lint_depth passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
