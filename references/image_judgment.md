# Image Judgment

In Step 5, inspect each extracted image using whatever image-reading capability the agent has available, then decide whether it should appear in the final note.

## Output structure

```json
{
  "id": "slide12_img1",
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

1. Inspect the image itself
2. Check `context_text` from the intermediate JSON
3. Ask three questions:
   - Does the image communicate something important that the slide text does not fully capture?
   - Would a learner miss a key concept if this image disappeared?
   - Can the agent explain the image accurately in one or two Chinese sentences?
4. Decide:
   - If all three answers are no, drop it
   - If any answer is yes, keep it and write a useful `brief`

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

## Optional persistence

The agent may write `image_decisions.json` in the work directory for debugging and reuse:

```json
{
  "decisions": [
    {"id": "slide1_img1", "decision": "drop", "role": "decoration", "brief": ""},
    {"id": "slide3_img1", "decision": "keep", "role": "diagram", "brief": "..."}
  ]
}
```
