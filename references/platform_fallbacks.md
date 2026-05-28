# Capability Fallbacks

This skill is intended to be usable across many agent runtimes. The agent should choose a path based on available capabilities rather than product-specific assumptions.

## Capability matrix

| Capability mode | Shell | Python | LibreOffice | Visual file reading | File writing |
|---|---|---|---|---|---|
| Scripted local runtime | Yes | Yes | Maybe | Maybe | Yes |
| Restricted runtime with multimodal file access | No or limited | No or limited | No | Yes | Maybe |
| Text-only runtime | No | No | No | No | Maybe |

## Decision flow

```text
1. Can the agent run shell commands and Python?
   - Yes -> prefer the scripted path
   - No -> continue

2. Can the agent open PDFs and images directly with a native multimodal capability?
   - Yes -> use the native multimodal fallback
   - No -> continue

3. If neither path is available:
   - stop
   - explain the missing capability clearly
   - ask the user to provide a PDF in a more capable environment
```

## Scripted path

Use the standard workflow from `SKILL.md`, including default-on image extraction, image judgment, and final-note embedding for kept images.

## Native multimodal fallback

This mode applies when the agent cannot run extraction scripts but can directly inspect PDF pages and images.

### Supported inputs

| Format | Supported? | Strategy |
|---|---|---|
| `.pdf` | Yes | Read the PDF directly and emulate the intermediate structure in memory |
| `.pptx` | Usually no | Tell the user to resave as PDF and retry |
| `.ppt` | No | Tell the user to resave as `.pptx` or `.pdf` and retry |
| lecture directory | Usually no | Ask the user to run in a scripted environment, or provide a generated `lecture_manifest.json` plus extracted text |

### Fallback workflow for PDF

```text
Step 0: detect that scripting is unavailable
Step 1: verify the input is a PDF
Step 2: skip bundled extraction scripts
        read the PDF directly
        build an equivalent in-memory structure with page text, inferred titles, and image observations
Step 3-7: follow the normal reasoning workflow, including course memory and image judgment
Step 8: if file writing is available, write the Markdown note and course_memory.json
        otherwise return both the Markdown and the updated course_memory.json content directly in the response
```

### Image handling in multimodal fallback

If images cannot be exported as files:

- Treat this as a fallback limitation, not the default behavior
- Prefer text-only image explanations only when image files truly cannot be written or referenced
- Optionally cite the original page number, for example `(see the figure on page 12 of the source PDF)`

Add a short note near the end of the generated Markdown:

```markdown
> **说明**: 本讲义是在无脚本图片导出能力的环境中生成的，关键图片内容已改写为文字说明。
```

## Text-only fallback

If the agent cannot run scripts and cannot directly inspect PDF pages or images:

- Stop instead of pretending to process the file
- Explain that the skill requires either local extraction tooling or direct PDF/image reading capability
- Ask the user to rerun the task in a more capable environment or provide extracted text manually

## Error message templates

### Missing Python

```text
Python was not detected in the current runtime.
This skill needs Python 3.8+ for the scripted path.
If you cannot install Python here, export the deck as PDF and retry in a runtime that supports direct PDF reading.
```

### Missing parser

```text
Python is available, but a required parser is missing: {missing_dependency}
Install only what is needed for the current input:
- PDF: pip install pymupdf
- PPTX: pip install python-pptx
```

### Missing LibreOffice for `.ppt`

```text
The input is an old `.ppt` file and requires LibreOffice for conversion.
Either install LibreOffice or reopen the file in PowerPoint / LibreOffice and save it as `.pptx` or `.pdf`.
```
