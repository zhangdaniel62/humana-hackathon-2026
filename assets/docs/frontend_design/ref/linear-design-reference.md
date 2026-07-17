# Linear — Design Reference

Distilled from decoded HAR captures of the live Linear web app — both the **dark**
and **light** themes (`whole_site.har` / `whole_site_light.har`, ~1045 requests
each: the rendered document, `Root-*.css`, 66 stylesheets, and the JS bundles incl.
`LoadApplicationLayout`, `ThemeProvider`, and `lightThemeRefresh`). This is a
**reference for how Linear builds their UI** — tokens *and* patterns to borrow
when building Claim Assist.

It covers **both how things are colored and how they are shaped/structured**:
typography and the type scale (§2), the color system and the light/dark
theme-generation engine (§3), spacing · radius · layout · sizing (§4), motion
(§5), and component/structural patterns (§6). Shape, size, and motion are
**identical across both themes**; only color values swap.

It is not Linear's source: component CSS is compiled by StyleX into atomic class
hashes and theme colors are injected at runtime, so what survives cleanly is the
**token + role layer** plus the signature global rules. Values are verbatim from
the captures unless noted.

---

## 1. Signature characteristics (what makes it look like Linear)

These are the details that carry the "Linear feel" more than any single color:

- **One hue, everywhere.** The whole chrome is built on a single blue-violet
  hue **`272`** in the `lch()` color space. Backgrounds, borders, and text are
  the *same hue* at different lightness/chroma — never neutral gray mixed with a
  separate accent. This is why it reads as calm and unified.
- **Near-black, not black.** The dark canvas is `lch(1.82% 0 272)` (~`#08080a`),
  never `#000`. Surfaces are separated by tiny lightness steps, not borders.
- **Thin 1px focus ring**, not the usual 2–3px browser ring. `--focus-ring-width: 1px`.
- **Hairline borders** at very low chroma of the same hue (`lch(13% 1.38 272)`),
  so dividers are felt more than seen.
- **`450` "normal" font weight** (not `400`). Inter Variable is set a touch
  heavier than default for body text — subtly crisper on dark backgrounds.
- **Small type.** Body copy is `.9375rem` (15px); most UI chrome is 13px. Dense,
  information-first.
- **8px corner radius** as the default; fully-rounded (`9999px`) for pills/avatars.
- **Fast, short motion.** Default transition `.25s`, hovers `.1s`. Easing is
  almost always an `ease-out` curve, never linear.

---

## 2. Typography

```css
/* Families */
--font-regular:  "Inter Variable", "SF Pro Display", -apple-system,
                 BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--font-display:  var(--font-regular);          /* same face, used at title sizes */
--font-monospace:"Berkeley Mono", "SFMono Regular", Consolas, Menlo, monospace;
--font-emoji:    "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji";

/* Weights — note "normal" is 450, not 400 */
--font-weight-light:    300;
--font-weight-normal:   450;
--font-weight-medium:   500;
--font-weight-semibold: 600;
--font-weight-bold:     700;
```

### Type scale (rem → px @16)

| Token                     | rem       | px    | Typical use                     |
|---------------------------|-----------|-------|---------------------------------|
| `--font-size-micro`       | .6875rem  | 11px  | badges, meta, timestamps        |
| `--font-size-mini`        | .75rem    | 12px  | secondary labels                |
| `--font-size-small`       | .8125rem  | 13px  | **default UI chrome** (buttons, menus, rows) |
| `--font-size-regular`     | .9375rem  | 15px  | **body / editor text**          |
| `--font-size-large`       | 1.125rem  | 18px  | emphasized body, sub-headers    |
| `--font-size-title3`      | 1.25rem   | 20px  | section titles                  |
| `--font-size-title2`      | 1.5rem    | 24px  | page titles                     |
| `--font-size-title1`      | 2.25rem   | 36px  | hero / large headings           |

> Each size has a `…Plus` twin (e.g. `--font-size-smallPlus`) held at the same
> value — a hook for optical bumps without touching the base scale. `micro` is
> pixel-snapped with `round(up, .6875rem, 2px)` so 11px text stays crisp.

---

## 3. Color

Linear composes its themes at runtime in the **`lch()`** color space from a base
background + a single hue, then derives surfaces/borders/text by shifting
lightness and chroma. Hard hex/hsl values below are the ones the capture pinned
directly; treat `lch` entries as the live dark-theme values.

