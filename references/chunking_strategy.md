# Chunking Strategy

## When to chunk

Chunk the task when either condition is true:

- More than 30 slides/pages
- More than about 20,000 Chinese characters of combined slide text and notes

## Core idea

Use the chapter plan from Step 4 as the chunk boundary.

Benefits:

1. Each generation pass stays bounded
2. Chapters remain internally coherent
3. Cross-chapter continuity can be preserved through short summaries

## Execution pattern

```python
# After Step 4 returns chapters

slides_by_index = {slide["index"]: slide for slide in intermediate["slides"]}

for i, chapter in enumerate(chapters):
    chapter_slides = [slides_by_index[idx] for idx in chapter["slide_indices"]]
    inputs = {
        "title": chapter["title"],
        "summary": chapter["summary"],
        "slides_text": [s["text"] + "\n" + s.get("notes", "") for s in chapter_slides],
        "kept_images": [img for img in all_kept if img["slide_index"] in chapter["slide_indices"]],
        "prev_summary": chapters[i - 1]["summary"] if i > 0 else None,
        "course_memory_brief": course_memory_brief,
    }
    chapter_md = generate_one_chapter(inputs)
    accumulator.append(chapter_md)

final_md = HEADER + "\n\n".join(accumulator) + REVIEW_SECTION + QUESTION_SECTION
```

Important:

- `slide_indices` are 1-based slide numbers, not zero-based list offsets
- Use a dictionary keyed by `slide["index"]` to avoid indexing mistakes

## Rough budget

| Item | Typical size |
|---|---|
| Text and notes for one chapter | 1k to 3k tokens |
| Image briefs | 0.2k to 1k tokens |
| Instructions plus previous summary | ~0.3k tokens |
| Total input per chapter | usually under 5k tokens |

## If one chapter is still too large

If a single chapter contains more than about 12 slides or more than about 5,000 Chinese characters of text:

1. Prefer to split that chapter into two subchapters
2. If that is not possible, process the chapter in smaller internal batches and merge carefully

## Cross-chapter consistency

- Keep a terminology memory so bilingual term introductions are not repeated unnecessarily
- Keep course-level continuity grounded in `course_memory.json`; do not load previous full notes while chunking
- Normalize chapter numbering at the end
- Track image numbering as `图 {chapter_no}-{image_no}`

## Retry behavior

If generation for one chapter fails or truncates:

1. Retry that chapter once
2. If it still fails, fall back to a minimal prose conversion and mention the fallback in the final report
