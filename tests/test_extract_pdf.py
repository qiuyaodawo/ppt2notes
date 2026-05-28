from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_pdf.py"


def write_pdf(path: Path, pages: list[tuple[str, str]]) -> None:
    doc = fitz.open()
    for title, body in pages:
        page = doc.new_page(width=640, height=480)
        page.insert_text((36, 28), "Compiler Principles - Prof. Zhang", fontsize=9)
        page.insert_text((72, 72), title, fontsize=24)
        page.insert_text((72, 122), body, fontsize=13)
        page.insert_text((310, 462), str(len(doc)), fontsize=9)
    doc.save(path)
    doc.close()


def write_png(path: Path, width: int, height: int, label: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.draw_rect(fitz.Rect(0, 0, width, height), color=(0.1, 0.2, 0.6), fill=(0.9, 0.95, 1.0))
    page.insert_text((20, min(50, height - 20)), label, fontsize=18)
    pix = page.get_pixmap(alpha=False)
    pix.save(path)
    doc.close()


class ExtractPdfTests(unittest.TestCase):
    def test_default_stdout_is_summary_not_full_json_and_handles_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "unicode.pdf"
            out = tmp_path / "work"
            write_pdf(pdf, [("Parsing", "• LR items\n• FIRST and FOLLOW\n中文项目符号")])

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(pdf), "--out-dir", str(out)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            self.assertIn("Intermediate JSON written to:", result.stdout)
            self.assertIn("Pages: 1", result.stdout)
            self.assertNotIn('"slides"', result.stdout)
            data = json.loads((out / "intermediate.json").read_text(encoding="utf-8"))
            self.assertIn("LR items", data["slides"][0]["text"])
            self.assertTrue(any(ord(ch) > 127 for ch in data["slides"][0]["text"]))

    def test_print_json_is_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "unicode.pdf"
            out = tmp_path / "work"
            write_pdf(pdf, [("Parsing", "• item with bullet\n中文 bullet")])

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(pdf),
                    "--out-dir",
                    str(out),
                    "--print-json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            data = json.loads(result.stdout)
            self.assertEqual(data["slides"][0]["title"], "Parsing")
            self.assertIn("item with bullet", data["slides"][0]["text"])
            self.assertTrue(any(ord(ch) > 127 for ch in data["slides"][0]["text"]))

    def test_titles_ignore_repeated_headers_footers_page_numbers_and_empty_bullets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "titles.pdf"
            out = tmp_path / "work"

            doc = fitz.open()
            for i, title in enumerate(["Lexical Analysis", "Top Down Parsing", "LR Parsing"], start=1):
                page = doc.new_page(width=640, height=480)
                page.insert_text((36, 28), "Compiler Principles - Prof. Zhang", fontsize=9)
                page.insert_text((72, 58), "•", fontsize=28)
                page.insert_text((72, 92), title, fontsize=24)
                page.insert_text((72, 142), f"Important content for page {i}", fontsize=13)
                page.insert_text((314, 462), str(i), fontsize=9)
            doc.save(pdf)
            doc.close()

            subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(pdf), "--out-dir", str(out), "--quiet"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            data = json.loads((out / "intermediate.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [slide["title"] for slide in data["slides"]],
                ["Lexical Analysis", "Top Down Parsing", "LR Parsing"],
            )

    def test_no_images_threshold_selected_pages_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            big = tmp_path / "big.png"
            small = tmp_path / "small.png"
            write_png(big, 420, 260, "large diagram")
            write_png(small, 120, 120, "logo")

            pdf = tmp_path / "images.pdf"
            doc = fitz.open()
            for i in range(1, 4):
                page = doc.new_page(width=640, height=480)
                page.insert_text((72, 72), f"Topic {i}", fontsize=24)
                page.insert_text((72, 120), f"Body page {i}", fontsize=13)
                if i == 2:
                    page.insert_image(fitz.Rect(80, 160, 500, 420), filename=str(big))
                    page.insert_image(fitz.Rect(510, 20, 630, 140), filename=str(small))
            doc.save(pdf)
            doc.close()

            no_img_out = tmp_path / "no_images"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(pdf),
                    "--out-dir",
                    str(no_img_out),
                    "--no-images",
                    "--quiet",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            no_img_data = json.loads((no_img_out / "intermediate.json").read_text(encoding="utf-8"))
            no_img_manifest = json.loads((no_img_out / "image_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(sum(len(slide["images"]) for slide in no_img_data["slides"]), 0)
            self.assertFalse(no_img_manifest["images_extracted"])

            filtered_out = tmp_path / "filtered"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(pdf),
                    "--out-dir",
                    str(filtered_out),
                    "--image-threshold",
                    "200",
                    "--extract-selected-pages",
                    "2-3",
                    "--quiet",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            data = json.loads((filtered_out / "intermediate.json").read_text(encoding="utf-8"))
            manifest = json.loads((filtered_out / "image_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual([slide["index"] for slide in data["slides"]], [2, 3])
            self.assertEqual(sum(len(slide["images"]) for slide in data["slides"]), 1)
            self.assertEqual(len(manifest["images"]), 2)
            self.assertEqual(
                sorted(item["decision"] for item in manifest["images"]),
                ["extracted", "skipped"],
            )


if __name__ == "__main__":
    unittest.main()
