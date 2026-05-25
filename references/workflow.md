# Workflow

This file expands the required workflow from `SKILL.md`. Use it when the skill has already triggered.

## Step 0 - Detect capabilities

Goal: determine the safest viable execution path before doing any work.

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

## Step 3 - Read globally and regroup by topic

### Input

Read only `{index, title, text, notes}` from `intermediate.json`. Do not inspect images yet.

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

### Agent behavior

After building the chapter plan, report it briefly and continue automatically. Do not wait for confirmation unless the user explicitly asked for review checkpoints.

## Step 4 - Judge image importance

See `image_judgment.md`.

Key rules:

- Use whatever image-reading capability the agent has available
- Produce `{decision, role, brief}` for each image
- Decorative images should be dropped
- Informative charts, formulas, diagrams, screenshots, and content-relevant photos should usually be kept

## Step 5 - Write chapter-based notes

### Input package per chapter

```text
- chapter title
- chapter summary
- all text and notes from the listed slides
- kept images for those slides (id + path + brief + role)
- previous chapter summary, if any
```

### Writing rules

1. Turn slide bullets into connected prose
2. Expand only where it helps learning
3. Place image explanations after the relevant paragraph
4. Rewrite formulas in LaTeX instead of relying on formula screenshots
5. Use `###` subsections when a chapter is dense

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

## Step 6 - Add review aids

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

## Step 7 - Write files and clean up

```python
output_path = source_path.with_name(f"{source_path.stem}_notes.md")
output_path.write_text(final_md, encoding="utf-8")

for img in image_decisions:
    if img["decision"] == "drop":
        (work_dir / img["path"]).unlink(missing_ok=True)

if temp_pptx_created:
    Path(temp_pptx).unlink(missing_ok=True)

print(f"Generated note: {output_path}")
print(f"Chapters: {n_chapters}")
print(f"Estimated characters: ~{char_count}")
print(f"Kept images: {n_kept} / {n_total}")
```

Important:

- `img["path"]` is relative to `work_dir`
- Clean up only files created by this workflow
