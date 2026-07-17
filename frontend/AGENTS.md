# AGENTS.md — Frontend state of the world

Working context for agents on the Claim Assist frontend. Read this before
exploring the codebase; update it (append/edit) at the end of a session when
told to. The design authority is `assets/docs/frontend_design/` at the repo
root — `design_system.md` for tokens/primitives, `design_philosophy.md` for
principles, `ref/linear-design-reference.md` as the extracted-from-Linear
source of truth. **We currently style exactly like Linear, no divergence.**

## Stack

pnpm · Vite · React 19 (TypeScript, strict, `erasableSyntaxOnly`) ·
Tailwind v4 (CSS-first config via `@theme` in `src/index.css`) ·
react-aria-components (RAC) · lucide-react · react-router-dom v7.
Path alias `@/` → `src/`. Commands: `pnpm dev` / `pnpm build` (runs `tsc -b`
first) / `pnpm lint`.

## Design tokens (`src/index.css`) — the only place colors/type/motion live

- **Colors are semantic ramps, Linear-style, all `lch()` hue 272 (light theme):**
  `--color-bg-primary…quinary` (5 elevation steps; primary = canvas),
  `--color-text-primary…quaternary` (4 emphasis steps),
  `--color-border-primary…tertiary` (3 hairline steps),
  `--color-accent` / `--color-accent-hover` (blue-violet, ≈ Linear `#5e6ad2`),
  status triads `--color-{info,success,warning,danger}` + `-bg` + `-border`.
  Utility classes therefore read `bg-bg-secondary`, `text-text-tertiary`,
  `border-border-primary`, etc. Components never use raw colors.
- **Dark theme:** not implemented yet, deliberately — the ramps are semantic
  so a dark base can be dropped in later (see reference §3.5).
- **Type:** Inter (Google variable font loaded in `index.html`); `font-normal`
  is **450**, not 400. Scale: `text-micro` 11 / `mini` 12 / `small` 13 (default
  UI chrome) / `regular` 15 (body) / `large` 18 / `title3` 20 / `title2` 24 /
  `title1` 36. Titles carry weight 600 via the token.
- **Radius:** `rounded-md` = 8px is THE radius; `rounded-sm` = 4px only for the
  smallest chrome (badges, tiny close/chevron buttons); `rounded-full` pills.
- **Motion:** default transition duration is 0.1s with a custom `--ease-out`
  (never `linear`). Larger moves use `duration-[250ms]`. Keyframes `pop-in` /
  `pop-out` (150ms fade + 2px rise) exist for floating surfaces via
  `data-entering:animate-pop-in data-exiting:animate-pop-out` on RAC overlays.
  The app fades in once on boot (`bootstrap-fade-in`, 200ms, on `#root`).
- **Focus:** a single global rule styles `:focus-visible` and RAC's
  `[data-focus-visible]` with a 1px accent outline, offset 2px. **Do not add
  per-component `outline-*` utilities**; add `outline-none` only where a fill
  highlight replaces the ring (e.g. menu items), or a variant utility like
  `data-focus-visible:-outline-offset-1` to tweak locally.
- **Elevation:** tone separates surfaces, not shadow. `shadow-float` is only
  for true floating elements (popover/tooltip/menu) and pairs with a hairline
  border + `bg-bg-primary`.

## App structure

- `src/main.tsx` → `AuthProvider` → `RouterProvider`.
- Routes (`src/app/router.tsx`): `/signin` and `/member` are public;
  everything else is under `RequireAuth` + `SessionsProvider` + `AppShell`:
  `/` Dashboard, `/metrics/:metricSlug`, `/queue`, `/workspace`.
- **Auth (`src/lib/auth*.ts[x]`) is demo-only**: any non-empty
  username/password signs in; username containing "manager" → Manager role,
  else Representative. Persisted in `sessionStorage`. (These lib files were
  reconstructed from call sites after an accidental revert wiped the
  uncommitted originals — behavior is plausible, not verbatim.)
- `src/lib/api.ts`: typed `apiFetch` against `VITE_API_BASE_URL`
  (default `http://localhost:8000`). Nothing calls it yet. The frontend
  renders backend facts; it never infers them.
- `src/lib/cn.ts`: plain truthy-join, **no tailwind-merge** — later classes
  don't override earlier conflicting ones, so keep call sites conflict-free.
- Sessions (`src/app/sessions*.ts[x]`): in-memory list of concurrent member
  interactions; `openSession` is meant to be called on queue pickup.

## Operations dashboard

- The dashboard is five route-backed views sharing one filter context: `/` is
  the overview; `/metrics/average-handle-time`,
  `/metrics/first-call-resolution`, `/metrics/repeat-contacts`, and
  `/metrics/preventable-denials` are focused views. `DashboardFiltersProvider`
  sits above these routes, so date range and Weekly/Monthly selection survive
  client-side tab navigation (a full page reload intentionally resets them).
- `src/lib/operationsDashboard.ts` owns the typed response/query contract and
  is the single data-source swap point. It currently calls
  `buildMockDashboardResponse`; replace only `fetchOperationsDashboard` when
  the real `GET /api/operations/dashboard` endpoint is ready.
- `src/lib/mockOperationsDashboard.ts` is a deterministic client-side stand-in:
  it filters weekly source rows, re-buckets by month, and derives aggregates
  from integer counts. UI copy must continue to label these values and the
  comparison baseline as synthetic.
- `DashboardPageFrame` owns filters, loading skeleton, empty-range handling,
  and refetch dimming. The overview/focused tabs should stay presentation-only
  consumers of `OperationsDashboardResponse`.
