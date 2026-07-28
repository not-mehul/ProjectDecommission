# vCommander — Code Audit

A read-only scan of the codebase for dead/stale code, lint findings, and
optimization opportunities. This document is the **inventory**; the
accompanying change set applied the low-risk fixes (lint, reliability,
duplication) and the two structural refactors, and left the items below as
**report-only** so they can be triaged individually.

Every "unreferenced" claim was cross-checked against the dynamic dispatch maps
in [`constants.py`](../constants.py) (`_INTERNAL_GETTERS`, `_INTERNAL_DELETERS`,
`_EXTERNAL_GETTERS`, `_EXTERNAL_DELETERS`, resolved via `getattr` in
`decommission_view.py`) and `ASSET_CATEGORIES` / `DELETION_ORDER`, so methods
reached only by string dispatch are **not** falsely reported.

> Line numbers reflect the state of the tree when this audit was written and
> will drift as the files change.

---

## A1 — API layer: reserved for future implementation (keep)

These symbols are currently unreferenced but are intentional scaffolding for
planned features (alarm sub-device provisioning, public-API parity, additional
endpoint coverage). **They are deliberately retained** — listed here for
visibility, not for deletion.

### `apis/internal_api.py` — 23 currently-unreferenced methods

Alarm sub-device **provisioning** cluster (only the `get_*_all` scan and
`delete_*` sides are wired into decommission today):

| Line | Method |
|---|---|
| ~2203 | `create_alarm_partition` |
| ~2235 | `assign_alarm_partition_response` |
| ~2275 | `create_alarm_guard` |
| ~2461 | `configure_alarm_expander` |
| ~2495 | `configure_wireless_contact_sensor` |
| ~2537 | `configure_wireless_panic_button` |
| ~2579 | `configure_wireless_universal_transmitter` |
| ~2626 | `create_wired_output` |
| ~2667 | `create_wired_input` |

Internal methods paralleling the external/public API (the app currently routes
these operations through `VerkadaExternalAPIClient`):

| Line | Method | Live counterpart |
|---|---|---|
| ~791 | `get_user` | `external_api.get_users` |
| ~822 | `delete_user` | `external_api.delete_user` |
| ~1071 | `get_camera` | `external_api.get_cameras` |
| ~1480 | `create_access_group` | `external_api.create_access_group` |
| ~1502 | `get_access_group` | `external_api.get_access_groups` |
| ~1528 | `delete_access_group` | `external_api.delete_access_group` |
| ~1535 | `add_user_to_access_group` | `external_api.add_user_to_access_group` |

Other reserved methods: `is_org_empty` (~696), `get_device_count` (~709),
`get_external_api_key` (~885), `delete_external_api_key` (~896),
`get_alarm_device` (~2737), `delete_alarm_device` (~2800),
`create_mailroom_site` (~2861).

### `apis/endpoints.py` — 10 currently-unused endpoint keys

Never passed to `resolve()` yet; kept as the registry backing the reserved
methods above: `permissions.access_system_admin.disable`,
`permissions.access_user_admin.disable`, `org.device_information.list`,
`user.hard_delete`, `user.add_license_plate`, `floorplan.delete`,
`scenario.create`, `guest_type.create`, `guest_type.list`,
`guest_type.delete`.

Four keys from the original list are now wired up: `org.allow_face_unlock`,
`face_station_pro.create`, `face_station_pro.door.create` (renamed from
`face_station_pro.set_door_controller`), and `schedule.create.mfa` (renamed
from `schedule.create`) — see the Face Station Pro / MFA methods in
`internal_api.py`. `_FACE_STATION_PRO_DOOR_CREATE_CONFIGS` (~101–132) is
consumed by `create_access_station_pro_door`, and `_MFA_DOOR_EVENT` by
`create_mfa_schedule`.

### `apis/external_api.py`

No unreferenced methods. `delete_access_user` (~517) is a thin alias of
`delete_user` — informational only.

