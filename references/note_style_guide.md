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
- Only keep an image when it contributes meaning that text alone would likely lose

## Speaker notes

Speaker notes often contain high-value teaching context. Blend them into the prose instead of quoting them as a separate artifact.

## Boundaries for expansion

Allowed expansions:

- Brief historical background
- Missing derivation steps
- One short clarifying example
- Concept relationships
- Common misconceptions

Not allowed:

- Tangents unrelated to the deck
- Content far above the apparent course level without need
- Invented facts, citations, datasets, or references

Test for inclusion:

- Every added sentence should help a student understand the source deck more easily

## Length guidance

As a rough target, the final note is usually 2x to 4x the source text volume.

## Review points

Write one compressed takeaway per chapter.

## Practice questions

- Write 5 to 10 questions
- Mix concept, derivation, application, comparison, and calculation prompts
- Hints are allowed
- Do not provide full answers
