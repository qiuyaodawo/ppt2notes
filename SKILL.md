---
name: ppt2notes
description: Use when the user provides a course `.ppt`, `.pptx`, slide-style `.pdf`, or lecture folder such as `Lec01/` and asks for an organized Chinese study note, handout, review note, or topic-reorganized learning artifact. Trigger for casual requests like "整理课件", "做笔记", "整理成讲义", including one-lecture directories with multiple Part PDFs, question PDFs, labs, or code examples. Do not trigger for pure translation, books/papers, non-learning decks, bare files with no task, or conversational "explain this slide" questions without a written deliverable.
---

# ppt2notes

## When to use this skill

Trigger this skill when **both** conditions hold:

1. The input is a local `.ppt`, `.pptx`, lecture-style `.pdf`, or one lecture directory, AND
2. The user's message asks for an organized written study artifact derived from that file

Concrete examples of (2):

- Explicit requests: "做笔记", "讲义", "handout", "study notes", "review material"
- Casual but clear "produce-an-artifact" framing: "整理一下", "整理成讲义", "复习一下", "帮我消化成一份笔记"
- Topic-reorganization requests: "按主题重新整理", "重新组织一下"
- Directory-mode requests: "这个 Lec03 文件夹整理成一讲", "把这一讲多个 Part PDF 和题目一起整理"

Do not use this skill for:

- Books or papers in PDF form (these are not slide-style documents)
- Pure translation tasks (the user wants language conversion, not learning material)
- Simple summarization where the user explicitly wants something shorter than the slides, not a study expansion
- Requests for help **understanding** the slides without asking for a written deliverable (e.g., "看不懂这个 PPT", "讲讲这个是什么意思", "这页在说啥") — those are conversational explanations, not note-generation tasks; answer them directly instead
- Slide files that are clearly not learning material (e.g., a product pitch deck, a wedding photo album exported as `.pptx`) — in those cases the slide-by-slide structure is the point
- A bare slide file with no message or instruction — ask the user what they want before assuming this skill applies, since a slide file alone could be heading toward many different tasks (extract text, translate, summarize, redesign, …)

## Input and output

Input:

- Single-file mode: one local file path ending in `.ppt`, `.pptx`, or `.pdf`
- Lecture directory mode: one directory representing one lecture, usually named `LecXX`, containing multiple slide PDFs/PPTX files plus optional questions, labs, or code examples

Output:

- Single-file mode: `{original_stem}_notes.md` in the same directory as the source file
- Directory mode: `{lecture_dir_name}_notes.md` in the lecture directory unless the user asks for a different output name
- `course_memory.json`, created or updated on every successful run. In directory mode, default it to the course root, not the `LecXX` folder.
- A centralized work directory, normally `.ppt2notes_work/`, containing extraction artifacts, manifests, coverage, chapter plans, and image decisions
- A single Markdown document in Chinese
- Image-aware output by default: extract images, judge every extracted image, and embed every retained instructional image in the final note. Do not leave one `_assets` directory per source PDF unless the user explicitly wants raw extraction artifacts preserved.

Writing contract:

- Write narrative study notes, not slide transcription
- Reorganize content by topic
- Expand carefully with background, derivations, examples, and common pitfalls only when they help the learner understand the original material
- Identify important or difficult material before drafting. Treat central, repeated, later-dependent, formula-heavy, algorithmic, derivation-based, process-diagram, or easily confused topics as deep explanation targets.
- For each deep explanation target, explain the problem it addresses, the intuition, the key steps or derivation when applicable, one concrete example/comparison/pitfall, and how it connects to the surrounding lecture. Revise any chapter that only restates slide bullets for these targets.
- Introduce important terms on first use with Chinese plus English, for example `反向传播 (Backpropagation)`
- Rewrite formulas in LaTeX
- Keep every informative image unless the user explicitly disables images, and explain each kept image in text
- Always end with `## 复习要点` and `## 思考题`
- Always use course memory for continuity: read or initialize the resolved memory path before planning, use it while writing, and update it after the note passes validation

