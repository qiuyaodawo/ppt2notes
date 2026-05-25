---
name: ppt2notes
description: Turn a course slide deck or lecture PDF into a self-study Markdown note. Use this skill when the user provides a `.ppt`, `.pptx`, or slide-style `.pdf` file and wants study notes, a lecture handout, review material, or a reorganized learning document rather than a slide-by-slide summary.
---

# ppt2notes

## When to use this skill

Use this skill when:

- The user provides a local `.ppt`, `.pptx`, or lecture-style `.pdf`
- The user asks to turn slides into study notes, a handout, review notes, or a readable learning document
- The desired output should reorganize material by topic, not preserve slide order

Do not use this skill for:

- Books or papers in PDF form
- Pure translation tasks
- Simple summarization tasks where expansion is not wanted

## Input and output

Input:

- One local file path ending in `.ppt`, `.pptx`, or `.pdf`

Output:

- `{original_stem}_notes.md` in the same directory as the source file
- A single Markdown document in Chinese
- Image references pointing to `{original_stem}_assets/`

Writing contract:

- Write narrative study notes, not slide transcription
- Reorganize content by topic
- Expand carefully with background, derivations, examples, and common pitfalls only when they help the learner understand the original material
- Introduce important terms on first use with Chinese plus English, for example `反向传播 (Backpropagation)`
- Rewrite formulas in LaTeX
- Keep only informative images and explain them in text
- Always end with `## 复习要点` and `## 思考题`

See `references/note_style_guide.md` for style details.

## Execution modes

Choose the best path from `references/platform_fallbacks.md` based on capabilities, not brand or product name.

- **Scripted path**: The agent can run shell commands and Python locally
- **Native multimodal path**: The agent cannot run scripts but can read PDFs and images directly
- **Text-only fallback**: The agent lacks both scripting and direct visual file access; in this case it should stop and explain the limitation clearly

## Required workflow

Follow the full workflow in `references/workflow.md`. The required high-level sequence is:

1. Detect available capabilities and input format
2. Convert `.ppt` to `.pptx` when needed
3. Extract a normalized intermediate representation
4. Build a chapter plan from text and notes only
5. Judge which images are instructionally important
6. Generate chapter-based study notes
7. Add review aids, write output, and clean temporary artifacts

If the deck is large, use `references/chunking_strategy.md`.
If images matter, use `references/image_judgment.md`.

## Script entry points

For the scripted path, use the bundled scripts in `scripts/`:

```text
python scripts/extract_pptx.py --input <file.pptx> --out-dir <work-dir>
python scripts/extract_pdf.py --input <file.pdf> --out-dir <work-dir>
python scripts/convert_ppt_to_pptx.py --input <file.ppt> --output <temp-file.pptx>
```

Use `{original_stem}_assets/` as the work directory unless there is a strong reason not to.

The intermediate JSON schema is documented in `assets/intermediate_schema.json`.

## Image judgment contract

For each image, produce a decision object like:

```json
{
  "id": "slide12_img1",
  "decision": "keep",
  "role": "chart",
  "brief": "One concise Chinese explanation of what the image teaches"
}
```

Allowed `role` values:

- `chart`
- `formula`
- `diagram`
- `screenshot`
- `photo`
- `decoration`

## Error handling

- If a required parser is missing, report the exact install command and stop
- If `.ppt` conversion is required but LibreOffice is unavailable, tell the user to install LibreOffice or resave as `.pptx` or `.pdf`
- If parsing fails, forward the useful error details and stop
- If the extracted document has no usable text, explain that scanned PDFs without a text layer are not supported by this skill
- If the deck is very large, warn about runtime and continue with chunked generation

## Strict prohibitions

- Do not dump slide text page by page
- Do not add unrelated knowledge just to make the output longer
- Do not invent claims, data, or references not grounded in the source or standard domain knowledge
- Do not keep decorative images
- Do not skip `## 复习要点` or `## 思考题`
- Do not skip workflow steps just because the task is long
