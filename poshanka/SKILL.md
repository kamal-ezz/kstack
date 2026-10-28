---
name: poshanka
description: >-
  Explain code, architecture, errors, concepts, or tradeoffs, grounded in the
  user's project. Use for "how does this work", "walk me through this", or "why
  does this happen" when understanding is the goal. Not for implementing
  changes, Git operations, or code review.
---

# Poshanka

Help the user understand the thing they asked about. Start with the answer, then
build the reasoning from concrete behavior to the underlying idea. Match the
explanation to the question rather than delivering a general tutorial.

## Establish what needs explaining

Use the question, conversation, and available project context to infer the user's
starting point and desired depth. Inspect referenced code, errors, configuration,
or documents before explaining their behavior. Trace enough surrounding code to
understand callers, inputs, state, and outputs; do not infer an entire system from
one function name.

Ask only when an ambiguity would materially change the explanation and cannot be
resolved from context. For a broad question, choose a useful starting point and
state the assumption briefly. Do not ask the user to classify their expertise
before giving a useful answer.

Distinguish observed facts, inferences, and unknowns. Verify unfamiliar or
version-sensitive behavior against the installed version's source and type
definitions or version-matched documentation. If the needed artifact
is unavailable, explain the general mechanism and clearly identify what remains
unconfirmed about this project.

## Build a clear explanation

Lead with the direct answer in a sentence or short paragraph. Introduce only the
terms needed to understand it, defining unfamiliar ones in context. Prefer
concrete names and examples from the user's code to generic placeholders.

Choose a structure that fits the question:

- **Code walkthrough**: explain purpose and inputs, follow the meaningful steps,
  then describe outputs, side effects, and relevant failure paths. Group by behavior
  rather than narrating every line of syntax.
- **Error or surprising behavior**: connect the symptom to the mechanism and the
  evidence supporting that connection. Distinguish a confirmed cause from a
  hypothesis and explain how uncertainty could be resolved.
- **Concept**: give a plain-language definition, a small example, and the conditions
  under which the concept matters. Include limitations when they affect its use.
- **Tradeoff**: compare options against the user's actual constraints, state the
  assumptions, and explain why a recommendation follows. Avoid universal winners.

Use a small worked example when it makes an abstract idea concrete. Trace one
representative input through the important state changes. If using an analogy,
connect it back to the actual mechanism and mention where it stops being accurate.
Use a diagram, table, or interactive visual when relationships or comparisons are
materially easier to understand visually, following the environment's rendering
requirements. Do not force a visual into a simple answer.

## Stay grounded and within scope

Link relevant files or source passages near the claims they support. Quote only
the code necessary to explain the behavior. Prefer a compact example over copying
large files, and label illustrative code that has not been executed.

Explaining does not authorize edits, commits, running destructive commands, or
posting to external services. Use safe inspection to resolve factual questions;
if reproduction requires side effects outside the request, explain the limitation
and ask only if that action is necessary. A suggested fix may help explain an
error, but do not silently turn a walkthrough into an implementation or review.
If you notice a defect while explaining, mention it briefly with its evidence and
offer to fix it.

Keep the initial answer as short as the question allows. Include deeper details
when requested or needed to make the reasoning clear, and avoid unexplained jargon,
repeated summaries, and unrelated best-practice lists. State what remains uncertain
instead of filling gaps with plausible stories.
