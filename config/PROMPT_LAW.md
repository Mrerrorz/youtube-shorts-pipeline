# PROMPT_LAW.md

## Purpose
This file governs all LLM prompt outputs.

---

## Mandatory Output Format

All outputs must return strict JSON.
No prose outside schema.

---

## JSON Enforcement Rule

Every generation must validate before next stage.
If malformed: retry.

---

## Script Prompt Standard

Prompt must force:
- hook
- insight
- mechanism
- takeaway
- scene readiness

---

## Prompt Tone Rule

Prompt must explicitly forbid:
- generic motivation
- vague business wisdom
- repeated internet phrasing

---

## Headline Prompt Rule

Headline must score:
- curiosity
- clarity
- retention potential

---

## Scene Prompt Rule

Scene output must always include:
- scene number
- duration
- visual
- caption
- emotion

---

## Prompt Retry Rule

If output lacks one sharp insight: regenerate.

---

## LLM Instruction Priority

Content quality > speed.
