# Design System

Concrete, implementable values that put [design_philosophy.md](design_philosophy.md)'s
principles into practice. Primitives only — feature-specific components
(claim cards, metric tiles, queue rows) are built from these in code, not
specified here.

> **We style exactly like Linear — for now.** Every value below mirrors what we
> extracted from the live Linear app; there is intentionally **no divergence** at
> this point. This file is the working summary;
> [ref/linear-design-reference.md](ref/linear-design-reference.md) is the full,
> authoritative source (tokens, the light/dark theme engine, motion, component
> structure) — go there for anything not spelled out here, and it wins on any
> question of "what does Linear actually do." We can loosen specific choices
> later (e.g. a Humana-appropriate accent hue) if the product needs it; until
> then, match Linear.

## 1. Colors

Linear builds its entire chrome on a **single blue-violet hue — `272` — in the
`lch()` color space**. Backgrounds, borders, and text are the *same hue* at
different lightness/chroma, never neutral gray plus a separate accent. That is
what makes it read as calm and unified. See §3 of the reference for the full
system and §3.5 for the theme-generation engine.

**Surfaces** (captured, `light / dark`)

| Role | Light | Dark |
|---|---|---|
| Base background | `#fcfcfd` | `#0f0f11` |
| App canvas (dark) | — | `lch(1.82% 0 272)` ≈ `#08080a` |
| Sidebar | `#f5f5f5` | `#090909` |
| Border (hairline) | `#e0e0e0` | `#1c1e21` |
| Secondary text | `#b0b5c0` | `#6b6f76` |
| Primary text | `#23252a` | `#ffffff` |

**Semantic token ramps** — everything styles against these; components never
reference raw colors. Values are injected at runtime by the theme engine.

- **Backgrounds — 5 elevation steps:** `--color-bg-primary` (canvas) →
  `secondary` → `tertiary` → `quaternary` → `quinary`.
- **Text — 4 emphasis steps:** `--color-text-primary` (strongest) →
  `secondary` → `tertiary` → `quaternary`.
- **Borders — 3 steps:** `--color-border-primary` (most visible) → `secondary`
  → `tertiary`.

**Neutral gray scale** — Radix-style 1→12 (light values): `--gray1`
`hsl(0,0%,99%)` … `--gray9` `hsl(0,0%,56.1%)` … `--gray12` `hsl(0,0%,9%)`.
Convention: 1–2 backgrounds, 3–5 fills, 6–8 borders, 9–10 solid, 11 low-contrast
text, 12 high-contrast text. Full table in the reference.

**Accent** — Linear uses **one accent color, derived in-hue** (blue-violet,
hue ~267–272), not a fixed brand hex; the theme engine tints controls/links from
it. Used sparingly, for the single primary action or state on a screen.

**Semantic — status colors** (`bg / border / text`, `light` then `dark`):

| Status | Light | Dark |
|---|---|---|
| Info | `hsl(208,100%,97%)` / `hsl(221,91%,93%)` / `hsl(210,92%,45%)` | `hsl(215,100%,6%)` / `hsl(223,43%,17%)` / `hsl(216,87%,65%)` |
| Success | `hsl(143,85%,96%)` / `hsl(145,92%,87%)` / `hsl(140,100%,27%)` | `hsl(150,100%,6%)` / `hsl(147,100%,12%)` / `hsl(150,86%,65%)` |
| Warning | `hsl(49,100%,97%)` / `hsl(49,91%,84%)` / `hsl(31,92%,45%)` | `hsl(64,100%,6%)` / `hsl(60,100%,9%)` / `hsl(46,87%,65%)` |
| Error | `hsl(359,100%,97%)` / `hsl(359,100%,94%)` / `hsl(360,100%,45%)` | `hsl(358,76%,10%)` / `hsl(357,89%,16%)` / `hsl(358,100%,81%)` |

Pattern: soft tinted bg + matching border + saturated text; bg sits ~6% L in
dark / ~97% L in light, text lifts to ~65% L in dark.

**Dark theme** is not a second palette — it's the same recipe from a different
base color: `base.L > 50` picks light vs. dark, and every derived color is a
mode-normalized delta (one positive magnitude steps darker in light, lighter in
dark). Dark uses larger lightness steps and heavier shadows/scrims. The full
engine, role vocabulary, and exact light/dark constants are in §3.5 of the
reference — that is the implementation model to build against.

