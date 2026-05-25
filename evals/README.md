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

`fixtures/` is **not** checked in — each test case names a file but you supply the bytes. This keeps the repo small and lets you point the tests at decks you actually care about.

## Populating fixtures

You have three options, from easiest to most rigorous:

1. **Use your own decks.** Drop any `.pptx`/`.pdf` files into `fixtures/` and rename them to match the paths in `evals.json`. The faster path if you already have representative material.
2. **Edit `evals.json`** to point `"files"` at decks you already have somewhere else on disk. Useful when you do not want to copy large files.
3. **Generate synthetic fixtures.** A short `python-pptx` script can build minimal decks for the structural test cases (`tiny_deck.pptx`, `image_heavy.pptx`). For `scanned.pdf`, you can take any PDF and run it through a "print to PDF" tool that does not embed a text layer, or use `pdf2image` + `img2pdf` to round-trip pages through PNG.

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

For automated runs, follow the `skill-creator` workflow: spawn one with-skill subagent and one baseline subagent per test case in the same turn, save outputs under a sibling workspace directory (e.g. `../ppt2notes-workspace/iteration-1/eval-<N>/{with_skill,old_skill}/outputs/`), then grade with `agents/grader.md` and aggregate with `scripts.aggregate_benchmark`.

## Adding new evals

When a real-world failure surfaces something the existing tests do not catch, add a sixth eval rather than over-extending an existing one. Each eval should have a single clear thing it is testing — that keeps the grading signal interpretable when results regress.
