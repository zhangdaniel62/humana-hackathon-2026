# Design Philosophy

## 1. Product Identity

Claim Assist is an operational tool embedded in a health-plan call center —
not a consumer product, not a marketing surface. It's used inside a shift,
not browsed. Three people touch it: a member talking to the AI, a rep who
inherits escalated calls, and a manager watching outcomes.

**What it draws from, in order:**

1. **Linear** — the primary reference, specifically its recent redesign
   philosophy: structure should be felt, not seen; nothing competes for
   attention it hasn't earned. We adopt Linear's styling **directly** — for
   how it's implemented (tokens, the light/dark theme engine, motion, and
   component structure, extracted from a live capture) see
   [ref/linear-design-reference.md](ref/linear-design-reference.md). That file
   is the source of truth: there are intentionally **no divergences right now**,
   and it wins on any question of styling. We may loosen specific choices later
   (e.g. a Humana-appropriate accent hue) if the product needs it.
2. **Codex** — a calm, technical, text-forward aesthetic for the
   conversational and agentic parts of the interface.
3. **Notion, Apple, Anthropic, xAI** — secondary references for typography,
   spacing, and restraint, used only where they don't conflict with Linear's
   approach.

**What it explicitly is not:** a generic AI dashboard. No hero sections, no
chat-bubble novelty, no decorative gradients signaling "this is AI." It
should read as an operational tool that happens to be powered by AI, not the
reverse.

## 2. Design Goals

- **Earn attention before taking it.** Chrome, navigation, and AI flourishes
  stay quiet by default; the claim, the answer, or the metric someone
  actually came for gets the visual weight.
- **Make structure felt, not seen.** Hierarchy comes from spacing, alignment,
  and type weight before it comes from borders or dividers.
- **Stay legible under time pressure.** A rep or manager should never have to
  slow down to figure out what they're looking at.
- **Keep grounding visible.** An AI-sourced answer carries its source in the
  same glance, not as a separate thing to go dig for.
- **Evolve, don't reinvent.** Once a pattern exists — a card, a table, a
  state — extend it for the next feature instead of introducing a new one.

## 3. Product Personality

The personality of the interface itself — not the AI's conversational tone,
which is a separate concern. One consistent character across member, rep,
and manager surfaces, drawn from Linear's redesign philosophy rather than
invented for this product.

- **Restrained.** Nothing performs for attention it hasn't earned. No
  flourish exists just to prove the interface is "AI-powered."
- **Neutral.** Timeless over trendy — quiet, low-chroma grays (Linear's
  single-hue neutrals) and consistent contrast rather than expressive color.
- **Considered.** Every element looks deliberately placed, not decorated.
  Precision reads as care, not sterility.
- **Unobtrusive.** The interface recedes so the actual work — the claim, the
  card, the metric — stays the subject.

## 4. Visual Principles

**Color**
- Neutral-first: quiet, warm grays carry structure and text. One accent
  color, used sparingly, for the single primary action or state on a screen.
- No mandated brand color — the palette is ours to define within that
  neutral-plus-one-accent approach.
- Color signals state (risk, success, escalation), not decoration, and never
  exists just to signal "this is AI."

**Typography**
- Inter Display for headings, Inter for body and UI text. Weight and size
  carry hierarchy before color or decoration do.

**Spacing & alignment**
- Whitespace is the primary tool for grouping and separation, before
  borders.
- Labels, icons, and buttons stay meticulously aligned — polish that's felt
  after a few minutes, not immediately noticed.

**Structure**
- Borders are a last resort, not a default. When used, they're soft contrast
  rather than hard lines.
- Rounded, soft edges over sharp geometry.

**Icons**
- Lucide only, used sparingly and small — they support a label, they don't
  replace one in primary navigation.

**Theming**
- Built light-first, but as one system that also produces a dark theme, not
  two separate designs. Linear does exactly this — one recipe run from a
  different base color, where `base.L > 50` decides light vs. dark and every
  derived color is a mode-normalized delta; see the theme-generation model in
  [ref/linear-design-reference.md](ref/linear-design-reference.md) (§3.5) for
  the concrete approach to copy.

## 5. Component Rules

- **Every data-bearing component defines all three states — empty, loading,
  and error — not just the happy path.** So much of this product is fed by
  an AI/backend that can be incomplete, ambiguous, or wrong; skipping a
  state isn't an oversight, it's a gap in the design.
- **Reuse the existing shape before inventing a new one.** A card, a table,
  a tile — once a pattern exists for a kind of data, the next feature
  extends it instead of introducing a visual one-off.
- **Components size to their content, not the space available.** No padding
  a card out to look substantial; if it earns three lines, it's three lines
  tall.
- **A component behaves the same everywhere it appears.** The same tile or
  card doesn't get reskinned per screen to fit a layout — the layout adapts
  to the component, not the reverse.

## 6. Interaction Philosophy

Centered on the conversation for the member and the rep — the member
talking to the AI, and the rep talking to the member once they pick up.
That's the most distinctive interaction in the product, and the rules below
apply to it specifically.

Two other surfaces are not conversational and sit outside this section's
core rules:

- **The rep's queue** — who's waiting, in the order they called, watched
  before a conversation starts. First in, first served, not ranked by
  urgency.
- **The manager's dashboard** — a separate surface entirely: the metrics
  from Design Goals, alerts, and a performance breakdown by rep (likely
  hardcoded for the demo).

Both follow the same restrained, functional-motion spirit as everything
else in this document — they're just ordinary list/table interactions, not
conversations.

- **State is always visible.** No one is left wondering if they were heard.
  Listening, thinking, and speaking are distinct, immediately legible states
  — for the member talking to the AI, and for the rep watching a call.
- **Interruption is instant.** Barging in stops queued audio immediately, no
  fade-out, no delay. The interface always yields to the person, never the
  AI.
- **Modality matches modality.** A rep responds in whatever medium the
  customer used — text if they typed, voice if they spoke. Neither side is
  forced to switch modes.
- **Motion is functional, not decorative.** Near-instant by default;
  animation exists only to clarify a state change, never to delight or to
  prove the interface is alive.
- **Handoff continues, it doesn't reset.** When a rep picks up an escalated
  call, the interaction picks up where the AI left off — the same thread,
  not a new one.
- **Rep and manager tools are keyboard-first.** Every action reachable
  without a mouse. Voice/text stays the member's primary mode, but the
  tools built for reps and managers assume someone working fast under
  pressure.

## 7. Engineering Constraints

- **Stack is fixed.** pnpm, Vite, React (TypeScript), Tailwind, React Aria,
  Lucide. No swapping frameworks or styling systems mid-project.
- **The frontend renders, it doesn't decide.** Claim, coverage, ROI, and
  readiness facts come from the backend as typed results. The frontend
  never infers or fabricates a fact the backend hasn't returned.
- **Interactive components are built on React Aria, not custom-rolled.**
  This is what makes the keyboard-first goal real rather than aspirational.
- **Chat and voice call are separate, parallel surfaces — not a fallback
  pair.** Chat is the first, primary surface for the demo. The voice call is
  a distinct option a member can choose, not a degraded mode entered only
  when voice fails.
