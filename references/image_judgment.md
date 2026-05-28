# Image Judgment

In Step 5, inspect each extracted image using whatever image-reading capability the agent has available, then decide whether it should appear in the final note. When `image_manifest.json` exists, use it as the screening table before opening images: it records page number, dimensions, position, coverage, extracted/skipped status, and threshold reasons.

Image handling is default-on. A `keep` decision means the image must be copied or referenced from the final Markdown with a nearby `> **图解(...)**` block. If you cannot embed the image, do not leave the decision as `keep`; fix the path, re-extract the image, or change the decision with a clear reason.

## Output structure

```json
{
  "id": "slide12_img1",
  "path": "slide12_img1.png",
  "decision": "keep",
  "role": "diagram",
  "brief": "One concise Chinese explanation of what the image teaches"
}
```

Allowed roles:

- `chart`
- `formula`
- `diagram`
- `screenshot`
- `photo`
- `decoration`

## Role guide

| Role | Meaning | Default |
|---|---|---|
| `chart` | A data visualization such as a bar chart, line chart, scatter plot, heatmap, or pie chart | keep |
| `formula` | A formula screenshot or derivation figure | keep, but rewrite the formula in LaTeX |
| `diagram` | A process diagram, architecture figure, concept sketch, or system structure figure | keep |
| `screenshot` | A UI, code, tool, or webpage screenshot | keep only if it directly supports instruction |
| `photo` | A real-world photo of a person, experiment, product, scene, or artifact | keep only if it is instructionally relevant |
| `decoration` | Background art, logos, purely decorative icons, page ornaments, repeated branding | drop |

## Decision procedure

1. Read `image_manifest.json` if present
2. Drop images already marked `skipped` unless there is a strong reason to re-extract them
3. Inspect the remaining image itself
4. Check `context_text` from the intermediate JSON
5. Ask three questions:
   - Does the image communicate something important that the slide text does not fully capture?
   - Would a learner miss a key concept if this image disappeared?
   - Can the agent explain the image accurately in one or two Chinese sentences?
6. Decide:
   - If all three answers are no, drop it
   - If any answer is yes, keep it, preserve its `path`, and write a useful `brief`

## What makes a good `brief`

Good:

- `TCP 三次握手：客户端发 SYN，服务端回 SYN-ACK，客户端再回 ACK，连接建立。`
- `ResNet 残差块：两个 3×3 卷积串联，输入通过 shortcut 直接加到输出。`
- `训练曲线显示验证损失在 epoch 12 后回升，说明开始过拟合。`

Bad:

- `A chart`
- `A TCP figure`
- `A course-related screenshot`

## Embedding format

```markdown
> **图解(图 3-2,diagram):** TCP 三次握手：客户端发 SYN，服务端回 SYN-ACK，客户端再回 ACK，连接建立。

![图 3-2](lecture_assets/slide12_img1.png)
```

## Boundaries and pitfalls

- For `formula` images, LaTeX in the note is mandatory even if the image is kept
- For readable code screenshots, prefer rewriting the code as text and dropping the image
- If the same branding or cover image repeats across slides, keep at most the first meaningful instance
- Low-resolution or badly cropped images can usually be dropped
- Composite figures with multiple small panels should usually be kept as one unit if the relationships matter

## Required persistence

Write `image_decisions.json` in the active work directory for debugging, auditability, and regeneration. Do this even when every image is dropped:

```json
{
  "schema_version": "1.0",
  "decisions": [
    {"id": "slide1_img1", "source_file": "PartA.pdf", "decision": "drop", "role": "decoration", "brief": ""},
    {"id": "slide3_img1", "source_file": "PartA.pdf", "path": "slide3_img1.png", "decision": "keep", "role": "diagram", "brief": "..."}
  ]
}
```

If the workflow later deletes dropped raw images, keep their decision records. The decision file is the audit trail.
