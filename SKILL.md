---
name: ppt2notes
description: Turn a course slide deck or lecture PDF into a self-study Markdown study note written in Chinese. Use this skill when the user provides a `.ppt`, `.pptx`, or slide-style `.pdf` file AND signals intent to produce an organized written study document — including casual phrasings like "整理一下这个课件", "帮我做笔记", "复习一下这个讲义", "做一份讲义", "整理成讲义", or asking for a "readable / reorganized / topic-based" version. Trigger even when the user does not literally say "notes", "handout", or "讲义", as long as the message clearly asks for a reorganized written artifact. Do not trigger when the user only asks for help understanding the slides (e.g., "看不懂这个 PPT", "讲讲这个是什么意思") without asking for a written deliverable — answer those conversationally instead. Do not trigger when the user only provides a slide file with no instruction at all — ask what they want to do with it. Do not trigger for books, papers, non-slide documents, pure translation requests, or slide files that are clearly not learning material (pitch decks, photo albums).
---

# ppt2notes

## When to use this skill

Trigger this skill when **both** conditions hold:

1. The input is a local `.ppt`, `.pptx`, or lecture-style `.pdf`, AND
2. The user's message asks for an organized written study artifact derived from that file

Concrete examples of (2):

- Explicit requests: "做笔记", "讲义", "handout", "study notes", "review material"
- Casual but clear "produce-an-artifact" framing: "整理一下", "整理成讲义", "复习一下", "帮我消化成一份笔记"
- Topic-reorganization requests: "按主题重新整理", "重新组织一下"

Do not use this skill for:

- Books or papers in PDF form (these are not slide-style documents)
- Pure translation tasks (the user wants language conversion, not learning material)
- Simple summarization where the user explicitly wants something shorter than the slides, not a study expansion
- Requests for help **understanding** the slides without asking for a written deliverable (e.g., "看不懂这个 PPT", "讲讲这个是什么意思", "这页在说啥") — those are conversational explanations, not note-generation tasks; answer them directly instead
- Slide files that are clearly not learning material (e.g., a product pitch deck, a wedding photo album exported as `.pptx`) — in those cases the slide-by-slide structure is the point
- A bare slide file with no message or instruction — ask the user what they want before assuming this skill applies, since a slide file alone could be heading toward many different tasks (extract text, translate, summarize, redesign, …)

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

These come up often enough to call out explicitly, with the reason for each so you can judge edge cases instead of just memorizing rules.

- **Do not dump slide text page by page.** The value of this skill is *reorganization* — a student who wanted the raw slides could just open the file. Page-by-page output pushes the learning burden back onto the reader.
- **Do not pad with unrelated knowledge to make the output longer.** Length is a side effect of explaining the source material well, never a goal. Padding dilutes the parts that actually help.
- **Do not invent claims, data, citations, or references not grounded in the source or in standard domain knowledge.** Students will trust the note; fabrication damages that trust and produces wrong learning.
- **Do not keep decorative images.** They cost the reader attention without teaching anything. See `references/image_judgment.md` for the keep/drop rubric.
- **Do not skip `## 复习要点` or `## 思考题`.** These two sections are what turn a passive read into active recall, which is the whole point of producing a "note" rather than a "summary".
- **Do not skip workflow steps because the task feels long.** Each step exists to prevent a specific failure mode (e.g., skipping the chapter plan leads to slide-order drift). If a step truly does not apply, say so explicitly rather than silently dropping it.