---

## A2 — Non-API unreferenced symbols (triage candidates)

Genuinely unreferenced across the repo. Left in place this pass; safe to remove
per-item when convenient.

| Symbol | Location | Notes |
|---|---|---|
| `secondary_button` | `components/buttons.py` | Now **live** after the view migration adopted it. |
| `danger_button` | `components/buttons.py` | Now **live** (decommission confirm button). |
| `badge` | `components/surfaces.py` | Still unused — part of the design-system palette. |
| `export_json` | `utils/export.py` | Only `export_csv` is used. |
| `create_loading_overlay` | `utils/ui_utils.py` | Never called. |
| `mark_warning_shown` / `was_warning_shown` | `utils/session.py` | Dead pair; the `_warning_shown` module state they gate is therefore write-only. The real pre-expiry warning is computed in `pages/app_shell.py` (`in_warning = remaining <= SESSION_WARNING_MINUTES * 60`). |
| `CancellationToken.reset()` | `utils/cancellation.py` | Views construct a fresh token each run; `.cancel()` / `.is_cancelled` are used. |
| `space()` | `theme.py` | Referenced only in its own docstring. |

**Verified NOT dead:** `utils/executor.py` `_executor`; all 9 `constants.py`
color re-exports + `CARD_SHADOW` (consumed via multi-line imports across the
views); `CancellationToken` itself; the Visits/Visitors getters/deleters (still
in `ASSET_CATEGORIES` / `DELETION_ORDER`).

---

## Lint findings reported but not changed

The chosen scope was "lint fixes only, no reformat." The following were left
untouched (a repo-wide `black` run or an added `pyproject.toml` was explicitly
out of scope):

- **`black`**: 15 files would be reformatted at the default 88-col width —
  mostly collapsing manually column-aligned inline comments. Cosmetic.
- **`C901` (complexity > 10)**: `main.main` (32), `tools/shoot_app._drive` (22),
  `decommission_view._run_deletions` (13), `commission_view._on_commission` (11),
  `decommission_view._delete_one` (11). Decomposition deferred (behavior-risky).
- **`PERF401`**: manual list-comprehension opportunities in
  `commission_view.py` and `decommission_view.py`.
- **`E501`**: ~20 lines slightly over 88 cols (mostly long f-strings/URLs black
  would leave intact).

### Applied in the accompanying change set
- `F401` (9): the `theme` re-exports in `constants.py` are live — annotated
  `# noqa: E402, F401` (intentional re-exports).
- `B904` (13): added `from e` / `from None` to `raise`-inside-`except` in the API layer.
- `SIM105` (3): `try/except: pass` → `contextlib.suppress` in `app_shell.py`, `shoot_app.py`.
- `RUF022`: sorted `__all__` in `components/__init__.py`.
- `RUF059`: unused unpack `floor_id` → `_` in `commission_view.py`.
- Removed a stray debug `print` in `commission_view._load_kits`.

---

## Notes / smaller observations

- **`flet.ElevatedButton` is deprecated** (since flet 0.80, removal slated for
  1.0) in favor of `flet.Button`. The whole codebase still uses `ElevatedButton`
  (now centralized in `components/buttons.py`, so a future swap is a one-file
  change). Not addressed here.
- **`main.py` background tasks** previously used bare `asyncio.create_task(...)`
  (GC-risk for the session watchdog); fixed by holding strong references. The
  correct pattern already existed at `pages/app_shell.py` (`self._timer_task`).
- **HTTP reliability**: the external client had a retry adapter but no request
  timeout; the internal client had timeouts but no retries. Unified via
  `apis/http.py` (`build_session` + a `TimeoutRetryAdapter`) so both get both.
- **`docs/REDESIGN_PLAN.md`** is a completed tracking doc pinned to an old dev
  branch (`claude/busy-dijkstra-mcs2vh`); every phase is marked DONE. Historical
  artifact — left in place.
