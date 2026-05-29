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

**Why this step exists:** The three file formats need different toolchains, and a lecture directory needs a manifest before note planning. `.ppt` (old binary format) cannot be parsed by `python-pptx` directly — it needs LibreOffice to convert it first. Branching up front is cleaner than letting downstream code blow up on an unsupported input.

```python
source = Path(input_path)
if source.is_dir():
    mode = "lecture_directory"
    run("python scripts/prepare_lecture.py --input-dir <LecXX> --course-root <course-root> --work-dir <course-root>/.ppt2notes_work")
elif source.suffix.lower() == ".ppt":
    converted = run("python scripts/convert_ppt_to_pptx.py --input <file> --output <tmp.pptx>")
    process_as_pptx(converted)
elif source.suffix.lower() == ".pptx":
    process_as_pptx(source)
elif source.suffix.lower() == ".pdf":
    process_as_pdf(source)
else:
    abort("Unsupported format")
```

### Lecture directory mode

Use this mode when the user gives a directory such as `Lec01/` and that directory represents one lecture. The directory may contain several Part PDFs/PPTX files, question PDFs, lab sheets, and code examples. Run `prepare_lecture.py` first to create `lecture_manifest.json` and `coverage_report.json`; those files become the formal input to the rest of the workflow.

Resolve paths as follows:

- `--course-root`: the course-level folder that contains all `LecXX` folders. If the user does not specify it, use `input_dir.parent`.
- `--memory-path`: an explicit memory path, if provided by the user. It overrides `--course-root`.
- `--work-dir`: default to `<course-root>/.ppt2notes_work`.

If `lecture_manifest.json` contains any material with `requires_conversion: true`, convert that `.ppt` with `convert_ppt_to_pptx.py`, extract the converted `.pptx` into that material's `work_dir`, and update the manifest/coverage paths before chapter planning. If LibreOffice is missing, stop with the install/resave guidance instead of continuing with an empty material.

## Step 2 - Extract the intermediate JSON

**Why this step exists:** Separating extraction from generation gives a stable, inspectable artifact between the two stages. If something looks wrong in the final note, you can re-check `intermediate.json` to tell whether the bug was in extraction or in the writing stage. It also makes the rest of the pipeline format-agnostic.

### Working directory convention

Given `/path/to/lecture01.pptx`, prefer a centralized work directory:

- Work directory: `/path/to/.ppt2notes_work/lecture01/`
- Intermediate JSON: `/path/to/.ppt2notes_work/lecture01/intermediate.json`
- Image manifest: `/path/to/.ppt2notes_work/lecture01/image_manifest.json`
- Extracted images: `/path/to/.ppt2notes_work/lecture01/slide{N}_img{M}.{ext}`
- Final note: `/path/to/lecture01_notes.md`

For a lecture directory `/course/Lec01/`:

- Work directory: `/course/.ppt2notes_work/Lec01/`
- Manifest: `/course/.ppt2notes_work/Lec01/lecture_manifest.json`
- Coverage report: `/course/.ppt2notes_work/Lec01/coverage_report.json`
- Final note: `/course/Lec01/Lec01_notes.md`

Image extraction is default-on. Do not pass `--no-images` unless the user explicitly asks for a text-only note or the runtime cannot extract images.

Keep raw extraction artifacts under `.ppt2notes_work/`. For every retained instructional image, copy only that image to a small final assets location such as `{output_stem}_assets/` or `{lecture_dir_name}_assets/`, then reference that final relative path from the note. Do not leave raw per-PDF `_assets` directories in the lecture folder.

`extract_pdf.py` writes `intermediate.json` and `image_manifest.json`; `extract_pptx.py` writes image refs into `intermediate.json`. Both print only a compact summary by default; use `--print-json` only if stdout JSON is explicitly needed. Use `--quiet` in batch or directory runs.

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

Single-file default:

```text
source_path.parent / "course_memory.json"
```

Lecture-directory default:

```text
course_root / "course_memory.json"
```

If the user explicitly provides a course memory path, use that path instead. In directory mode, `prepare_lecture.py` records the resolved memory path in `lecture_manifest.json`; use that exact value.

### Required action