Use `assets/note_template.md` as the structural skeleton for the final Markdown. Adapt headings and chapter counts to the source, but keep its overall contract: one `#` title, `##` chapters, optional `###` subsections, `> **图解(...)**` blocks before kept images, and final review sections.

See `references/note_style_guide.md` for style details.
See `references/course_memory.md` for the required persistent memory behavior.

## Execution modes

Choose the best path from `references/platform_fallbacks.md` based on capabilities, not brand or product name.

- **Scripted path**: The agent can run shell commands and Python locally
- **Native multimodal path**: The agent cannot run scripts but can read PDFs and images directly
- **Text-only fallback**: The agent lacks both scripting and direct visual file access; in this case it should stop and explain the limitation clearly

## Required workflow

Follow the full workflow in `references/workflow.md`. The required high-level sequence is:

1. Detect available capabilities and input format, including whether the input is a lecture directory
2. Convert `.ppt` to `.pptx` when needed
3. Extract normalized intermediate representations and images into a centralized work directory unless the user explicitly disables images
4. Read or initialize course memory using `--course-root` / `--memory-path` rules
5. Build and save `chapter_plan.json` from text, notes, companion materials, and compact course memory
6. Judge images with help from `image_manifest.json` / intermediate image refs and save `image_decisions.json`
7. Generate chapter-based study notes with every `keep` image embedded
8. Add review aids, write output, validate the Markdown against `image_decisions.json`, update course memory, update `coverage_report.json`, and clean temporary artifacts

If the deck is large, use `references/chunking_strategy.md`.
Always use `references/image_judgment.md` unless the user explicitly disables images or the runtime has no visual/image-reading capability.
Always use `references/course_memory.md`.

## Script entry points

For the scripted path, use the bundled scripts in `scripts/`:

```text
python scripts/extract_pptx.py --input <file.pptx> --out-dir <work-dir> [--quiet] [--print-json]
python scripts/extract_pdf.py --input <file.pdf> --out-dir <work-dir> [--quiet] [--print-json] [--no-images] [--image-threshold 200] [--extract-selected-pages 1,3-5]
python scripts/convert_ppt_to_pptx.py --input <file.ppt> --output <temp-file.pptx>
python scripts/prepare_lecture.py --input-dir <LecXX> --course-root <course-root> --work-dir <course-root>/.ppt2notes_work [--no-images]
python scripts/lint_note.py --note <original_stem>_notes.md --min-chapters 3 --max-chapters 8 --image-decisions <work-dir>/image_decisions.json
python scripts/lint_course_memory.py --memory <resolved-course_memory.json>
```

Do not pass `--no-images` unless the user explicitly asks for no images or the runtime cannot handle image extraction.

Use `.ppt2notes_work/<source-or-lecture-name>/` as the default work directory so repeated PDF extraction does not dirty course folders. `extract_pdf.py` writes `intermediate.json` and `image_manifest.json`; by default it prints only a compact summary to avoid Windows GBK stdout crashes. Use `--print-json` only when an agent truly needs full JSON on stdout.

In directory mode, run `prepare_lecture.py` first. It sorts files by name, classifies materials as `lecture_slides`, `questions`, `code_examples`, `labs`, or `companion_material`, extracts supported slide files, and writes:

- `lecture_manifest.json`
- `coverage_report.json`
- per-source `intermediate.json`
- per-PDF `image_manifest.json`

For very short decks, run `lint_note.py` with `--min-chapters 1 --max-chapters 1`.

The intermediate JSON schema is documented in `assets/intermediate_schema.json`.

For skill maintenance, generate synthetic eval fixtures with:

```text
python scripts/generate_eval_fixtures.py --out-dir evals/fixtures
```

## Image judgment contract

