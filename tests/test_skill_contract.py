from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def skill_text() -> str:
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


def frontmatter() -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", skill_text(), flags=re.S)
    if not match:
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_has_only_required_fields(self) -> None:
        fields = frontmatter()
        self.assertEqual(set(fields), {"name", "description"})
        self.assertEqual(fields["name"], "ppt2notes")
        self.assertTrue(fields["description"].startswith("Use when "))

    def test_trigger_description_stays_concise(self) -> None:
        description = frontmatter()["description"]
        self.assertLessEqual(len(description), 500)

    def test_openai_agent_metadata_exists(self) -> None:
        metadata = ROOT / "agents" / "openai.yaml"
        self.assertTrue(metadata.exists(), "agents/openai.yaml should exist for UI metadata")
        text = metadata.read_text(encoding="utf-8")
        self.assertIn("display_name:", text)
        self.assertIn("short_description:", text)
        self.assertIn("default_prompt:", text)
        self.assertIn("$ppt2notes", text)

    def test_image_decision_contract_names_final_note_path(self) -> None:
        text = (ROOT / "references" / "image_judgment.md").read_text(encoding="utf-8")
        self.assertIn("note_path", text)
        self.assertIn("final assets", text.lower())


if __name__ == "__main__":
    unittest.main()