```python
memory_path = resolved_memory_path

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

Single-file mode: read `{index, title, text, notes}` from `intermediate.json` plus the compact memory briefing from Step 3. Do not inspect images yet.

Directory mode: read `lecture_manifest.json`, then read the listed `intermediate.json` files and code samples. Preserve source ordering from the manifest, but chapter organization should still be topical.

Companion material rules:

- `lecture_slides`: primary source for chapter structure
- `questions`: fold into examples, checkpoints, or final `思考题`
- `code_examples`: quote small relevant snippets and explain behavior
- `labs`: connect practical tasks to the concepts they exercise
- `companion_material`: include only if it directly supports a chapter

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
      "summary": "Derives gradient computation and weight updates through the chain rule.",
      "deep_explanation_targets": [
        "用三层网络的一个权重路径推导 chain rule 如何把最终 loss 分解成局部梯度",
        "用连续相乘的 0.2 导数数值例子解释 gradient vanishing 为什么会让前层几乎不更新"
      ],
      "code_examples": [
        {
          "path": "backprop_example.py",
          "snippet": "dW2 = h.T @ dlogits"
        }
      ],
      "question_prompts": [
        "Q0.1.pdf: worked prompt for deriving one local gradient"
      ]
    }
  ]
}
```

Write this plan to `chapter_plan.json` in the active work directory before drafting the note. In directory mode, each chapter entry should also include a `sources` list that names the source files it uses. Then update `coverage_report.json` so every source shows whether it was included and which chapters used it.

### Grouping rules

- Prefer 3 to 8 chapters
- Keep each chapter semantically coherent
- Reordering is allowed if it improves topical flow
- Do not split one slide across multiple chapters
- Cover all non-empty instructional slides; title pages, agenda pages, and thank-you pages may be dropped
- For each chapter, record `deep_explanation_targets` for central, repeated, later-dependent, formula-heavy, algorithmic, derivation-based, process-diagram, or easily confused topics. Each target must name a concrete explanation block, not a broad objective. Prefer targets like "用两个 MPI 进程的发送/接收顺序画出阻塞通信死锁" or "用一个 warp 等待访存、另一个 ready warp 被调度的时间线解释 latency hiding"; avoid broad targets like "理解 SM、warp scheduling 和架构演化".
- In directory mode, cover all primary lecture-slide files unless a file is clearly non-instructional; account for every question, lab, and code file in coverage even if it is not included in prose
- In directory mode, every `code_examples` material from `lecture_manifest.json` must appear in at least one chapter's `code_examples`, with a path and preferably a short snippet. Every `questions` material must appear in `question_prompts` or `questions` as a worked prompt, checkpoint, or final `思考题` candidate. `lint_depth.py --lecture-manifest` enforces this.
- In directory mode with multiple slide files, use `source_refs` when page numbers overlap, for example `{"source_path": "02-PartB.pdf", "slide_indices": [1, 2]}`. `build_chapter_context.py` uses `source_refs` to avoid confusing page 1 of Part A with page 1 of Part B.
- Use course memory to clarify continuity references and terminology, but never let it override the current source material

**Short-deck fallback:** if the deck has fewer than ~5 instructional slides after dropping cover/agenda/thank-you pages, ignore the "3 to 8 chapters" rule and produce a single chapter that covers the whole deck. Splitting a 4-slide deck into 3 chapters yields three thin sections that hurt readability more than they help.

### Agent behavior

After building the chapter plan, report it briefly and continue automatically. Do not wait for confirmation unless the user explicitly asked for review checkpoints.

## Step 5 - Judge image importance

**Why this step exists:** Lecture decks routinely carry decorative logos, footer ornaments, and stock photos that add nothing to learning. Keeping them all pollutes the note and trains the reader to ignore figures. Judging each image once, against the slide's context, lets the final note keep only the figures that actually teach something.

See `image_judgment.md`.

Key rules:

- Use whatever image-reading capability the agent has available. If images were extracted but no visual inspection is available, use `image_manifest.json`, image dimensions/positions, filenames, and `context_text` as a fallback rather than skipping `image_decisions.json`.
- Start from `image_manifest.json` when present, because it records extracted/skipped images, dimensions, position, coverage, and threshold decisions
- Produce `{id, path, note_path, decision, role, brief}` for each kept image; `path` stays relative to the work directory and `note_path` is relative to the final Markdown note
- Decorative images should be dropped
- Informative charts, formulas, diagrams, screenshots, and content-relevant photos must be kept unless they are unreadable, redundant, or better represented as text/code/formulas
- Write the final image decisions to `image_decisions.json` in the active work directory before drafting image blocks

## Step 6 - Write chapter-based notes

**Why this step exists:** This is where reorganized text actually gets produced. Generating one chapter at a time, with a known summary of the previous chapter as context, keeps each generation pass bounded and avoids the model losing the overall thread on long decks. It is also the natural seam to apply the style guide consistently.

Use `assets/note_template.md` as the output skeleton. Do not copy placeholder text; use it to keep heading levels, image blocks, and review sections consistent.

### Build the input package per chapter

After `chapter_plan.json` and `image_decisions.json` are ready, build an explicit drafting context:

