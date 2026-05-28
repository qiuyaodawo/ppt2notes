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
