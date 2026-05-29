from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint_depth.py"


def run_lint(note_text: str, chapter_plan: dict) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        note = tmp_path / "note.md"
        plan = tmp_path / "chapter_plan.json"
        note.write_text(note_text, encoding="utf-8")
        plan.write_text(json.dumps(chapter_plan, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--note",
                str(note),
                "--chapter-plan",
                str(plan),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


def run_lint_with_manifest(
    note_text: str,
    chapter_plan: dict,
    lecture_manifest: dict,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        note = tmp_path / "note.md"
        plan = tmp_path / "chapter_plan.json"
        manifest = tmp_path / "lecture_manifest.json"
        note.write_text(note_text, encoding="utf-8")
        plan.write_text(json.dumps(chapter_plan, ensure_ascii=False), encoding="utf-8")
        manifest.write_text(json.dumps(lecture_manifest, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--note",
                str(note),
                "--chapter-plan",
                str(plan),
                "--lecture-manifest",
                str(manifest),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


class LintDepthTests(unittest.TestCase):
    def test_deep_cuda_chapter_with_code_and_execution_trace_passes(self) -> None:
        target = "用错误的 CUDA reduction 写法说明为什么分支发散和共享内存访问模式会拖慢性能"
        note = f"""# CUDA 讲义

## 1. CUDA Reduction

### 深入理解：warp 调度与 reduction 性能

**问题**：CUDA reduction 的目标是让一个 block 内的线程把多个数合并成一个结果，但朴素写法会让同一个 warp 中只有一部分线程真正执行加法，吞吐下降。

**直觉**：可以把 warp 想成 32 个线程共用同一条指令流。遇到 `if` 后，分支发散会让活跃线程掩码变小；当一个 warp 等待共享内存访存时，调度器切到另一个 ready warp，这条时间线就是 latency hiding 的核心。

**步骤/推导**：第一步，stride=1 时偶数线程读取 `sdata[tid + 1]`；第二步，stride=2 时只有 4 的倍数线程继续执行；第三步，活跃线程越来越少，但每轮仍要同步和访存，所以共享内存访问模式与发散一起拖慢 reduction。

```cuda
if (tid % (2 * stride) == 0) {{
    sdata[tid] += sdata[tid + stride];
}}
```

这个 `reduction_bad.cu` 关键片段验证了 {target}：同一 warp 内相邻线程被分到不同路径，执行轨迹会经历“部分线程活跃、等待共享内存、切换到 ready warp、再回到原 warp”的过程。

**例子/易错点**：常见错误是只数加法次数，忽略被屏蔽线程仍然占用 warp 调度窗口；更好的写法会让连续线程参与连续地址访问，减少分支发散和共享内存访问冲突。

**联系**：这解释了前面 SM 和 warp scheduling 的硬件模型为什么会直接影响后面的并行规约算法设计。
"""
        result = run_lint(
            note,
            {
                "chapters": [
                    {
                        "title": "1. CUDA Reduction",
                        "source_page_count": 8,
                        "deep_explanation_targets": [target],
                        "code_examples": [{"path": "reduction_bad.cu"}],
                        "content_flags": ["execution_model", "algorithm"],
                    }
                ]
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("lint_depth passed", result.stdout)

    def test_missing_deep_target_is_reported(self) -> None:
        result = run_lint(
            """# MPI 讲义

## 1. MPI Blocking Communication

这一章介绍 MPI 的阻塞通信。阻塞发送和阻塞接收都很重要。
""",
            {
                "chapters": [
                    {
                        "title": "1. MPI Blocking Communication",
                        "deep_explanation_targets": [
                            "用两个 MPI 进程的发送/接收顺序画出阻塞通信死锁"
                        ],
                    }
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Deep target not covered", result.stderr)

    def test_broad_deep_target_is_rejected(self) -> None:
        result = run_lint(
            """# CUDA 讲义

## 1. CUDA Architecture

### 深入理解：SM 与 warp scheduling

**问题**：这里解释 SM 和 warp scheduling。
**直觉**：硬件通过切换 ready warp 隐藏延迟。
**步骤/推导**：先选择可运行 warp，再发射指令。
**例子/易错点**：不要把线程块等同于 warp。
**联系**：这会影响并行算法。
""",
            {
                "chapters": [
                    {
                        "title": "1. CUDA Architecture",
                        "deep_explanation_targets": ["理解 SM、warp scheduling 和架构演化"],
                    }
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("too broad", result.stderr)

    def test_code_examples_require_code_block_or_line_explanation(self) -> None:
        result = run_lint(
            """# CUDA 讲义

## 1. CUDA Reduction

### 深入理解：reduction

**问题**：reduction 需要合并线程结果。
**直觉**：树形归约可以减少工作量。
**步骤/推导**：每轮 stride 加倍。
**例子/易错点**：错误写法会导致分支发散。
**联系**：这连接到 warp scheduling。
""",
            {
                "chapters": [
                    {
                        "title": "1. CUDA Reduction",
                        "deep_explanation_targets": [
                            "用错误的 CUDA reduction 写法说明为什么分支发散会拖慢性能"
                        ],
                        "code_examples": [{"path": "reduction_bad.cu"}],
                    }
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code_examples", result.stderr)

    def test_each_code_example_requires_specific_coverage(self) -> None:
        result = run_lint(
            """# CUDA 讲义

## 1. CUDA Reduction

### 深入理解：reduction

**问题**：reduction 需要合并线程结果。
**直觉**：树形归约可以减少工作量。
**步骤/推导**：每轮 stride 加倍，并观察线程活跃掩码。

```cuda
// reduction_bad.cu
if (tid % (2 * stride) == 0) {
    sdata[tid] += sdata[tid + stride];
}
```

这个 `reduction_bad.cu` 关键片段验证了错误 reduction 如何造成分支发散。

**例子/易错点**：常见错误是只数加法次数，忽略被屏蔽线程仍然占用调度窗口。
**联系**：这连接到 warp scheduling。
""",
            {
                "chapters": [
                    {
                        "title": "1. CUDA Reduction",
                        "deep_explanation_targets": [
                            "用错误的 CUDA reduction 写法说明为什么分支发散会拖慢性能"
                        ],
                        "code_examples": [
                            {"path": "reduction_bad.cu"},
                            {"path": "warp_helper.cuh"},
                        ],
                    }
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("warp_helper.cuh", result.stderr)

    def test_question_material_requires_worked_prompt_or_thinking_question(self) -> None:
        result = run_lint(
            """# MPI 讲义

## 1. MPI Blocking Communication

### 深入理解：阻塞通信死锁

**问题**：两个进程都先执行阻塞发送时，可能都在等待对方接收。
**直觉**：可以把 send/recv 看成必须配对的门闩。
**步骤/推导**：第一步，P0 调用 Send；第二步，P1 也调用 Send；第三步，两边都没有进入 Recv，于是形成等待环。
**例子/易错点**：常见错误是以为小消息总能由缓冲区兜底。
**联系**：这连接到后面的集合通信顺序约束。
""",
            {
                "chapters": [
                    {
                        "title": "1. MPI Blocking Communication",
                        "deep_explanation_targets": [
                            "用两个 MPI 进程的发送/接收顺序画出阻塞通信死锁"
                        ],
                        "question_prompts": [
                            "Q0.1.pdf: 判断两个进程先 Send 后 Recv 是否会死锁"
                        ],
                    }
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("question material", result.stderr)

    def test_manifest_code_and_question_material_must_enter_chapter_plan(self) -> None:
        note = """# CUDA 讲义

## 1. CUDA Reduction

### 深入理解：reduction

**问题**：CUDA reduction 需要合并线程结果。
**直觉**：可以把 warp 想成共享指令流。
**步骤/推导**：第一步加载数据，第二步按 stride 归约，第三步写回结果。
**例子/易错点**：示例里错误写法会造成发散。
**联系**：这连接到后续并行性能分析。
"""
        result = run_lint_with_manifest(
            note,
            {
                "chapters": [
                    {
                        "title": "1. CUDA Reduction",
                        "deep_explanation_targets": [
                            "用错误的 CUDA reduction 写法说明为什么分支发散会拖慢性能"
                        ],
                    }
                ]
            },
            {
                "materials": [
                    {
                        "kind": "code_examples",
                        "relative_path": "reduction_bad.cu",
                        "sample_path": "work/code_sample.txt",
                    },
                    {
                        "kind": "questions",
                        "relative_path": "Q0.1.pdf",
                        "intermediate_path": "work/q/intermediate.json",
                    },
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Companion material missing from chapter_plan", result.stderr)
        self.assertIn("reduction_bad.cu", result.stderr)
        self.assertIn("Q0.1.pdf", result.stderr)

    def test_mpi_deadlock_execution_trace_passes(self) -> None:
        target = "用两个 MPI 进程的发送/接收顺序画出阻塞通信死锁"
        note = f"""# MPI 讲义

## 1. MPI Blocking Communication

### 深入理解：阻塞通信为什么会死锁

**问题**：阻塞通信要解决的是进程之间交换数据的同步问题，但如果两个进程都先发后收，通信顺序本身就会变成等待环。

**直觉**：可以把 `MPI_Send` 和 `MPI_Recv` 想成两个人同时递文件。如果双方都伸手递文件却没人先接，动作就卡住；只有把其中一边改成先接收，或者改用非阻塞通信，等待环才会被打断。

**步骤/执行轨迹**：第一步，P0 执行 `MPI_Send(to=P1)` 并等待 P1 匹配接收；第二步，P1 执行 `MPI_Send(to=P0)` 并等待 P0 匹配接收；第三步，P0 和 P1 都没有机会进入后面的 `MPI_Recv`，所以这条时间线画出来就是 P0->等待 P1、P1->等待 P0 的环。

**例子/易错点**：一个 worked prompt 是：给出 P0: Send(P1), Recv(P1) 和 P1: Send(P0), Recv(P0)，判断是否结束。答案思路不是背 API，而是沿着执行轨迹找第一个阻塞点；常见错误是默认系统缓冲一定存在。

**联系**：{target} 解释了为什么后面的集合通信必须让所有进程按兼容顺序进入调用，否则局部看似合理的通信会破坏全局进度。

## 复习要点

- **第 1 章 MPI Blocking Communication**: 判断阻塞通信能否完成，要沿发送/接收执行轨迹寻找等待环。

## 思考题

1. **(应用)** 给定两个进程的 Send/Recv 顺序，画出等待关系并判断是否死锁。
"""
        result = run_lint(
            note,
            {
                "chapters": [
                    {
                        "title": "1. MPI Blocking Communication",
                        "source_page_count": 6,
                        "deep_explanation_targets": [target],
                        "question_prompts": [
                            "Q0.1.pdf: 判断两个进程先 Send 后 Recv 是否会死锁"
                        ],
                        "content_flags": ["execution_model"],
                    }
                ]
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_large_source_with_tiny_chapter_is_reported(self) -> None:
        result = run_lint(
            """# MPI 讲义

## 1. Collective Communication

这一章介绍集合通信。

它还介绍一些顺序要求。

最后提醒要注意性能。
""",
            {
                "chapters": [
                    {
                        "title": "1. Collective Communication",
                        "source_page_count": 30,
                        "deep_explanation_targets": [],
                    }
                ]
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("too short", result.stderr)


if __name__ == "__main__":
    unittest.main()