### 3.1 Semantic token architecture (the design-system API)

This is the authoritative token set the app writes onto `:root` / `body` at boot
(from `LoadApplicationLayout`). Everything else styles against these — components
never reference raw colors. **Values are injected at runtime by the theme engine
(`ThemeProvider`), which formats numeric palettes into `lch()`** (with P3/RGB
fallbacks via `@supports`). The *structure* is the reusable part:

```css
:root {
  /* Backgrounds — 5 elevation steps, primary = canvas, up = more raised */
  --color-bg-primary;    --color-bg-secondary;  --color-bg-tertiary;
  --color-bg-quaternary; --color-bg-quinary: 0;   /* quinary is an alpha slot */

  /* Text — 4 emphasis steps, primary = strongest */
  --color-text-primary;  --color-text-secondary;
  --color-text-tertiary; --color-text-quaternary;

  /* Borders — 3 steps, primary = most visible hairline */
  --color-border-primary; --color-border-secondary; --color-border-tertiary;

  --ai-selection-bg;               /* highlight for AI-touched ranges */
  --linear-find-highlight-color;   /* in-page find match             */
  --control-border-radius;         /* inputs/controls (see §4)        */
}
body {
  --content-bg-color;   --header-color;   --header-height; /* px */
  --focus-color;        --selection-bg;                    /* text selection */
}
```

**Design lesson:** three ramps (bg ×5, text ×4, border ×3) cover the entire UI.
Build Claim Assist's palette as these same named ramps and components stay
theme-agnostic. The concrete captured values below show what one resolved dark
theme looks like.

### 3.2 Canvas & surfaces (dark theme, as captured)

```css
--bg-color:          lch(1.82% 0 272 / 1);     /* app canvas (~#08080a)        */
--bg-sidebar-color:  lch(1.82% 0 272 / 1);     /* sidebar = same as canvas     */
--bg-base-color:     lch(4.52% 0.3 272);       /* raised surface / panel        */
--bg-border-color:   lch(13.16% 1.38 272 / 1); /* hairline divider              */
```

Light/dark endpoints the theme interpolates between:

| Role              | Light      | Dark       |
|-------------------|------------|------------|
| Base background   | `#fcfcfd`  | `#0f0f11`  |
| Sidebar           | `#f5f5f5`  | `#090909`  |
| Border            | `#e0e0e0`  | `#1c1e21`  |
| Content (text)    | `#b0b5c0`  | `#6b6f76`  |
| Content highlight | `#23252a`  | `#ffffff`  |

> **The hue `272` is the whole identity.** To re-skin for Claim Assist, keep this
> exact lch structure and swap `272` for a Humana-appropriate hue — every surface,
> border, and shade moves together automatically.

### 3.3 Neutral gray scale (Radix-style 1→12, light theme values)

```css
--gray1:  hsl(0,0%,99%);    --gray7:  hsl(0,0%,85.8%);
--gray2:  hsl(0,0%,97.3%);  --gray8:  hsl(0,0%,78%);
--gray3:  hsl(0,0%,95.1%);  --gray9:  hsl(0,0%,56.1%);
--gray4:  hsl(0,0%,93%);    --gray10: hsl(0,0%,52.3%);
--gray5:  hsl(0,0%,90.9%);  --gray11: hsl(0,0%,43.5%);
--gray6:  hsl(0,0%,88.7%);  --gray12: hsl(0,0%,9%);
```
Convention (Radix): 1–2 backgrounds, 3–5 component fills, 6–8 borders,
9–10 solid/handles, 11 low-contrast text, 12 high-contrast text.

### 3.4 Status colors (semantic, light / dark pairs)

Each status ships a `bg` / `border` / `text` triad for both themes — the standard
"tinted callout" pattern (soft bg, matching border, saturated text).

| Status  | Light bg / border / text                          | Dark bg / border / text                           |
|---------|---------------------------------------------------|---------------------------------------------------|
| Info    | `hsl(208,100%,97%)` / `hsl(221,91%,93%)` / `hsl(210,92%,45%)` | `hsl(215,100%,6%)` / `hsl(223,43%,17%)` / `hsl(216,87%,65%)` |
| Success | `hsl(143,85%,96%)` / `hsl(145,92%,87%)` / `hsl(140,100%,27%)` | `hsl(150,100%,6%)` / `hsl(147,100%,12%)` / `hsl(150,86%,65%)` |
| Warning | `hsl(49,100%,97%)` / `hsl(49,91%,84%)` / `hsl(31,92%,45%)`   | `hsl(64,100%,6%)` / `hsl(60,100%,9%)` / `hsl(46,87%,65%)`   |
| Error   | `hsl(359,100%,97%)` / `hsl(359,100%,94%)` / `hsl(360,100%,45%)` | `hsl(358,76%,10%)` / `hsl(357,89%,16%)` / `hsl(358,100%,81%)` |

