"""Cmd/Ctrl-K command palette.

A lightweight searchable overlay for jumping between tools and running a few
global actions. The owner (main) supplies the command list as
`(label, icon, action)` tuples; the palette handles filtering, keyboard
submit (runs the top match), and dismissal.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

import theme
from components.inputs import text_field

Command = tuple[str, str, Callable[[], None]]

_WIDTH = 560


class CommandPalette:
    def __init__(self, page: ft.Page, commands: list[Command]):
        self._page = page
        self._commands = commands
        self._results = ft.Column(spacing=2, tight=True)
        self._search = text_field(
            "Type a command…",
            on_change=self._on_change,
            on_submit=self._on_submit,
        )
        self._dialog = ft.AlertDialog(
            bgcolor=theme.SURFACE,
            content_padding=0,
            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_LG),
            content=ft.Container(
                width=_WIDTH,
                padding=ft.Padding.all(theme.SPACE_SM),
                content=ft.Column(
                    [
                        ft.Container(
                            padding=ft.Padding.all(theme.SPACE_XS),
                            content=self._search,
                        ),
                        ft.Divider(height=1, color=theme.BORDER_SUBTLE),
                        ft.Container(height=theme.SPACE_XS),
                        self._results,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    tight=True,
                ),
            ),
        )

    def open(self):
        self._search.value = ""
        self._render(self._commands)
        self._page.show_dialog(self._dialog)

    # -- internals -----------------------------------------------------
    def _filtered(self) -> list[Command]:
        query = (self._search.value or "").strip().lower()
        if not query:
            return self._commands
        return [c for c in self._commands if query in c[0].lower()]

    def _on_change(self, e):
        self._render(self._filtered())
        self._page.update()

    def _on_submit(self, e):
        matches = self._filtered()
        if matches:
            self._run(matches[0][2])

    def _render(self, items: list[Command]):
        if not items:
            self._results.controls = [
                ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=theme.SPACE_MD, vertical=theme.SPACE_MD
                    ),
                    content=ft.Text(
                        "No matching commands",
                        color=theme.TEXT_MUTED,
                        size=theme.FONT_CAPTION,
                    ),
                )
            ]
            return
        self._results.controls = [self._row(*c) for c in items]

    def _row(self, label: str, icon: str, action: Callable[[], None]) -> ft.Control:
        row = ft.Container(
            on_click=lambda _: self._run(action),
            ink=True,
            border_radius=theme.RADIUS_MD,
            padding=ft.Padding.symmetric(
                horizontal=theme.SPACE_MD, vertical=theme.SPACE_MD - 2
            ),
            content=ft.Row(
                [
                    ft.Icon(icon, size=18, color=theme.TEXT_SECONDARY),
                    ft.Text(label, size=theme.FONT_BODY, color=theme.TEXT_PRIMARY),
                ],
                spacing=theme.SPACE_MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        row.on_hover = lambda e, c=row: self._hover(e, c)
        return row

    def _hover(self, e, container: ft.Container):
        container.bgcolor = (
            theme.palette.tint(theme.TEXT_PRIMARY, 0.06)
            if e.data == "true"
            else None
        )
        self._page.update()

    def _run(self, action: Callable[[], None]):
        self._page.pop_dialog()
        action()
