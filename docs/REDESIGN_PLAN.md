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

## Phase 4 · Progress & report screens (review gate) — DONE
- [x] T4.1 Shared progress primitives: `ProgressHeader` (determinate for decommission / indeterminate for commission, with "x/y · n failed"), `status_row`, `RawLogPanel`. Reports lead with a result banner and a failures-first section; decommission keeps its collapsible per-category groups.
- [x] T4.2 Commission's flat run log moved behind a "View raw log" disclosure; Copy log + Export report (CSV) on both tools (`utils/export.py`, ~/Downloads).

## Phase 5 · Polish — DONE
- [x] T5.1 Light/dark theme toggle (sidebar) + OS-preference default + persistence
- [x] T5.2 Non-blocking pre-expiry banner with bounded "Extend session" (+15 min, capped) replacing the blocking modal; amber session chip
- [x] T5.3 Command palette (Cmd/Ctrl-K) overlay — searchable nav + theme toggle + logout
- [x] T5.4 Inline Login validation (field errors + error banner, migrated onto components); decommission "no assets found" empty state

## Phase 6 · Visual QA pass (headless CanvasKit screenshots) — DONE
Rendered every view/state with a headless browser (tools/shoot_app.py) and reviewed spacing/format:
- [x] Replaced unicode arrow/triangle glyphs (▯ tofu in the bundled font) with Material icons / plain labels (Edit/Back/Review/raw-log chevron; ghost_button gained an `icon` param)
- [x] Home tool cards: full descriptions, equal height (was clipped by a too-short fixed height)
- [x] Login + 2FA cards: hug content and center (were filling full viewport height — Column mainAxisSize)
- [x] Decommission "Assets Found": uses stat_row so non-zero counts pop and zeros recede
- [x] Moved the light/dark toggle from the sidebar footer to the sidebar header (next to the wordmark)
- [x] Commission Configure: Template/Kit now a clean 50/50 (dropdowns expand)
- [x] Decommission complete banner copy: partial runs read "X/Y deleted — N could not be removed" (was "deleted successfully" under a warning icon)

## Phase 7 · Navigation rework (persistent shell) — DONE
Replaced the per-view sidebar + page.views route stack with one persistent shell:
- [x] `AppShell` is mounted once; tools are lightweight `ToolView`s whose body is
      hosted in a content area. Switching tools calls `shell.show(route)` and
      swaps only the content — the sidebar stays constant, no page transition.
- [x] Esc uses route-aware `back()` (no growing history): no-op on Home/public,
      tool→Home, 2FA→login. Fixes "Esc keeps going back on Home".
- [x] Cmd/Ctrl-K gated to authenticated tool routes only — can no longer open on
      the 2FA screen (which previously let you bypass MFA into the app).

## Phase 8 · Home + palette polish — DONE
- [x] Home tool cards rebalanced: icon tile + navigate arrow on a top row, larger
      title/description, tighter height — no more content floating in sparse,
      wide cards.
- [x] Command palette tidied: full-width search aligned with the rows, a divider,
      consistent padding, hover highlight, and it sizes to content (no empty
      bottom). content_padding=0 + a STRETCH column.