```bash
python scripts/build_chapter_context.py \
  --chapter-plan <work-dir>/chapter_plan.json \
  --intermediate <work-dir>/intermediate.json \
  --image-decisions <work-dir>/image_decisions.json \
  --out <work-dir>/chapter_context.json
```

In directory mode, pass every primary slide extraction with repeated `--intermediate`, and use the `code_examples` and `question_prompts` already recorded in each chapter plan entry. Draft from `chapter_context.json`, not from the chapter summary alone. This is the execution closure for `deep_explanation_targets`.

Each chapter package must contain:

```text
- chapter title
- chapter summary
- all text and notes from the listed slides
- kept images for those slides (id + path + brief + role)
- deep explanation targets from the chapter plan
- code examples and key snippets assigned to the chapter
- question/lab prompts assigned to the chapter
- previous chapter summary, if any
- compact course memory briefing from Step 3
```

### Writing rules

1. Turn slide bullets into connected prose
2. Expand only where it helps learning
3. Explain every `deep_explanation_targets` item carefully: state the problem, intuition, key steps or derivation when applicable, one example/comparison/pitfall, and the connection to the surrounding lecture
4. Embed every `keep` image from `image_decisions.json` near the paragraph where it is explained
5. Rewrite formulas in LaTeX instead of relying on formula screenshots, and define symbols in prose
6. Use `###` subsections when a chapter is dense
7. Use course memory for terminology, notation, and brief continuity bridges
8. If course memory contains prior lectures and the current lecture clearly continues them, add a one- or two-sentence `> **与前文的衔接**` block after the note header
9. For every code file assigned to the chapter, quote one key snippet, explain which concept it verifies, and name one common mistake or runtime phenomenon
10. For every question PDF assigned to the chapter, turn it into a worked prompt, checkpoint, or final `思考题` candidate

After drafting a chapter, compare it against its `deep_explanation_targets` and kept images. If a target is only named, translated, or restated from the slide, revise the chapter before moving on. If a kept image is not embedded with a nearby `> **图解(...)**` block, copy/reference the image or revise the decision before moving on.

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

### Enhancing an existing note

When the user wants to improve already-generated notes, do not regenerate from scratch unless necessary. Build enhancement prompts:

```bash
python scripts/build_chapter_context.py \
  --chapter-plan <work-dir>/chapter_plan.json \
  --existing-note <note.md> \
  --mode enhance \
  --out <work-dir>/enhance_context.json
```

For each chapter, append one or more `### 深入理解：...` blocks after the current chapter content. Each block must consume a `deep_explanation_targets` item and include the problem, intuition, steps/derivation or execution trace, an example or pitfall, and the connection to the surrounding lecture. Then rerun `lint_note.py` and `lint_depth.py`.

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
import shutil

output_path = source_path.with_name(f"{source_path.stem}_notes.md")
output_path.write_text(final_md, encoding="utf-8")
image_decisions_path = work_dir / "image_decisions.json"
write_json(image_decisions_path, image_decisions)

for img in image_decisions:
    if img["decision"] == "keep":
        raw_image = work_dir / img["path"]
        final_image = output_path.parent / img["note_path"]
        final_image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(raw_image, final_image)

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
    "--image-decisions",
    str(image_decisions_path),
])

lint_depth_cmd = [
    "python",
    "scripts/lint_depth.py",
    "--note",
    str(output_path),
    "--chapter-plan",
    str(work_dir / "chapter_plan.json"),
]
if lecture_manifest_path:
    lint_depth_cmd.extend(["--lecture-manifest", str(lecture_manifest_path)])
run(lint_depth_cmd)

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

write_json(work_dir / "chapter_plan.json", chapter_plan)
update_coverage_report(work_dir / "coverage_report.json", chapter_plan, final_md)

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
print(f"Chapter plan: {work_dir / 'chapter_plan.json'}")
print(f"Image decisions: {work_dir / 'image_decisions.json'}")
print(f"Coverage report: {work_dir / 'coverage_report.json'}")
```

Important:

- Before running the linter, perform a depth self-check against `chapter_plan.json`: every `deep_explanation_targets` item should have a substantive explanation in the corresponding chapter, not just a bullet restatement
- `img["path"]` is relative to `work_dir`
- `img["note_path"]` is relative to the final note path and must match the Markdown image target
- Preserve the extracted image basename when copying a kept image to final assets, so `lint_note.py --image-decisions` can match the decision to the Markdown image target
- Clean up only files created by this workflow
- If `lint_note.py` fails, fix the Markdown structure or image paths and rerun it before reporting completion
- Do not update `course_memory.json` until the note has passed `lint_note.py`
- If `lint_course_memory.py` fails, fix the memory JSON and rerun it before reporting completion
