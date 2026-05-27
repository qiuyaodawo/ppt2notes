# Course Memory

Course memory is a required persistent state file for this skill. It keeps lecture notes coherent across separate runs, separate conversations, and separate agents without loading previous full notes into context.

## File location

Default path:

```text
{source_directory}/course_memory.json
```

Use this same file for every lecture in the same course folder. If the user explicitly provides a different course memory path, use that path instead.

## Required behavior

Always perform these actions for every successful note-generation task:

1. Read `course_memory.json` if it exists
2. If it does not exist, initialize an empty memory object using `assets/course_memory_schema.json`
3. Use the memory while planning and writing the current note
4. Update and write `course_memory.json` after the note passes structural validation
5. Run `python scripts/lint_course_memory.py --memory course_memory.json`

Do not treat course memory as a batch-only feature. A single lecture still initializes useful memory for future lectures.

## Initialization

When no memory file exists, start from:

```json
{
  "schema_version": "1.0",
  "course": {
    "title": "",
    "language": "Chinese",
    "level": "unknown",
    "topic_scope": ""
  },
  "lectures": [],
  "terms": [],
  "symbols": [],
  "continuity": {
    "last_lecture_summary": "",
    "open_threads": [],
    "avoid_repeating": []
  }
}
```

Infer missing course fields from the source file name, metadata, and lecture content. Keep uncertain values conservative rather than inventing a precise course title.

## How to use memory while writing

Before chapter planning, build a compact memory briefing:

- Course title, level, and topic scope
- The most recent lecture summary
- Relevant established terms and symbols
- Open conceptual threads that the current lecture appears to continue
- Concepts already explained enough, so the current note can refer back briefly

Use this briefing to:

- Add continuity where it is genuinely helpful
- Keep terminology and notation consistent
- Avoid re-introducing the same term bilingually if memory already records it, unless the current note needs a reminder
- Explain references such as "上一讲", "as discussed before", "继续", or "recall" using the memory rather than leaving them vague
- Write transitions that connect the current lecture to prior course material

Do not load previous full notes just to improve continuity. The memory file is the continuity boundary.

## Note output impact

If memory contains at least one prior lecture and the current deck clearly continues earlier material, include a short opening bridge after the note header:

```markdown
> **与前文的衔接**: 上一讲已经说明……本讲在此基础上……
```

Keep this bridge to one or two sentences. If the current lecture is independent, omit the bridge rather than forcing a fake connection.

For the first processed lecture, do not add an empty "前文衔接" block. The memory still matters because it will be written for future runs.

## How to update memory

After the note passes `lint_note.py`, update memory from the current lecture and generated note:

- Append or replace the lecture record for the current `source_file`
- Update `course.title`, `course.level`, and `course.topic_scope` only when the current material gives better evidence
- Add new important terms and symbols
- Preserve existing definitions unless the current lecture clearly refines them
- Update `continuity.last_lecture_summary` to the current lecture
- Refresh `continuity.open_threads` with ideas likely to continue later
- Refresh `continuity.avoid_repeating` with foundations now sufficiently covered

If a `source_file` already exists in `lectures`, replace that record instead of appending a duplicate. This supports regenerating notes for one lecture.

After writing the file, validate it:

```text
python scripts/lint_course_memory.py --memory course_memory.json
```

Fix validation failures before reporting completion.

## Size discipline

Keep memory compact enough to load in future runs:

- `last_lecture_summary`: 2 to 4 Chinese sentences
- Each lecture `summary`: 2 to 4 Chinese sentences
- Each lecture `key_takeaways`: 3 to 8 bullets
- `terms`: keep the course's important terms, not every phrase
- `symbols`: keep notation that is likely to reappear
- `open_threads`: 3 to 8 items
- `avoid_repeating`: 3 to 12 items

When memory grows too large, compress older lecture records before adding the new one. Do not delete important terms or symbols just because they are old.

## Boundaries

- Do not use memory to introduce unsupported claims into the note
- Do not let memory override the current source when they conflict; mention only what the current source supports
- Do not store full generated chapters in memory
- Do not store decorative image decisions in memory
- Do not update memory if extraction fails, scanned-PDF detection aborts, or note linting fails