Pattern to reuse: **bg is ~6% L in dark / ~97% L in light; text stays ~45% L in
light and lifts to ~65% L in dark** so it reads on the tinted surface.

---

### 3.5 Theme-generation model (how light *and* dark are produced)

Light and dark aren't two hand-authored palettes — they're the **same recipe run
from a different base color** (from `lightThemeRefresh.js`, the theme engine).
Understanding this is what lets you regenerate the whole thing for Claim Assist.

**The rule that decides everything:** a theme takes a `base` color, an `accent`,
and a `contrast` amount. Whether it's light or dark is derived, not declared:

```
isLight = base.L > 50          // base lightness over 50%
isDark  = !isLight
```

**One set of role definitions yields both themes** because every derived color is
a *mode-normalized delta* off the base. The core adjuster is:

```
u = (isLight ? -1 : +1) * contrast / 30
f(color, {l: d}) → shift lightness by d * u
```

So a **single positive magnitude steps *toward the foreground*** — darker in
light mode, lighter in dark mode — automatically. Authors write one number
(e.g. hover = `{l: 5}`) and it does the right thing in either theme. The
`contrast` value scales all steps at once (the user's contrast slider).

**Mode-dependent constants** (the places light and dark genuinely diverge),
captured verbatim as `light / dark`:

| Thing                     | Light        | Dark          | Note                                   |
|---------------------------|--------------|---------------|----------------------------------------|
| Shadow color alpha        | `0.03`       | `0.15`        | dark uses heavier black shadows        |
| Modal overlay alpha       | `0.25`       | `0.40`        | ×opacity, clamped ≤ 0.8 (dark scrim heavier) |
| Scroll track              | opaque white | ~transparent  | `[100,0,0,0]` vs `[0,0,0,.004]`        |
| Focus surface step        | `l:4`        | `l:6.5 c:1`   | dark needs a bigger jump + a little chroma |
| Sidebar link hover        | `l:2.8`      | `l:5 c:.75`   | ″                                      |
| Sidebar link active       | `l:4.9`      | `l:10 c:1.5`  | ″                                      |

Rule of thumb: **dark mode uses larger lightness steps (and adds a touch of
chroma)** for the same interaction state, because equal-sized steps read as
smaller on a dark surface.

**The internal role vocabulary** the engine emits — richer than the public
`--color-*` vars, and the real map of "every kind of surface/line/label":

- **Surfaces:** `bgSub` · `bgBase` · `bgShade` · `bgSelected` · `bgFocus`
  (each with a `…Hover`). These collapse into the public
  `--color-bg-primary…quinary`.
- **Borders — 3 weights, each in solid/alpha and a thin variant:** `bgBorder`,
  `bgBorderFaint`, `bgBorderSolid` (× `Hover`, × `Thin`, × `Alpha`). Map to
  `--color-border-primary…tertiary`.
- **Text/labels:** `labelTitle` (strongest) · `labelBase` · `labelMuted` ·
  `labelFaint` · `labelLink`. Map to `--color-text-primary…quaternary`.
- **Controls:** `controlPrimary` (+`Hover`, +`Label`), `controlSecondaryHighlight`,
  `controlLabel`, `controlSelectLabel`.
- **Chrome:** `sidebarLinkBg`/`…Active`, `bgModalOverlay`, `shadowColor`,
  `focusColor`, `scrollBackground`.

**Functional color anchors** `[L, C, H]` (status/accent hues, mode-tuned where
noted): purple `[48, 59, 288]` · blue `[80, 70, 267]` · info-cyan
`[67.5, 45, 210]` · green `[68, 64, 142]` light / `[60, 64, 142]` dark · amber
`[66, 80, 48]` / `[58, 73, 29]`.

> **For Claim Assist:** define your palette once as these roles off a single
> base + brand accent, and both themes fall out. Don't hand-pick a separate dark
> palette — pick a dark *base* and reuse the same role deltas.

## 4. Spacing, radius & layout

> **Note — this section and §5–6 are theme-independent.** Shape, size, structure,
> and motion are identical in light and dark; only the color *values* in §3 swap.
> Radii, type scale, spacing, icon sizes, focus-ring width, the `data-*` state
> model, and easings below apply to both themes unchanged.


```css
--size:            16px;     /* base unit; spacing is multiples of this   */
--border-radius:   8px;      /* default corner radius                     */
--radius-rounded:  9999px;   /* pills, avatars, toggles                   */
--sidebar-width:   244px;    /* primary nav width                         */
--scrollbar-width: 12px;     /* custom scrollbar (0 when overlaid)         */

--focus-ring-width:   1px;                                            /* thin! */
--focus-ring-outline: var(--focus-ring-width) solid var(--focus-ring-color);
```

Editor / list rhythm tokens seen in the bundles (useful for dense rows):
`--editor-block-spacing`, `--editor-block-radius`, `--editor-list-inset`,
`--settings-list-view-item-padding-x/y`, `--settings-list-view-item-radius`,
`--line-number-width`, `--indent-offset`. Row indentation steps in ~19px units
(`--indent-current: 19px`).

Icon sizes are two fixed steps: **14px** (`small`) and **16px** (`normal`).

---

## 5. Motion

```css
/* Durations */
--speed-highlightFadeIn:  0s;      /* highlight appears instantly           */
--speed-highlightFadeOut: .15s;    /* …and fades out gently                  */
--speed-quickTransition:  .1s;     /* hover / press feedback                 */
--speed-regularTransition:.25s;    /* default UI transition                  */
--speed-slowTransition:   .35s;    /* panels, larger moves                   */
```

Full easing set is available; the app leans on the **`out`** curves for
enter/settle motion. Most-used defaults:

```css
--ease-out-quad:  cubic-bezier(.25, .46, .45, .94);
--ease-out-cubic: cubic-bezier(.215, .61, .355, 1);
--ease-out-quart: cubic-bezier(.165, .84, .44, 1);
--ease-out-expo:  cubic-bezier(.19, 1, .22, 1);   /* dramatic settle          */
--ease-in-out-cubic: cubic-bezier(.645, .045, .355, 1); /* symmetric moves     */
```

Also captured — `in-quad/cubic/quart/quint/expo/circ`,
`out-quint/circ`, and `in-out-quad/quart/quint/expo/circ` — a complete Penner
easing library, so any interaction can pick a curve without inventing one.

Rule of thumb from the capture: **things enter fast and decelerate** (ease-out),
**hover states are ~100ms**, **nothing uses `linear`.**

---

## 6. Component patterns (from the StyleX bundles)

Component CSS is compiled to atomic classes, but the *structure* is legible:

- **Buttons** define `iconSmall` (14px) / `iconNormal` (16px) icon slots and use
  a `--btn-highlight-bg` / `--btn-highlight-color` pair driven by
  `[data-menu-open=true]` and `[data-active=true]` state attributes rather than
  extra classes. A separate **overlay layer** (`:after` with
  `--btn-overlay-shadow` / `--btn-overlay-shadow-hover`) paints the hover/press
  shine, keeping the button's own background stable.
- **State via data-attributes**, not modifier classes: `data-menu-open`,
  `data-active`, `data-menu-open` on ancestors cascade to children. Cheap to
  toggle from JS, no class bookkeeping.
- **CSS `@layer reset, base;`** is declared up front so component styles can't be
  accidentally out-specified by resets.
- **`@media (any-hover:hover) and (any-pointer:fine)`** guards every hover style —
  hover effects never fire on touch devices.
- **Toasts, tabs, list cells** each carry their own logical-property tokens
  (`margin-start/end`, `padding-x/y`) so they mirror correctly in RTL.

### Global base layer (from `LoadApplicationLayout`, `@layer app.base`)

```css
/* Every interactive element gets an app-controlled cursor token… */
a, button, input[type="checkbox"], select, *[onclick] { cursor: var(--pointer); }
/* …but genuinely external links (not linear.app/.dev, mailto, _blank) get a
   real pointer — internal "links" are SPA nav, so they don't. */
a[href*="//"]:not([href*="linear.app"]):not([href*="linear.dev"]),
a[href^="mailto:"], a[target="external"], a[target="_blank"] { cursor: pointer; }

a { color: var(--…link); transition: color <quick>; }        /* links animate color   */
body::selection { background: var(--selection-bg); }          /* themed text selection */

/* App boots hidden, then fades in once — no flash of unstyled/half-loaded UI */
@keyframes bootstrap-fade-in { from { opacity: 0; } }
body.<loaded> #root { animation: bootstrap-fade-in 200ms ease-out; }
```

Takeaways worth copying: a single **`--pointer`** token lets the app switch all
cursors at once (e.g. during drag); **internal nav isn't a real `pointer`**; and
the whole app **fades in over 200ms** rather than popping in. There's also a
`@media print` block that hides everything except `.section-to-print` — the
pattern for printable claim summaries.

---

### Window tab bar (desktop) — *approximated from a screenshot*

> ⚠️ **Not extracted — eyeballed from a screenshot of the desktop (Electron)
> app.** This chrome doesn't render in a browser capture, so unlike the rest of
> this doc these are *observed proportions*, not captured token values. Pixel
> sizes are rounded estimates; the tokens referenced (radius, type, color ramps)
> are the app's real ones, reused here for consistency.

The browser-style tab strip is the top, full-width bar that also serves as the
OS **draggable title bar**. Layout, left → right:

```
[● ● ●]   [⟲] [‹] [›]   [◧ Overview            ]  [▷ Linear              ]  [+]
 traffic   history/nav    ACTIVE tab (filled)        inactive tab (no fill)   new
 lights    (desktop only)                                                     tab
```

**Bar**
- Full width; height ≈ **44–48px**. Background = the app canvas, the darkest
  surface (`--color-bg-primary`, ~`#08080a` in dark). No bottom border — the
  content header below is separated by tone, not a line.
- Left inset clears the macOS traffic lights (~**80px**) when not fullscreen.

**Nav cluster** (desktop only, left of the tabs)
- History/clock, back `‹`, forward `›` — ghost **icon buttons**, ~**28px**
  square, muted icon color (`--color-text-tertiary`), no background until hover.
  Same ghost-button style as the rest of the app's icon buttons.

**Tabs** — rounded-rectangle pills, vertically centered in the bar
- Corner radius ≈ **8px** (the app's default `--border-radius`).
- Width looks **fixed/uniform** per tab (~**200–230px**), not content-hugging;
  they'd truncate rather than grow. Height ≈ **32–36px**. Small gap (~**4–6px**)
  between pills.
- Internal layout: `favicon (16px) · gap ~8px · label`, left-aligned, with
  padding ~**10–12px** each side. Label is chrome-sized (**~13px**,
  `--font-size-small`).
- **Active tab** (`Overview`): filled with a surface **one elevation step above
  the bar** (reads like `--color-bg-secondary`/`bgBase`), giving a raised look;
  label in near-white `--color-text-primary`, weight ~**medium (500)**. This
  fill is the *only* active indicator — no underline, no accent bar.
- **Inactive tab** (`Linear`): **no fill** (transparent, blends into the bar);
  label dimmer (`--color-text-tertiary`), weight ~**normal (450)**; favicon
  still shown. (Hover almost certainly adds a faint fill — not visible in a
  static shot; assume a `bgSub`-level tint.)

**New-tab `+`**
- Borderless icon button after the last tab, ~**28px** square, muted icon color —
  same ghost-button treatment as the nav cluster.

**How to reuse it:** it's built entirely from tokens already in this doc — 8px
radius, 13px chrome type, the bg-elevation ramp for active vs. inactive, the
text ramp for label emphasis, and the standard ghost icon button. The only
"new" idea is **active = a raised fill, inactive = flat**, with uniform-width
pills that truncate.

## 7. Cheat-sheet for Claim Assist

If you want the Linear feel quickly:

1. Pick **one brand hue**, express all chrome as `lch(L C <hue>)` — surfaces at
   very low L, borders at slightly higher L + tiny C, text by raising L.
2. Body text **15px / weight 450**; UI chrome **13px**; titles at 20/24/36.
3. **8px** radius default, **9999px** for pills/avatars.
4. **1px** focus ring in the brand hue.
5. Transitions **.25s ease-out**; hovers **.1s**; never `linear`.
6. Status callouts: soft tinted bg + matching border + saturated text, with the
   light/dark lightness rules in §3.4.
7. State with `data-*` attributes; guard hover with `any-hover:hover`.
