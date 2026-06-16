"""Run/report progress primitives shared by Commission and Decommission.

- `ProgressHeader`: a determinate-or-indeterminate bar with a live
  "x / y  ·  n failed" label, shown at the top of a run.
- `status_row`: one icon+label line with a semantic state.
- `RawLogPanel`: a collapsible "View raw log" disclosure that pulls its
  text lazily (so the log keeps growing during the run).

These replace the flat, unstructured scrolling logs the two tools used to
render while running.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

import theme

# state -> (icon, color)
_STATUS = {
    "done": (ft.Icons.CHECK_CIRCLE, theme.SUCCESS),
    "failed": (ft.Icons.ERROR, theme.DANGER),
    "cancelled": (ft.Icons.CANCEL, theme.WARNING),
    "pending": (ft.Icons.SCHEDULE_ROUNDED, theme.TEXT_MUTED),
    "partial": (ft.Icons.WARNING_AMBER_ROUNDED, theme.WARNING),
}


def status_row(state: str, label: str, *, detail: str | None = None) -> ft.Row:
    """A single icon + label line for a step/category result."""
    icon_name, color = _STATUS.get(state, (ft.Icons.CIRCLE, theme.TEXT_MUTED))
    text = label if not detail else f"{label} — {detail}"
    text_color = color if state in ("failed", "cancelled") else theme.TEXT_SECONDARY
    return ft.Row(
        [
            ft.Icon(icon_name, color=color, size=18),
            ft.Text(text, color=text_color, size=theme.FONT_CAPTION, expand=True),
        ],
        spacing=theme.SPACE_SM,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


class ProgressHeader(ft.Container):
    """A progress bar + live counts label.

    `determinate=True` drives the bar from done/total (use when the total is
    known up front, e.g. decommission's asset count); otherwise the bar runs
    indeterminate and the label just reports running counts.
    """

    def __init__(self, *, determinate: bool = False):
        super().__init__(padding=ft.Padding.only(bottom=theme.SPACE_MD))
        self._determinate = determinate
        self._bar = ft.ProgressBar(
            value=0.0 if determinate else None,
            color=theme.ACCENT,
            bgcolor=theme.SURFACE_VARIANT,
            bar_height=6,
            border_radius=theme.RADIUS_PILL,
        )
        self._label = ft.Text(
            "Starting…", size=theme.FONT_CAPTION, color=theme.TEXT_SECONDARY
        )
        self.content = ft.Column([self._label, self._bar], spacing=theme.SPACE_SM)

    def set_progress(
        self,
        done: int,
        total: int | None = None,
        failed: int = 0,
        *,
        prefix: str | None = None,
    ):
        parts = [prefix] if prefix else []
        parts.append(f"{done} / {total}" if total is not None else f"{done} done")
        if failed:
            parts.append(f"{failed} failed")
        self._label.value = "   ·   ".join(parts)
        self._label.color = theme.DANGER if failed else theme.TEXT_SECONDARY
        if self._determinate:
            self._bar.value = min(1.0, done / total) if total else 1.0

    def complete(self, *, color: str | None = None):
        """Fill the bar and optionally tint it (success/warning/danger)."""
        self._bar.value = 1.0
        if color:
            self._bar.color = color


class RawLogPanel(ft.Column):
    """Collapsible 'View raw log' disclosure backed by a text provider."""

    def __init__(self, get_text: Callable[[], str]):
        super().__init__(spacing=theme.SPACE_SM)
        self._get_text = get_text
        self._body = ft.Container(
            visible=False,
            bgcolor=theme.SURFACE_VARIANT,
            border_radius=theme.RADIUS_MD,
            padding=ft.Padding.all(theme.SPACE_MD),
            content=ft.Text(
                "",
                font_family=theme.FONT_MONO,
                size=theme.FONT_CAPTION,
                color=theme.TEXT_SECONDARY,
                selectable=True,
            ),
        )
        self._chevron = ft.Icon(
            ft.Icons.CHEVRON_RIGHT, size=18, color=theme.TEXT_SECONDARY
        )
        self._toggle_label = ft.Text(
            "View raw log", color=theme.TEXT_SECONDARY, size=theme.FONT_CAPTION
        )
        self._toggle = ft.TextButton(
            content=ft.Row(
                [self._chevron, self._toggle_label],
                spacing=theme.SPACE_XS,
                tight=True,
            ),
            on_click=self._on_toggle,
        )
        self.controls = [self._toggle, self._body]

    def _on_toggle(self, e):
        visible = not self._body.visible
        self._body.visible = visible
        self._body.content.value = self._get_text()
        self._chevron.name = (
            ft.Icons.EXPAND_MORE if visible else ft.Icons.CHEVRON_RIGHT
        )
        self._toggle_label.value = "Hide raw log" if visible else "View raw log"
        e.page.update()
