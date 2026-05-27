# Workflow

This file expands the required workflow from `SKILL.md`. Use it when the skill has already triggered.

## Step 0 - Detect capabilities

Goal: determine the safest viable execution path before doing any work.

**Why this step exists:** Different agent runtimes have very different powers — local shell, sandboxed Python, multimodal-only, or text-only. Picking the wrong path leads to silent failures (e.g., generating a note that references images that were never extracted). One short capability probe at the top removes a whole class of confusion.

### Scripted path checks

Check only the dependencies required by the actual input format.

```bash
# Generic shell examples
python --version
python -c "import fitz; print('pymupdf_ok')"      # for .pdf only
python -c "import pptx; print('python_pptx_ok')"  # for .pptx only
soffice --version                                 # for .ppt only
```

### Decision table

| Input format | Required capability | If missing |
|---|---|---|
| `.pdf` | Python + PyMuPDF (`fitz`) | Tell the user to install `pymupdf`, then stop |
| `.pptx` | Python + `python-pptx` | Tell the user to install `python-pptx`, then stop |
| `.ppt` | `.pptx` requirements + LibreOffice (`soffice`) | Tell the user to install LibreOffice or resave as `.pptx` / `.pdf`, then stop |

If the agent cannot run shell commands or Python, see `platform_fallbacks.md`.

## Step 1 - Detect input format

**Why this step exists:** The three input formats need different toolchains, and `.ppt` (old binary format) cannot be parsed by `python-pptx` directly — it needs LibreOffice to convert it first. Branching by extension up front is cleaner than letting downstream code blow up on an unsupported file.

```python
ext = Path(input_file).suffix.lower()
if ext == ".ppt":
    converted = run("python scripts/convert_ppt_to_pptx.py --input <file> --output <tmp.pptx>")
    process_as_pptx(converted)
elif ext == ".pptx":
    process_as_pptx(input_file)
elif ext == ".pdf":
    process_as_pdf(input_file)
else:
    abort("Unsupported format")
```

## Step 2 - Extract the intermediate JSON

**Why this step exists:** Separating extraction from generation gives a stable, inspectable artifact between the two stages. If something looks wrong in the final note, you can re-check `intermediate.json` to tell whether the bug was in extraction or in the writing stage. It also makes the rest of the pipeline format-agnostic.

### Working directory convention

Given `/path/to/lecture01.pptx`:

- Work directory: `/path/to/lecture01_assets/`
- Intermediate JSON: `/path/to/lecture01_assets/intermediate.json`
- Extracted images: `/path/to/lecture01_assets/slide{N}_img{M}.{ext}`
- Final note: `/path/to/lecture01_notes.md`

Reference images in the note using relative paths such as `lecture01_assets/slide12_img1.png`.

### Post-extraction validation

```python
data = json.load(open("intermediate.json", encoding="utf-8"))
assert data["slides"], "No slide data"
assert all("index" in s for s in data["slides"]), "Each slide must have an index"
```

### Content sanity check

After validation, check whether the extracted text is substantive enough to learn from. This catches scanned PDFs and image-only decks early, before wasting time generating an empty note.

```python
total_chars = sum(len(s.get("text", "")) + len(s.get("notes", "")) for s in data["slides"])
n_slides = len(data["slides"])

if n_slides >= 5 and total_chars < 500:
    # Almost certainly a scanned PDF with no text layer, or an image-only deck.
    abort_with_message(
        "The source has slides but almost no extractable text "
        "(likely a scanned PDF or image-only deck). This skill needs a text layer. "
        "Run OCR first (e.g., `ocrmypdf input.pdf output.pdf`) and retry."
    )
```

The 500-char / 5-slide threshold is a heuristic, not a hard rule. A genuinely short deck (a 3-slide intro) can have low character counts and still be valid — that is why the slide-count guard is there. Use judgment if the numbers are borderline.

## Step 3 - Read or initialize course memory

**Why this step exists:** Course decks are often released gradually, and later lectures may rely on terms, notation, or results from earlier lectures processed in a different conversation. A compact persistent memory preserves continuity without loading previous full notes into the context window.

Always follow `course_memory.md`.

### Memory path

Default:

```text
source_path.parent / "course_memory.json"
```

If the user explicitly provides a course memory path, use that path instead.

### Required action

```python
memory_path = source_path.parent / "course_memory.json"

if memory_path.exists():
    course_memory = json.load(open(memory_path, encoding="utf-8"))
else:
    course_memory = {
        "schema_version": "1.0",
        "course": {
            "title": "",
            "language": "Chinese",
            "level": "unknown",
            "topic_scope": "",
        },
        "lectures": [],
        "terms": [],
        "symbols": [],
        "continuity": {
            "last_lecture_summary": "",
            "open_threads": [],
            "avoid_repeating": [],
        },
    }
```

Build a compact memory briefing from the memory file before chapter planning. Include only the course context, the most recent lecture summary, relevant terms and symbols, and open threads likely to matter for the current deck.

Do not load previous full generated notes for continuity. `course_memory.json` is the continuity boundary.

## Step 4 - Read globally and regroup by topic

**Why this step exists:** Generating the note directly slide-by-slide produces output that drifts with the lecturer's original ordering and loses the chance to merge scattered material. Building an explicit chapter plan first forces a topical view of the whole deck, which is the single biggest reason a study note feels readable rather than transcribed.

### Input

Read `{index, title, text, notes}` from `intermediate.json` plus the compact memory briefing from Step 3. Do not inspect images yet.

### Output format

