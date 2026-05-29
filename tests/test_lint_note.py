from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint_note.py"


def valid_note_without_images() -> str:
    return """# Lecture 讲义

## 1. Core Topic

这一章用连贯文字解释核心概念。它不是项目符号堆叠。

## 复习要点

- **第 1 章 Core Topic**: 核心概念需要结合图示理解。

## 思考题

1. **(概念)** 什么是核心概念？
2. **(应用)** 它可以用于什么场景？
3. **(辨析)** A 和 B 有什么差异？
4. **(推导)** 关键关系如何推导？
5. **(计算)** 给定条件时如何计算结果？
"""


def valid_note_with_image() -> str:
    return """# Lecture 讲义

## 1. Core Topic

这一章用连贯文字解释核心概念。它不是项目符号堆叠。下面的图展示了流程关系。

> **图解(图 1-1,diagram):** 这张图解释核心流程。

![图 1-1](lecture_assets/slide3_img1.png)

## 复习要点

- **第 1 章 Core Topic**: 核心概念需要结合图示理解。

## 思考题

1. **(概念)** 什么是核心概念？
2. **(应用)** 它可以用于什么场景？
3. **(辨析)** A 和 B 有什么差异？
4. **(推导)** 关键关系如何推导？
5. **(计算)** 给定条件时如何计算结果？
"""


class LintNoteTests(unittest.TestCase):
    def test_review_point_count_must_match_chapter_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "lecture_notes.md"
            note.write_text(
                """# Lecture 讲义

## 1. Core Topic

这一章用连贯文字解释核心概念。它不是项目符号堆叠。

## 2. Second Topic

这一章继续解释第二个概念，并保持叙述完整。

## 复习要点

- **第 1 章 Core Topic**: 核心概念需要结合图示理解。

## 思考题

1. **(概念)** 什么是核心概念？
2. **(应用)** 它可以用于什么场景？
3. **(辨析)** A 和 B 有什么差异？
4. **(推导)** 关键关系如何推导？
5. **(计算)** 给定条件时如何计算结果？
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--note", str(note)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Review point count must match chapter count", result.stderr)

    def test_malformed_hint_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "lecture_notes.md"
            note.write_text(
                valid_note_without_images().replace(
                    "什么是核心概念？", "什么是核心概念。*提示：不要把提示接在句号后*"
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--note", str(note)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Malformed prompt marker", result.stderr)

    def test_dense_chapter_requires_subsections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "lecture_notes.md"
            dense_text = "这是一个密集章节，包含公式、算法、执行模型和多个容易混淆的概念。" * 90
            note.write_text(
                f"""# Lecture 讲义

## 1. Dense Topic

{dense_text}

## 复习要点

- **第 1 章 Dense Topic**: 密集内容需要拆成小节。

## 思考题

1. **(概念)** 什么是核心概念？
2. **(应用)** 它可以用于什么场景？
3. **(辨析)** A 和 B 有什么差异？
4. **(推导)** 关键关系如何推导？
5. **(计算)** 给定条件时如何计算结果？
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--note", str(note)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Dense chapter should use ### subsections", result.stderr)

    def test_image_manifest_without_extraction_reports_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            note = tmp_path / "lecture_notes.md"
            manifest = tmp_path / "image_manifest.json"
            note.write_text(valid_note_without_images(), encoding="utf-8")
            manifest.write_text(
                json.dumps({"schema_version": "1.0", "images_extracted": False, "images": []}),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--note",
                    str(note),
                    "--image-manifest",
                    str(manifest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("未进行图像评估", result.stdout)

    def test_keep_image_decisions_must_be_embedded_in_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            note = tmp_path / "lecture_notes.md"
            decisions = tmp_path / "image_decisions.json"
            image = tmp_path / "lecture_assets" / "slide3_img1.png"
            image.parent.mkdir()
            image.write_bytes(b"fake image bytes")

            note.write_text(valid_note_without_images(), encoding="utf-8")
            decisions.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "decisions": [
                            {
                                "id": "slide3_img1",
                                "decision": "keep",
                                "role": "diagram",
                                "brief": "这张图解释核心流程。",
                                "path": "lecture_assets/slide3_img1.png",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--note",
                    str(note),
                    "--image-decisions",
                    str(decisions),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Kept image decision is not embedded", result.stderr)

    def test_embedded_keep_image_decision_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            note = tmp_path / "lecture_notes.md"
            decisions = tmp_path / "image_decisions.json"
            image = tmp_path / "lecture_assets" / "slide3_img1.png"
            image.parent.mkdir()
            image.write_bytes(b"fake image bytes")

            note.write_text(valid_note_with_image(), encoding="utf-8")
            decisions.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "decisions": [
                            {
                                "id": "slide3_img1",
                                "decision": "keep",
                                "role": "diagram",
                                "brief": "这张图解释核心流程。",
                                "path": "slide3_img1.png",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--note",
                    str(note),
                    "--image-decisions",
                    str(decisions),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("lint_note passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
