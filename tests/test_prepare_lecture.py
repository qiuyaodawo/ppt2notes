from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_lecture.py"


def write_pdf(path: Path, title: str, body: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=640, height=480)
    page.insert_text((72, 72), title, fontsize=24)
    page.insert_text((72, 120), body, fontsize=13)
    doc.save(path)
    doc.close()


class PrepareLectureTests(unittest.TestCase):
    def test_directory_mode_builds_manifest_coverage_and_course_root_memory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Course"
            lecture = root / "Lec01"
            lecture.mkdir(parents=True)
            work = root / ".ppt2notes_work"

            write_pdf(lecture / "01-PartA.pdf", "Intro", "Slide material for lecture.")
            write_pdf(lecture / "Q0.1.pdf", "Question 0.1", "What does the parser accept?")
            write_pdf(lecture / "Lab01.pdf", "Lab", "Implement a scanner.")
            (lecture / "example.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input-dir",
                    str(lecture),
                    "--course-root",
                    str(root),
                    "--work-dir",
                    str(work),
                    "--no-images",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            self.assertIn("Lecture manifest written to:", result.stdout)
            manifest_path = work / "Lec01" / "lecture_manifest.json"
            coverage_path = work / "Lec01" / "coverage_report.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(coverage_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            kinds = {Path(item["source_path"]).name: item["kind"] for item in manifest["materials"]}

            self.assertEqual(manifest["memory_path"], str((root / "course_memory.json").resolve()))
            self.assertEqual(kinds["01-PartA.pdf"], "lecture_slides")
            self.assertEqual(kinds["Q0.1.pdf"], "questions")
            self.assertEqual(kinds["Lab01.pdf"], "labs")
            self.assertEqual(kinds["example.c"], "code_examples")
            self.assertEqual(len(coverage["sources"]), 4)
            self.assertTrue(all("included_in_plan" in source for source in coverage["sources"]))

    def test_memory_path_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Course"
            lecture = root / "Lec02"
            lecture.mkdir(parents=True)
            work = root / ".ppt2notes_work"
            memory = root / "shared" / "memory.json"
            write_pdf(lecture / "Part1.pdf", "Topic", "Lecture text.")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input-dir",
                    str(lecture),
                    "--course-root",
                    str(root),
                    "--memory-path",
                    str(memory),
                    "--work-dir",
                    str(work),
                    "--no-images",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            manifest = json.loads((work / "Lec02" / "lecture_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["memory_path"], str(memory.resolve()))


if __name__ == "__main__":
    unittest.main()