```json
{
  "chapters": [
    {
      "title": "1. Neural Network Basics",
      "slide_indices": [1, 2, 3, 4],
      "summary": "Introduces the neuron model, activation functions, and forward propagation."
    },
    {
      "title": "2. Backpropagation",
      "slide_indices": [5, 6, 7, 8, 9],
      "summary": "Derives gradient computation and weight updates through the chain rule."
    }
  ]
}
```

### Grouping rules

- Prefer 3 to 8 chapters
- Keep each chapter semantically coherent
- Reordering is allowed if it improves topical flow
- Do not split one slide across multiple chapters
- Cover all non-empty instructional slides; title pages, agenda pages, and thank-you pages may be dropped
- Use course memory to clarify continuity references and terminology, but never let it override the current source material

**Short-deck fallback:** if the deck has fewer than ~5 instructional slides after dropping cover/agenda/thank-you pages, ignore the "3 to 8 chapters" rule and produce a single chapter that covers the whole deck. Splitting a 4-slide deck into 3 chapters yields three thin sections that hurt readability more than they help.

### Agent behavior

After building the chapter plan, report it briefly and continue automatically. Do not wait for confirmation unless the user explicitly asked for review checkpoints.

## Step 5 - Judge image importance

**Why this step exists:** Lecture decks routinely carry decorative logos, footer ornaments, and stock photos that add nothing to learning. Keeping them all pollutes the note and trains the reader to ignore figures. Judging each image once, against the slide's context, lets the final note keep only the figures that actually teach something.

See `image_judgment.md`.

Key rules:

- Use whatever image-reading capability the agent has available
- Produce `{decision, role, brief}` for each image
- Decorative images should be dropped
- Informative charts, formulas, diagrams, screenshots, and content-relevant photos should usually be kept

## Step 6 - Write chapter-based notes

**Why this step exists:** This is where reorganized text actually gets produced. Generating one chapter at a time, with a known summary of the previous chapter as context, keeps each generation pass bounded and avoids the model losing the overall thread on long decks. It is also the natural seam to apply the style guide consistently.

Use `assets/note_template.md` as the output skeleton. Do not copy placeholder text; use it to keep heading levels, image blocks, and review sections consistent.

### Input package per chapter

```text
- chapter title
- chapter summary
- all text and notes from the listed slides
- kept images for those slides (id + path + brief + role)
- previous chapter summary, if any
- compact course memory briefing from Step 3
```

### Writing rules

1. Turn slide bullets into connected prose
2. Expand only where it helps learning
3. Place image explanations after the relevant paragraph
4. Rewrite formulas in LaTeX instead of relying on formula screenshots
5. Use `###` subsections when a chapter is dense
6. Use course memory for terminology, notation, and brief continuity bridges
7. If course memory contains prior lectures and the current lecture clearly continues them, add a one- or two-sentence `> **与前文的衔接**` block after the note header

### Chapter template

```markdown
## {Chapter Title}

### {Subsection}

{Narrative explanation}

> **图解(图 X-Y,chart):** {Chinese explanation}

![图 X-Y](xxx_assets/slideN_imgM.png)

{Continue the explanation}
```

Use `chunking_strategy.md` when the deck is large.

## Step 7 - Add review aids

**Why this step exists:** A document that ends right after the last topic is a summary, not a note. The `复习要点` section forces one compressed takeaway per chapter (catches sections that wandered), and `思考题` turns passive reading into active recall, which is the actual mechanism by which study notes help retention.

Always append:

```markdown
## 复习要点

- **第 1 章 ...**: One-sentence takeaway.
- ...

## 思考题

1. **(概念)** ...
2. **(推导)** ...
```

Requirements:

- 5 to 10 questions
- Mix concept, derivation, application, comparison, and calculation prompts
- Hints are allowed
- Do not provide full answers

## Step 8 - Write files, validate, update course memory, and clean up

**Why this step exists:** The previous steps produce content in memory or in temporary files; this step commits the final artifacts to disk, catches broken structure before delivery, updates persistent course context for future runs, and removes scaffolding the user does not need. A clear printed summary at the end also lets the user know exactly what was produced and where to find it, which matters when the working directory contains both source slides and generated files.

```python
output_path = source_path.with_name(f"{source_path.stem}_notes.md")
output_path.write_text(final_md, encoding="utf-8")

# Reuse the short-deck fallback decision from Step 4.
lint_min = 1 if is_short_deck else 3
run([
    "python",
    "scripts/lint_note.py",
    "--note",
    str(output_path),
    "--min-chapters",
    str(lint_min),
    "--max-chapters",
    "8",
])

# After linting passes, update course_memory.json according to course_memory.md.
course_memory = update_course_memory(
    existing_memory=course_memory,
    source_file=source_path.name,
    note_file=output_path.name,
    intermediate=data,
    chapter_plan=chapter_plan,
    final_md=final_md,
)
memory_path.write_text(
    json.dumps(course_memory, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
run(["python", "scripts/lint_course_memory.py", "--memory", str(memory_path)])

for img in image_decisions:
    if img["decision"] == "drop":
        (work_dir / img["path"]).unlink(missing_ok=True)

if temp_pptx_created:
    Path(temp_pptx).unlink(missing_ok=True)

print(f"Generated note: {output_path}")
print(f"Updated course memory: {memory_path}")
print(f"Chapters: {n_chapters}")
print(f"Estimated characters: ~{char_count}")
print(f"Kept images: {n_kept} / {n_total}")
```

Important:

- `img["path"]` is relative to `work_dir`
- Clean up only files created by this workflow
- If `lint_note.py` fails, fix the Markdown structure or image paths and rerun it before reporting completion
- Do not update `course_memory.json` until the note has passed `lint_note.py`
- If `lint_course_memory.py` fails, fix the memory JSON and rerun it before reporting completion