- Charts are hand-written responsive SVG components. `ChartCard` requires an
  accessible table for every chart and exposes the chart/table toggle; keep
  legends, hover tooltips, null handling, and the explicit "Not measured"
  caveats when changing metrics. Do not back-calculate counts from rounded
  rates or call recorded interventions a true prevented-denial outcome.

## Layout decisions (the Linear "content card" shell)

- `AppShell`: whole window chrome is one surface (`bg-bg-secondary`) —
  244px sidebar + top bar sit on it. Page content is a **raised card**:
  `bg-bg-primary`, `rounded-md`, hairline `border-border-secondary`,
  margins `mt-2 mr-2 mb-2` (uniform 8px; flush left toward the sidebar).
  The card itself scrolls (`overflow-y-auto`).
- **No breadcrumbs / no page title in the outer chrome.** `TopBar` renders
  *only* the session tab strip, and only on `/workspace` with ≥1 open
  session; otherwise it returns null. Orientation on metric pages relies on
  the sidebar's active sub-item; if that's ever insufficient, put a crumb
  inside the card header, not in the chrome.
- **`PageHeader` (`src/components/PageHeader.tsx`)** is the in-card header:
  sticky 44px bar, 13px medium title, hairline divider below, optional `(i)`
  ghost icon button whose RAC Tooltip (hover/focus, pop-in animation) holds
  the page description. Pages render `<PageHeader/>` then a `p-6` content
  region. Grow an actions slot here if a page needs right-side controls.
- Sidebar: top-level nav rows are 15px body text with 16px/1.5 Lucide icons
  (icon `text-text-tertiary`, accent only when active); active row fill is
  `bg-bg-quaternary`, hover `bg-bg-tertiary`. Sub-items (Dashboard metrics)
  are 13px medium, indented `pl-[27px]` (parent 8px + Linear's 19px unit).
- The Dashboard disclosure animates with the CSS grid trick:
  outer `grid` + `grid-rows-[0fr↔1fr]` + opacity, 250ms ease-out, inner
  `min-h-0 overflow-hidden` wrapper; collapsed content is `inert`.
- Session tab strip (`SessionTabStrip`): Linear window-tab pills — uniform
  `w-52`, `h-8`, active = raised `bg-bg-primary` fill + medium text (no
  underline anywhere), hover-revealed close X, ghost `+` opens a blank
  local session (edge-case manual management; real tabs open on queue pickup).

## UI primitives (`src/components/ui/`, exported from `index.ts`)

Button (primary/secondary/ghost; h-8 default, h-7 sm; iconOnly squares;
13px medium labels) · Input (RAC TextField; 15px text, `bg-bg-secondary`
fill, focus lifts border to accent) · Panel (`bg-bg-secondary`, p-4 or p-3
dense, optional hairline) · Badge (11px medium, tinted bg + matching border +
saturated text; never solid fills) + Dot · Tabs (selection = raised pill
fill `bg-bg-secondary`, no underline) · Table (13px tertiary header, 15px
cells, 40px rows, hairline dividers, no zebra).

Status→variant mapping (design_system.md §9): resolved/covered = success;
needs-attention = warning; high-risk/ROI-missing = danger; escalation/system
notice = info; closed/n-a = neutral.

## Gotchas discovered

- **`erasableSyntaxOnly` is on**: no TS parameter properties
  (`constructor(public x…)`) — declare fields explicitly.
- Tailwind v4 resets: `--text-*`, `--color-*`, `--radius-*`, `--ease-*`,
  `--shadow-*`, `--font-weight-*` are all `initial`-ed in `@theme`; only the
  tokens defined there exist. Old-style classes (`text-body`, `neutral-500`,
  `rounded-lg`…) silently produce nothing — grep for them after refactors.
- RAC state styling uses data attributes (`data-hovered`, `data-selected`,
  `data-entering`…) — never `:hover` on RAC components (plain elements like
  NavLink still use `hover:`).
- react-router `NavLink`/`Link` outside `AriaRouterProvider` (e.g. public
  pages) must be the react-router ones; RAC `Link href` there would hard
  navigate.
- Session strip lives inside `SessionsProvider`; `TopBar` calls
  `useSessions()`, so it must stay under the provider in `AppShell`'s tree.

## Verifying changes

Run `pnpm build` and `pnpm lint`, then drive the real app with Playwright after
starting `pnpm dev --host 127.0.0.1`. Sign in with `daniel`/anything. For
dashboard changes, exercise all five routes through the sidebar, change the
Weekly/Monthly bucket and confirm it persists across client-side navigation,
toggle at least one chart to its accessible table, inspect browser console
warnings/errors, and screenshot the overview plus affected focused views.
Actually inspect every screenshot for clipping, overlap, active-nav state, and
readability; a DOM-only pass is insufficient.

Last verified 2026-07-17 at `83141abd`: build and lint passed; all five
dashboard views, shared bucket persistence, the AHT table fallback, and a clean
browser console passed Playwright inspection at the normal desktop viewport.
Vite currently emits only its advisory warning that the main minified JS chunk
is about 538 kB; plan route-level code splitting before this grows materially.

## Known state / open items

- The five-view operations dashboard is implemented against deterministic
  synthetic mock data. Queue and workspace remain shells; there is still no
  queue table, workspace conversation UI, or member chat.
- `/member` is a placeholder ("Talk to Claim Assist") with a staff sign-in
  link; the member chat surface goes there.
- Nothing populates sessions yet except the strip's `+` button.
- Live backend integration is not started. `apiFetch` remains unused by the
  dashboard; its typed contract and mock swap point are ready for the real
  endpoint.
- Berkeley Mono (design mono face) isn't loaded — falls back through the
  `--font-mono` stack.
- The frontend source is committed through `83141abd`; preserve small,
  intentional commits because an earlier accidental revert destroyed
  uncommitted `src/lib/*` implementations.