For each image, produce a decision object like:

```json
{
  "id": "slide12_img1",
  "path": "slide12_img1.png",
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

Save the final decisions to `image_decisions.json` in the active work directory. This is required for auditability even when no images are kept. Every decision with `"decision": "keep"` must be embedded in the final Markdown; if a kept image cannot be embedded, fix the image path or change the decision before validation.

## Companion material contract

Directory mode treats non-primary files as companion material rather than noise:

- `lecture_slides`: primary conceptual source; chapters should be built mainly from these files
- `questions`: incorporate as worked prompts, examples, or additional `思考题`; do not solve every question unless solutions are present
- `code_examples`: quote only the relevant snippets and explain what they demonstrate
- `labs`: connect tasks to concepts and note practical steps, expected outputs, and common pitfalls
- `companion_material`: use only when it clearly supports the lecture; otherwise mention it in coverage as not included

Every source in `lecture_manifest.json` must appear in `coverage_report.json` with page/character counts and whether it was included in the chapter plan.

## Error handling

- If a required parser is missing, report the exact install command and stop
- If `.ppt` conversion is required but LibreOffice is unavailable, tell the user to install LibreOffice or resave as `.pptx` or `.pdf`
- If parsing fails, forward the useful error details and stop
- If `lint_note.py` fails on the generated Markdown, revise the note or image references and rerun the linter before reporting completion
- If `lint_course_memory.py` fails after updating `course_memory.json`, revise the memory JSON and rerun the linter before reporting completion
- **Scanned PDF with no text layer**: after extraction, if the total slide text across the whole document is under ~500 characters (and there are non-trivially many pages), the source is almost certainly a scanned PDF. Stop and explain that scanned PDFs without a text layer need OCR first, which is out of scope for this skill. Suggest the user run an OCR tool (e.g., `ocrmypdf input.pdf output.pdf`) and retry.
- **Very short deck (fewer than ~5 instructional slides)**: do not force the 3-to-8 chapter rule. Produce a single chapter that covers the whole deck, and still write `## 复习要点` and `## 思考题`. Forcing artificial chapter splits on tiny decks creates incoherent sections.
- **Mixed-language source (e.g., English slides, Chinese speaker notes)**: still produce Chinese output. Translate technical terms to Chinese on first use and keep the bilingual `中文 (English)` introduction pattern; English-original quotations may be kept inline when translation would distort meaning.
- **Deck that is clearly not learning material** (sales pitch, photo gallery, agenda-only deck): stop and explain that this skill is for lecture-style material. Offer to summarize it some other way instead.
- If the deck is very large, warn about runtime and continue with chunked generation

## Strict prohibitions

These come up often enough to call out explicitly, with the reason for each so you can judge edge cases instead of just memorizing rules.

- **Do not dump slide text page by page.** The value of this skill is *reorganization* — a student who wanted the raw slides could just open the file. Page-by-page output pushes the learning burden back onto the reader.
- **Do not pad with unrelated knowledge to make the output longer.** Length is a side effect of explaining the source material well, never a goal. Padding dilutes the parts that actually help.
- **Do not invent claims, data, citations, or references not grounded in the source or in standard domain knowledge.** Students will trust the note; fabrication damages that trust and produces wrong learning.
- **Do not keep decorative images.** They cost the reader attention without teaching anything. See `references/image_judgment.md` for the keep/drop rubric.
- **Do not omit kept instructional images from the final note.** A `keep` decision is a commitment to copy/reference the image and add a `> **图解(...)**` explanation block.
- **Do not skip `## 复习要点` or `## 思考题`.** These two sections are what turn a passive read into active recall, which is the whole point of producing a "note" rather than a "summary".
- **Do not skip workflow steps because the task feels long.** Each step exists to prevent a specific failure mode (e.g., skipping the chapter plan leads to slide-order drift). If a step truly does not apply, say so explicitly rather than silently dropping it.
