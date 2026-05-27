# ppt2notes — Evals

This directory holds test cases that exercise the skill end-to-end. The format follows the `skill-creator` evals schema, so the same test set can be run by hand or piped into the skill-creator iteration loop.

## Layout

```
evals/
├── README.md          # this file
├── evals.json         # prompts + assertions
└── fixtures/          # input slide files referenced by evals.json
    ├── concept_heavy_zh.pptx
    ├── math_heavy_en.pdf
    ├── image_heavy.pptx
    ├── scanned.pdf
    └── tiny_deck.pptx
```

`fixtures/` is **not** checked in — each test case names a file, and you can either generate synthetic fixtures or supply your own real decks.

## Populating fixtures

You have three options, from easiest to most rigorous:

1. **Generate synthetic fixtures.** Run `python scripts/generate_eval_fixtures.py --out-dir evals/fixtures` from the skill root. This creates every file named in `evals.json`.
2. **Use your own decks.** Drop any `.pptx`/`.pdf` files into `fixtures/` and rename them to match the paths in `evals.json`. This is better when you have representative course material.
3. **Edit `evals.json`** to point `"files"` at decks you already have somewhere else on disk. Useful when you do not want to copy large files.

## What each test case targets

| ID | Name | What it stresses |
|---|---|---|
| 1 | `concept-heavy-zh` | Default path: topic reorganization, bilingual terms, review sections |
| 2 | `math-heavy-en-to-zh` | Formula rewriting as LaTeX, Chinese output from English source |
| 3 | `image-heavy-deck` | Image judgment: decorative vs instructional figures |
| 4 | `scanned-pdf-graceful-failure` | Edge case: no text layer → clean abort instead of empty note |
| 5 | `very-short-deck` | Edge case: deck < 5 slides → single-chapter fallback |

## Running the evals

These prompts and assertions are intentionally written to be runnable through the `skill-creator` iteration tooling, but they are also useful as a manual checklist. The simplest manual flow:

1. Place the corresponding file in `fixtures/`.
2. In a fresh agent session, send the `prompt` and attach (or reference) the fixture.
3. Walk through the `assertions` list one by one against what the agent produced.

For structural checks after a note is generated, run:

```bash
python scripts/lint_note.py --note path/to/generated_notes.md --min-chapters 3 --max-chapters 8
```

For comparative quality checks, run each prompt in a fresh agent session and manually score the assertions in `evals.json`. Keep generated outputs in a sibling workspace directory such as `../ppt2notes-workspace/iteration-1/eval-<N>/outputs/` so the skill directory stays clean.

## Adding new evals

When a real-world failure surfaces something the existing tests do not catch, add a sixth eval rather than over-extending an existing one. Each eval should have a single clear thing it is testing — that keeps the grading signal interpretable when results regress.
