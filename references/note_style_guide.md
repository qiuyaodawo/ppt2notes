# Note Style Guide

The output must be a usable study note, not a slide transcript.

## Core principles

| Principle | Bad slide-like version | Good study-note version |
|---|---|---|
| Narrative prose | `• Backpropagation`<br>`• Chain rule`<br>`• Gradient update` | Explain how backpropagation uses the chain rule to compute gradients layer by layer, then updates the weights with gradient descent. |
| Full sentences | `Important: learning rate` | Explain what the learning rate controls and what happens when it is too large or too small. |
| Chapter flow | Hard topic jumps | Use transitions such as “上一节建立了前向传播，本节转向训练时的反向传播。” |
| Helpful expansion | Only restate the slide | Restate the point, then add one useful background note, example, or pitfall |

## Terminology

- On first appearance, write `中文 (English)`, for example `反向传播 (Backpropagation)`
- After the first appearance, Chinese alone is usually enough
- If `course_memory.json` already records that a term was introduced in a prior lecture, avoid a full re-introduction; use Chinese alone or a brief reminder unless the current lecture needs a precise reset
- Keep common abbreviations such as `CNN`, `RNN`, `SGD`, and `Adam`
- For abbreviations, first mention may include the full bilingual form, for example `卷积神经网络 (Convolutional Neural Network, CNN)`
- Keep personal names in their standard original form

## Formulas

- Inline example: `$L = \frac{1}{n}\sum_i (y_i - \hat{y}_i)^2$`
- Block example:

  ```text
  $$
  \frac{\partial L}{\partial w} = \frac{\partial L}{\partial y} \cdot \frac{\partial y}{\partial w}
  $$
  ```

- Do not rely on formula screenshots when LaTeX can be rewritten
- If a formula introduces new symbols, explain them in prose

## Code

- Use fenced code blocks with a language tag
- Keep important teaching code from the source
- If a code sample is very long, keep the important part and mark omissions clearly

## Document structure

```markdown
# {Course Title} 讲义

> 本讲义由 ppt2notes 自动生成，基于 {source file}。共 {N} 章。

## 1. {Chapter Topic}

### 1.1 {Subsection}

...

## 复习要点

...

## 思考题

...
```

- Use one `#` title for the whole note
- Use `##` for chapters
- Use `###` for subsections when helpful
- Avoid deep heading nesting

## Image embedding

```markdown
> **图解(图 3-2,diagram):** 残差块由两个 3×3 卷积串联，输入通过 shortcut 直接加到输出，从而缓解深层网络中的梯度消失。

![图 3-2](xxx_assets/slide12_img1.png)
```

- Put the explanation block before the image
- Keep the path relative, usually `{original_stem}_assets/...`
- Embed every image marked `keep` in `image_decisions.json`; preserve the extracted basename such as `slide12_img1.png` when copying to final assets
- Only keep an image when it contributes meaning that text alone would likely lose

## Speaker notes

Speaker notes often contain high-value teaching context. Blend them into the prose instead of quoting them as a separate artifact.

## Course continuity

Always use `course_memory.json` as the continuity source. It should help the note sound like part of a course rather than an isolated document, but it must stay subordinate to the current source.

When prior lectures exist and the current lecture clearly builds on them, add a short bridge after the note header:

```markdown
> **与前文的衔接**: 上一讲已经说明……本讲在此基础上……
```

- Keep the bridge to one or two sentences
- Mention only prior context that helps the current lecture
- Do not force a bridge for an independent lecture
- Do not paste old lecture summaries into the note
- Keep notation and terminology consistent with memory unless the current lecture explicitly changes them

## Boundaries for expansion

The point of expanding the source material is to lower the friction for a student reading the slide deck on their own. Use that test, not a checklist, to decide whether a sentence belongs.

## Important and difficult material

Before writing each chapter, identify the topics that need careful explanation. Treat a topic as important or difficult when it:

- Is central to the lecture objective or appears repeatedly
- Supports later concepts, examples, labs, or exam-style questions
- Contains formulas, algorithms, derivations, proofs, state machines, grammar rules, execution traces, or process diagrams
- Is compressed into a conclusion on the slide without the missing reasoning steps
- Is likely to confuse beginners because two terms, methods, or notations look similar

For each such topic, do more than summarize. Explain what problem it addresses, the intuition behind the method, the key steps or derivation, one concrete example/comparison/pitfall, and how it connects to the surrounding lecture content. For formulas, define the symbols and explain why the transformation or result is valid. For algorithms and procedures, explain the input, output, main loop or decision points, and a common failure or edge case.

A short paragraph is fine for a minor slide point. A central or difficult topic that only restates the slide bullets should be revised before finalizing the note.

Allowed expansions, and why each helps:

- **Brief historical background** — anchors a concept in time so the student remembers when and why it appeared
- **Missing derivation steps** — slides routinely jump from "we want X" to "the result is Y" because the lecturer filled the gap verbally; restoring the steps is exactly the value the lecturer was providing live
- **One short clarifying example** — a concrete instance helps a beginner pattern-match the abstract definition
- **Concept relationships** — explaining how the current topic connects to an earlier or later one prevents the deck from feeling like disconnected islands
- **Common misconceptions** — heading off a predictable wrong interpretation saves the student from learning the wrong thing first

Avoid:

- **Tangents unrelated to the deck** — they cost reading time without explaining the source material; a curious reader can search elsewhere
- **Content far above the apparent course level** — pulling in graduate-level theory into an undergraduate intro creates noise, not depth
- **Invented facts, citations, datasets, or references** — students will trust the note; fabrication damages that trust and produces wrong learning

The single test for inclusion: would removing this sentence make the source deck harder to follow? If no, drop it.

## Length guidance

As a rough target, the final note is usually 2x to 4x the source text volume.

## Review points

Write one compressed takeaway per chapter.

## Practice questions

- Write 5 to 10 questions
- Mix concept, derivation, application, comparison, and calculation prompts
- Hints are allowed
- Do not provide full answers
