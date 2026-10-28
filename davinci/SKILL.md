---
name: davinci
description: >-
  Design and build distinctive, usable frontend interfaces. Use when creating or
  visually reworking websites, landing pages, dashboards, app screens, or
  components, or improving layout, typography, hierarchy, or interaction design.
  Not for backend work, UI logic fixes without design changes, or standalone
  illustration.
license: Apache-2.0
---

# Davinci

Create an interface with a clear visual point of view and a complete user journey.
Make the design specific to the brief, with usability carrying as much weight as
appearance. Distinctiveness comes from deliberate choices, not extra decoration.

Adapted and modified from Anthropic's
[frontend-design skill](https://github.com/anthropics/skills/tree/main/skills/frontend-design).
This version adds project integration, scope, and verification guidance; upstream
revision and modification details are in [NOTICE.txt](NOTICE.txt).

## Responsibility

Own visual direction and presentation: composition, typography, color, spacing,
responsive layout, motion, imagery, and interface copy. For code changes, Chimp
owns architecture, implementation quality, state logic, semantic and keyboard
accessibility, and functional checks. Apply this skill's visual decisions within that workflow;
do not duplicate the engineering plan, functional checks, or report. A design-only
proposal does not require implementation.

## Ground the design

Identify the product, audience, primary action, and content before choosing a look.
Use the user's brief, references, existing interface, and repository to establish
constraints. Ask only when a missing decision would materially change the result;
otherwise state a reasonable assumption and proceed. Do not invent a client history,
brand requirement, or commercial claim to justify a direction.

For an existing product, inspect its tokens, typography, components, and interaction
patterns. Extend that visual language for ordinary additions. Redesign only the
requested area, and preserve the surrounding identity unless a broader change is
requested. Explicit user preferences win over stylistic defaults in this skill.

For a new identity or an authorized redesign, derive choices from the subject:
its materials, culture, purpose, and audience. A scheduling tool and a music archive
should not inherit the same composition just because both run in a browser.

## Choose a direction before building

For meaningful design work, form a compact plan: palette and roles, type and scale,
layout and alignment, visual focal point, and interaction behavior. Reuse existing
tokens where appropriate. Scale this to the task; changing a component does not
require a new identity system or a separate approval round.

Check the plan against the actual content and user goal. If the same choices could
be pasted into almost any unrelated project, make the direction more specific.
Choose one defining visual idea and let supporting elements stay restrained.

## Design with intention

- **Hierarchy and composition**: organize around what people need to understand
  or do. Use spacing, scale, alignment, and grouping to communicate relationships.
  On a landing page, let the opening express what is characteristic of its subject;
  inside an application, prioritize the task rather than adding a marketing hero.
- **Typography**: choose families and weights for a reason, with readable body
  text and a coherent scale. One family can be enough. Tune line length, leading,
  and spacing for the content and viewport. Avoid collecting fonts for novelty.
- **Color**: define clear roles for surfaces, text, emphasis, and status. Meet
  WCAG AA contrast: 4.5:1 for body text, and 3:1 for large text, UI components,
  and focus indicators. An accent should direct attention, not make every element
  compete. Preserve established brand colors when working inside a product. Work
  within the product's existing themes; when it supports dark mode, design and
  check both.
- **Structure**: borders, labels, dividers, and numbering should explain content.
  Use numbering for a real sequence. Use cards for meaningful groups rather than
  wrapping every piece of content in identical containers.
- **Motion**: show the relationship between an action and its result. Keep passive
  animation purposeful and restrained, and respect reduced-motion preferences.
  Do not delay access to content for a reveal effect.
- **Imagery**: use assets that support the subject and composition. Prefer existing
  suitable assets; create new imagery only when it benefits the request and the
  environment supports it. Do not treat a missing asset as a broken image or claim
  a placeholder is finished artwork.

Do not default to the same card grid, gradient background, oversized heading,
monospace labels, or animated section entrances across unrelated briefs. None of
these choices is forbidden: use it when it serves this design or the user asks
for it. Do not substitute a new formula for the old one.

## Write the interface

Use the audience's vocabulary and concrete, credible content. Name actions by
what happens, keep the same terms throughout a journey, and explain errors with
a useful recovery step. Make empty states guide the next action. Avoid decorative
microcopy, filler slogans, and implementation details users do not need.

Use plausible sample content for mockups when necessary, but do not fabricate
customer endorsements, adoption figures, or working integrations as real claims.
Account for longer labels, missing content, and real data density in the layout.

## Carry the design into the interface

Use existing components, tokens, and styling conventions unless the requested
redesign changes them. Keep CSS specificity predictable and avoid competing
selectors. A visual refresh does not authorize replacing the stack or changing
unrelated behavior. Implement only when requested; otherwise deliver the proposal.

Design the presentation of the functional states: loading, empty, error, success,
and disabled. Make focus visible, controls distinguishable, and layouts usable
across viewports without hiding essential content or actions. Make touch targets
at least 24×24 CSS pixels, and about 44 for primary touch controls. Chimp covers
state logic, semantic elements, keyboard behavior, and functional verification.

Keep the interface fast. Load only the font weights you use, with `font-display`
and a similar fallback stack. Give images explicit dimensions to prevent layout
shift, serve them at appropriate sizes, and lazy-load those below the fold.
Prefer CSS transitions to a heavy animation library for small effects.

## Inspect and refine

For visual verification, inspect the rendered result when the environment permits,
at representative widths (roughly 375, 768, and 1280 pixels or wider), at 200%
zoom, and in relevant states using permitted tools. Check text wrapping, spacing, clipping, hierarchy,
asset loading, focus visibility, and the effect of real content. Do not claim visual
verification from source inspection or a successful build alone.

Critique the result against the brief: does the main action stand out, does the
subject come through, does each visual element earn its place, and is any sample
content kept from reading as real endorsements, figures, or integrations? Remove
competing accents or decoration that weakens the hierarchy. Make focused
corrections and recheck affected behavior rather than repeatedly redesigning
without evidence.

Include the design decisions, visual checks, and unverified presentation details
in the task's report. Visual inspection does not replace Chimp's functional checks
or expand publishing permission.
