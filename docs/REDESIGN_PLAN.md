# vCommander UI/UX Redesign — Working Plan

Tracking doc for the staged UI/UX redesign. Checked items are done on the
`claude/busy-dijkstra-mcs2vh` branch. Major (user-visible structural) items
pause for review before continuing.

## Phase 1 · Foundation (design system) — DONE
- [x] T1.1 `theme.py` — spacing/type/semantic-color/elevation/radius tokens, light+dark palettes
- [x] T1.2 `components/` — buttons (primary/secondary/danger/ghost + loading), inputs (text_field/dropdown), surfaces (card/section_header/stat_row/banner/badge)
- [x] T1.3 Route every view through tokens via `constants.py` re-exporting from `theme.py` (identical values, zero visual change). Per-view *component* migration is deferred into each view's redesign phase to avoid restyling twice (login→P5, home→P2, commission/decommission/users→P3/P4).

## Phase 2 · App shell (structural — review gate)
- [ ] T2.1 Persistent left sidebar + content header/breadcrumb
- [ ] T2.2 Org + session chip in sidebar; wire nav into push/pop + Cmd-K/Esc
- [ ] T2.3 Compact dashboard home; demote per-tool brand colors

## Phase 3 · Unified flows (review gate)
- [ ] T3.1 Shared stepper component; restyle Users stepper
- [ ] T3.2 Commission: Configure → Review/summary → Run → Report
- [ ] T3.3 Decommission: Scan → Select → Confirm summary → Run → Report

## Phase 4 · Progress & report screens (review gate)
- [ ] T4.1 Structured progress (determinate bar, x/y · n failed), collapsible groups, failures-first
- [ ] T4.2 Replace raw log dumps (behind "view raw log"); Copy log / Export report (CSV/JSON)

## Phase 5 · Polish
- [ ] T5.1 Light/dark theme toggle + respect OS preference
- [ ] T5.2 Non-blocking session banner + Extend session; amber chip
- [ ] T5.3 Command palette (Cmd-K) overlay
- [ ] T5.4 Inline Login validation/error states; empty/skeleton states
