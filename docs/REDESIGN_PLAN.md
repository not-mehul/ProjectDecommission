# vCommander UI/UX Redesign — Working Plan

Tracking doc for the staged UI/UX redesign. Checked items are done on the
`claude/busy-dijkstra-mcs2vh` branch. Major (user-visible structural) items
pause for review before continuing.

## Phase 1 · Foundation (design system) — DONE
- [x] T1.1 `theme.py` — spacing/type/semantic-color/elevation/radius tokens, light+dark palettes
- [x] T1.2 `components/` — buttons (primary/secondary/danger/ghost + loading), inputs (text_field/dropdown), surfaces (card/section_header/stat_row/banner/badge)
- [x] T1.3 Route every view through tokens via `constants.py` re-exporting from `theme.py` (identical values, zero visual change). Per-view *component* migration is deferred into each view's redesign phase to avoid restyling twice (login→P5, home→P2, commission/decommission/users→P3/P4).

## Phase 1.5 · Migrate to Flet v0.85 (foundational — enables real testing)
The existing code mixed idioms from incompatible flet versions and couldn't be
constructed under any single release. Migrating to 0.85 standardizes the API
and lets every screen be validated against the installed runtime. Mechanical:
the navigation (page.views), window config, and View lifecycle are unchanged.
- [x] T1.5a Bump requirement to flet>=0.85; update theme/components idioms
- [x] T1.5b `ft.padding.*`->`ft.Padding.*`, `ft.border.all`->`ft.Border.all`, `ft.margin.only`->`ft.Margin.only` across all views (29+1 swaps)
- [x] T1.5c App entry `ft.app(target=main)` -> `ft.run(main)`
- [x] T1.5d Overlay show pattern (snackbar, date picker) -> `page.show_dialog(...)`
- [x] T1.5e Validated: components + all 6 Views construct under flet 0.85.3
      (NOTE: construction-level only — GUI render not verifiable headless here)

## Phase 2 · App shell (structural — review gate) — DONE
- [x] T2.1 `ShellView` base class: persistent left sidebar (wordmark + nav) + content title header
- [x] T2.2 Org + live session chip in sidebar; logout in sidebar; session countdown/warning/auto-logout centralized in ShellView (now ticks on every authed screen). Global Cmd-K/Esc/Cmd-, unchanged in main.py
- [x] T2.3 Compact dashboard Home (tool cards + shortcut hint); brand colors demoted to small nav/card icon tints. Tool views (commission/decommission/users) re-based onto ShellView; users keeps an in-card step-back button

## Phase 3 · Unified flows (review gate) — DONE
- [x] T3.1 Shared `Stepper` component (done=check / active / upcoming); Users stepper restyled onto it
- [x] T3.2 Commission: Configure → Review (pre-flight summary of what will be created) → Run → Report, driven by the shared stepper
- [x] T3.3 Decommission: Scan → Review → Select → Confirm (new destructive summary + danger banner before deletion) → Run → Report, with the shared stepper across all states

## Phase 4 · Progress & report screens (review gate)
- [ ] T4.1 Structured progress (determinate bar, x/y · n failed), collapsible groups, failures-first
- [ ] T4.2 Replace raw log dumps (behind "view raw log"); Copy log / Export report (CSV/JSON)

## Phase 5 · Polish
- [ ] T5.1 Light/dark theme toggle + respect OS preference
- [ ] T5.2 Non-blocking session banner + Extend session; amber chip
- [ ] T5.3 Command palette (Cmd-K) overlay
- [ ] T5.4 Inline Login validation/error states; empty/skeleton states