## 2. Spacing

4px base rhythm — Tailwind's default scale, used as-is; consistent with Linear's
4px-multiple spacing (Linear's `--size` base unit is 16px = `space-4`).

| Token | Value | Tailwind class | Typical use |
|---|---|---|---|
| space-1 | 4px | `1` | Icon-to-label gap, tightest spacing |
| space-2 | 8px | `2` | Compact internal padding |
| space-3 | 12px | `3` | Default gap between related elements |
| space-4 | 16px | `4` | Default component padding |
| space-6 | 24px | `6` | Gap between distinct elements or groups |
| space-8 | 32px | `8` | Section spacing within a page |
| space-12 | 48px | `12` | Spacing between major page sections |
| space-16 | 64px | `16` | Page-level top/bottom margins |

Anything outside this list is a sign a layout needs reconsidering, not a
new spacing value invented.

## 3. Typography

**One face — Inter Variable** for everything (Linear uses a single face for
headings and body; `--font-display` = `--font-regular`). Monospace is **Berkeley
Mono** (fallbacks: SFMono, Consolas, Menlo). Base body size is **15px**, UI
chrome **13px** — dense, so a rep sees more without scrolling.

**Weights** (note *normal* is `450`, not 400): light `300` · normal `450` ·
medium `500` · semibold `600` · bold `700`.

**Type scale** (rem → px @16):

| Token | rem | px | Use |
|---|---|---|---|
| micro | .6875rem | 11px | Badges, meta, timestamps |
| mini | .75rem | 12px | Secondary labels |
| small | .8125rem | 13px | **Default UI chrome** — buttons, menus, rows |
| regular | .9375rem | 15px | **Body / editor text** |
| large | 1.125rem | 18px | Emphasized body, sub-headers |
| title3 | 1.25rem | 20px | Card titles, subsections |
| title2 | 1.5rem | 24px | Section headers |
| title1 | 2.25rem | 36px | Page / hero titles |

Weight and size carry hierarchy before color does. Full scale (incl. the
`…Plus` optical twins) in §2 of the reference.

## 4. Buttons

Three variants — primary, secondary, ghost — which also enforces the
one-primary-action-per-screen habit: only one primary button visible at a time.

**Variants** — primary uses the derived accent (white label); secondary is a
faint surface fill with a hairline border; ghost is transparent until hover.
Hover/press is painted by a separate **overlay layer** (an `::after` with
`--btn-overlay-shadow` / `--btn-overlay-shadow-hover`) so the button's own
background stays stable. State is driven by **data-attributes**
(`data-menu-open`, `data-active`) rather than modifier classes, and every hover
style is guarded by `@media (any-hover:hover) and (any-pointer:fine)`.

**Sizes** — label is `small` (13px / medium). Icon slots are the two fixed icon
steps: **14px** (small) and **16px** (normal).

**Icon-only** — square, icon centered, no visible label — always paired with an
`aria-label`. The same three variants apply.

**Focus** — a **1px** ring (`--focus-ring-width: 1px`) in the accent/focus color,
visible on keyboard focus (`:focus-visible`) — handled by React Aria's button
primitives, not custom-built. (Linear's ring is thin — 1px, not the usual 2–3px.)

**Corner radius** — 8px (see Borders & Radii). See §6 of the reference for the
full button/overlay structure.

## 5. Icons

Lucide only — no mixing icon libraries. Rendered thin (`strokeWidth={1.5}`) for
a refined line weight.

**Sizes** — Linear uses **two fixed steps**:

| Token | Size | Use |
|---|---|---|
| icon-sm | 14px | Dense contexts — queue rows, table cells, small buttons |
| icon-md | 16px | Default — buttons, list rows, inline with labels |

Larger one-off contexts (empty states, section headers) scale up per the
reference; there is no standing third size.

**Color** — icons follow the text ramp, defaulting to a quieter step
(`--color-text-tertiary`) so navigation and chrome don't compete with content.
Accent or semantic color is reserved for when the icon conveys an active state
or status (selected nav item, risk indicator).

**Usage** — in primary navigation an icon pairs with a label, never replaces
one. Decorative icons that don't carry meaning are avoided.

## 6. Borders & Radii

**Radius** — Linear centers on a **single 8px** corner radius, with a
fully-rounded token for pills/avatars. Controls (inputs, etc.) use their own
`--control-border-radius`.

| Token | Value | Use |
|---|---|---|
| radius | 8px (`--border-radius`) | **Default** — buttons, inputs, cards, panels, tabs |
| radius-control | `--control-border-radius` | Form controls (see reference) |
| radius-full | 9999px (`--radius-rounded`) | Pills, avatars, toggles |

Rounded enough to feel soft, not so much it reads as a consumer app.

**Borders** — background-color contrast is the default separator, not a border:
a surface sits as a subtle background shift (an elevation step), and dividers are
low-chroma hairlines of the same hue (`--color-border-*`), felt more than seen.

- Add a 1px border only when two adjacent surfaces are too close in value to
  read apart. Use `--color-border-primary` (most visible) down to `tertiary`.
- Never heavier than 1px. If something needs stronger separation than a hairline
  allows, that's a spacing or background problem, not a thicker border.

## 7. Motion & Elevation

**Motion** — Linear's captured durations and curves:

| Token | Value | Use |
|---|---|---|
| quick | `.1s` | Hover / press feedback |
| regular | `.25s` | Default UI transition |
| slow | `.35s` | Panels, larger moves |
| highlight in / out | `0s` / `.15s` | Highlight appears instantly, fades gently |

- Easing: an **`ease-out`** curve, always — **never `linear`**. If a moment needs
  a specific curve, use one from Linear's easing library
  (`ease-out-quad/cubic/quart/expo`, etc.) rather than inventing values — full
  set in §5 of the reference.
- Only `opacity` and `transform` animate — never layout-triggering properties.
- The whole app fades in once on boot (`bootstrap-fade-in`, 200ms ease-out)
  rather than popping in.
- Exception: an in-progress AI state (e.g. "thinking") may use a subtle,
  continuous indicator — functional signaling, not decoration.

**Elevation** — surfaces separate by **tone (a lightness step), not shadow**, per
the background-first rule. Shadows are theme-dependent and subtle (captured alpha
`0.03` light / `0.15` dark) and reserved for elements that truly float above
arbitrary content (modals, dropdowns, popovers, toasts). See §3.5 of the
reference for the elevation model and exact shadow/overlay constants.

## 8. Form Inputs

Generic fields only — text field, select, checkbox. Built on React Aria's
field primitives (`useTextField`, `useSelect`, `useCheckbox`), not
custom-rolled, per Engineering Constraints. The chat compose box is a
composite built from these later, in code, not specified here.

**Text field & select**

| Property | Value |
|---|---|
| Text | body (15px) |
| Background | a faint surface fill (`--color-bg-secondary`) |
| Border | 1px `--color-border-primary` hairline |
| Placeholder | quieter text step (`--color-text-tertiary`) |
| Radius | `--control-border-radius` (8px default) |

States:
- **Focus** — border lifts to the accent, plus the same **1px** focus ring used
  on buttons.
- **Disabled** — a flatter surface, `--color-text-tertiary` label, hairline
  border.
- **Invalid** — border becomes the error color, with an inline caption-sized
  message in the error text color below the field.

Select adds a 16px chevron-down icon (quiet text color) on the right; its open
panel floats with a subtle shadow and shares the control radius.

**Checkbox** — 16px square, 8px radius, hairline border by default. Checked:
accent background with a white 12px Lucide `Check` icon. Same 1px focus ring as
buttons and fields.

## 9. Badges & Status Indicators

Uses the status colors from §1 — soft tinted background, saturated text, never a
solid saturated fill.

**Badge**

| Property | Value |
|---|---|
| Text | micro (11px) / medium |
| Background | status `bg` |
| Border | status `border` (hairline) |
| Text color | status `text` |
| Radius | 8px (or the reference's smaller badge radius) |

**Dot** — a small circle in the status `text` color, no background or label —
for the tightest contexts (queue rows, table cells) where a full badge doesn't
fit.

**Mapping** (product-specific — the claim states this tool cares about):

| State | Status |
|---|---|
| ROI verified, claim covered, resolved | success |
| Missing referral, needs attention | warning |
| High denial risk, ROI missing or expired | danger (error) |
| Escalation in progress, neutral system notice | info |
| Not applicable, closed | neutral |

## 10. Panel, Tabs & Table

**Panel** — the general-purpose container primitive (a queue list, a workspace
section, a dashboard block). Background-first: a panel is a subtle surface shift
(an elevation step up from the canvas), not a bordered box by default.

| Property | Value |
|---|---|
| Background | one elevation step above the page (`--color-bg-secondary`) |
| Border | none by default; 1px `--color-border-*` hairline only if contrast alone can't separate it |
| Radius | 8px |
| Padding | space-4 (16px) default, space-3 (12px) for dense/compact panels |
| Shadow | none — flat, unless floating (dropdown/popover), which uses the subtle float shadow |

**Tabs** — in-panel view tabs (as in Linear's content-view header, e.g.
`Overview · Updates · Projects`). Linear signals selection with a **raised pill
fill**, not an underline.

| Property | Value |
|---|---|
| Tab text | small (13px / medium) |
| Shape | rounded pill, 8px radius |
| Active | filled with a surface one elevation step up (`--color-bg-secondary`), `--color-text-primary` label — the fill is the only active indicator, no underline |
| Inactive | no fill (transparent), `--color-text-tertiary` label |
| Hover (inactive) | a faint `bgSub`-level tint |

See §6 of the reference for the tab structure.

**Table** — hairline row dividers, not zebra striping — striping adds visual
noise across many rows; a 1px divider is quieter and still scannable.

| Property | Value |
|---|---|
| Row height | 40px default, 32px for dense/compact tables |
| Header text | small (13px / medium), `--color-text-tertiary`, no uppercase or added tracking |
| Header border | 1px `--color-border-*` beneath the header row |
| Row divider | 1px `--color-border-*` between rows |
| Row hover | one elevation step up as a background (interactive rows only) |
| Cell padding | space-3 (12px) horizontal, space-2 (8px) vertical |
| Cell text | body (15px) |

## 11. Session Tab Strip

The top bar's tab strip — our analogue to Linear's browser-style **window tab
bar** (see §6 of the reference). Each tab is one concurrent interaction a rep is
holding, not a page section. Only meaningful in the Interaction Workspace; empty
or hidden everywhere else.

Styled to match Linear's window tab bar exactly:

| Property | Value |
|---|---|
| Bar | full-width top bar (doubles as the drag region), height ≈ 44–48px, background = the darkest surface (`--color-bg-primary`), no bottom border |
| Tab shape | rounded pill, 8px radius, vertically centered, ~4–6px gap between pills |
| Tab width | fixed / uniform (~200–230px), truncating the member label with an ellipsis past that |
| Tab content | favicon-or-status-dot (16px) · ~8px gap · member label (13px), ~10–12px side padding |
| Active tab | filled with a surface one step above the bar (`--color-bg-secondary`), `--color-text-primary` label at medium (500) — the raised fill is the only active indicator, **no underline** |
| Inactive tab | no fill (transparent, blends into the bar), `--color-text-tertiary` label at normal (450); favicon still shown; faint tint on hover |
| New tab | a borderless ghost `+` icon button (~28px) after the last tab, quiet icon color |
| Overflow | horizontal scroll, no wrap — unbounded tab count |

> Note: the window-tab-bar pixel values in the reference (§6) are approximated
> from a screenshot, not extracted — treat them as close estimates. If exact
> numbers matter, capture the desktop app's tab element in DevTools.

**Lifecycle:** opens automatically on queue pickup, closes automatically
when the member leaves. The `+`/close controls exist for the edge case of
manually managing a stale tab, but aren't the primary way tabs open or close.

## 12. Sidebar Disclosure

For nav items with sub-items (currently just Dashboard, for the manager's
metric breakdowns). Expands inline within the sidebar — not a flyout —
matching how Linear nests items under sections like "Your teams."

| Property | Value |
|---|---|
| Trigger | `ChevronRight` (collapsed) / `ChevronDown` (expanded), `icon-sm`, quiet text color |
| Collapsed | default state |
| Sub-item indent | steps in ~19px (Linear's row-indent unit) beyond the parent |
| Sub-item text | small (13px / medium), vs. body for top-level nav items |
