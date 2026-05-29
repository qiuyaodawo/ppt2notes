from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_chapter_context.py"


class BuildChapterContextTests(unittest.TestCase):
    def test_draft_context_includes_deep_targets_source_code_questions_and_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chapter_plan = tmp_path / "chapter_plan.json"
            intermediate = tmp_path / "intermediate.json"
            image_decisions = tmp_path / "image_decisions.json"
            out = tmp_path / "chapter_context.json"

            target = (
                "用错误的 CUDA reduction 写法说明为什么分支发散和共享内存访问模式会拖慢性能"
            )
            chapter_plan.write_text(
                json.dumps(
                    {
                        "chapters": [
                            {
                                "title": "1. CUDA Reduction",
                                "summary": "Explains warp execution and reduction performance.",
                                "slide_indices": [1, 2],
                                "deep_explanation_targets": [target],
                                "code_examples": [
                                    {
                                        "path": "reduction_bad.cu",
                                        "snippet": "if (tid % (2 * stride) == 0) {",
                                    }
                                ],
                                "question_prompts": [
                                    "为什么相邻线程在 reduction 中分到不同分支会降低吞吐？"
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            intermediate.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "source": {
                            "path": str(tmp_path / "cuda.pdf"),
                            "format": "pdf",
                            "title": "CUDA",
                            "page_count": 2,
                        },
                        "slides": [
                            {
                                "index": 1,
                                "title": "Warps",
                                "text": "A warp executes one instruction for 32 threads.",
                                "notes": "Discuss ready warp scheduling.",
                                "images": [],
                            },
                            {
                                "index": 2,
                                "title": "Reduction",
                                "text": "Naive reduction causes divergence and inefficient memory access.",
                                "notes": "",
                                "images": [
                                    {
                                        "id": "slide2_img1",
                                        "path": "slide2_img1.png",
                                        "width": 640,
                                        "height": 360,
                                    }
                                ],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            image_decisions.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "id": "slide2_img1",
                                "path": "lecture_assets/slide2_img1.png",
                                "decision": "keep",
                                "role": "diagram",
                                "brief": "reduction 中活跃线程随 stride 变化的示意图",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--chapter-plan",
                    str(chapter_plan),
                    "--intermediate",
                    str(intermediate),
                    "--image-decisions",
                    str(image_decisions),
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            payload = json.loads(out.read_text(encoding="utf-8"))
            chapter = payload["chapters"][0]
            prompt = chapter["prompt"]
            self.assertIn(target, prompt)
            self.assertIn("问题", prompt)
            self.assertIn("直觉", prompt)
            self.assertIn("步骤/推导", prompt)
            self.assertIn("if (tid % (2 * stride) == 0)", prompt)
            self.assertIn("为什么相邻线程", prompt)
            self.assertIn("slide2_img1", prompt)
            self.assertEqual(chapter["source_material"][0]["slide_index"], 1)

    def test_enhance_mode_builds_insert_prompt_from_existing_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chapter_plan = tmp_path / "chapter_plan.json"
            note = tmp_path / "LecMPI_notes.md"
            out = tmp_path / "enhance_context.json"

            chapter_plan.write_text(
                json.dumps(
                    {
                        "chapters": [
                            {
                                "title": "1. MPI Blocking Communication",
                                "summary": "Blocking send/recv ordering.",
                                "deep_explanation_targets": [
                                    "用两个 MPI 进程的发送/接收顺序画出阻塞通信死锁"
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            note.write_text(
                """# MPI 讲义

## 1. MPI Blocking Communication

这里简单介绍阻塞发送和接收。

## 复习要点

- **第 1 章 MPI Blocking Communication**: 注意通信顺序。

## 思考题

1. **(概念)** 什么是阻塞通信？
2. **(应用)** 如何安排发送接收？
3. **(辨析)** 阻塞和非阻塞有什么不同？
4. **(推导)** 为什么会死锁？
5. **(计算)** 给定顺序判断是否能结束？
""",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--chapter-plan",
                    str(chapter_plan),
                    "--existing-note",
                    str(note),
                    "--mode",
                    "enhance",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            payload = json.loads(out.read_text(encoding="utf-8"))
            prompt = payload["chapters"][0]["prompt"]
            self.assertIn("### 深入理解", prompt)
            self.assertIn("原章节现有内容", prompt)
            self.assertIn("阻塞发送和接收", prompt)

    def test_directory_context_disambiguates_same_page_index_by_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chapter_plan = tmp_path / "chapter_plan.json"
            part_a = tmp_path / "part_a_intermediate.json"
            part_b = tmp_path / "part_b_intermediate.json"
            out = tmp_path / "chapter_context.json"

            chapter_plan.write_text(
                json.dumps(
                    {
                        "chapters": [
                            {
                                "title": "1. Part B Topic",
                                "summary": "Use the second source page 1, not part A page 1.",
                                "source_refs": [
                                    {"source_path": "02-PartB.pdf", "slide_indices": [1]}
                                ],
                                "deep_explanation_targets": [
                                    "用 Part B 第 1 页的执行轨迹解释 collective ordering"
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            part_a.write_text(
                json.dumps(
                    {
                        "source": {"path": str(tmp_path / "01-PartA.pdf"), "page_count": 1},
                        "slides": [
                            {
                                "index": 1,
                                "title": "Part A",
                                "text": "This is part A page one and should not be selected.",
                                "notes": "",
                                "images": [],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            part_b.write_text(
                json.dumps(
                    {
                        "source": {"path": str(tmp_path / "02-PartB.pdf"), "page_count": 1},
                        "slides": [
                            {
                                "index": 1,
                                "title": "Part B",
                                "text": "This is part B page one and must be selected.",
                                "notes": "",
                                "images": [],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--chapter-plan",
                    str(chapter_plan),
                    "--intermediate",
                    str(part_a),
                    "--intermediate",
                    str(part_b),
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            payload = json.loads(out.read_text(encoding="utf-8"))
            material = payload["chapters"][0]["source_material"]
            self.assertEqual(len(material), 1)
            self.assertEqual(material[0]["title"], "Part B")
            self.assertIn("must be selected", payload["chapters"][0]["prompt"])
            self.assertIn("02-PartB.pdf", payload["chapters"][0]["prompt"])
            self.assertNotIn("should not be selected", payload["chapters"][0]["prompt"])


if __name__ == "__main__":
    unittest.main()
