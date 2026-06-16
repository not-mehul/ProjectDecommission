"""Shared horizontal step indicator.

One component for every multi-step flow (Users invite, and the new
Configure -> Review -> Run -> Report flows in Commission/Decommission).
Renders numbered circles with connectors and three states:

  done      -> filled success, check icon
  active    -> filled accent, step number
  upcoming  -> muted fill, step number

Call `set_active(index)` to advance; the caller is responsible for the
following `page.update()` (matching how the rest of the views update).
"""

from __future__ import annotations

import flet as ft

import theme

_CIRCLE = 30
_CONNECTOR_W = 48


class Stepper(ft.Container):
    def __init__(self, labels: list[str], current: int = 0):
        super().__init__(alignment=ft.Alignment.CENTER)
        self._labels = labels
        self._current = current
        self._circles: list[ft.Container] = []
        self._captions: list[ft.Text] = []
        self._connectors: list[ft.Container] = []
        self.content = self._build()

    def _build(self) -> ft.Row:
        items: list[ft.Control] = []
        for i, label in enumerate(self._labels):
            circle = ft.Container(
                width=_CIRCLE,
                height=_CIRCLE,
                border_radius=theme.RADIUS_PILL,
                alignment=ft.Alignment.CENTER,
            )
            caption = ft.Text(
                label, size=theme.FONT_MICRO, text_align=ft.TextAlign.CENTER
            )
            self._circles.append(circle)
            self._captions.append(caption)
            items.append(
                ft.Column(
                    [circle, caption],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=theme.SPACE_XS,
                )
            )
            if i < len(self._labels) - 1:
                connector = ft.Container(
                    width=_CONNECTOR_W,
                    height=2,
                    border_radius=1,
                    margin=ft.Margin.only(bottom=18),
                )
                self._connectors.append(connector)
                items.append(connector)
        self._apply()
        return ft.Row(
            items,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=theme.SPACE_SM,
        )

    def _apply(self):
        for i, circle in enumerate(self._circles):
            caption = self._captions[i]
            if i < self._current:  # done
                circle.bgcolor = theme.SUCCESS
                circle.content = ft.Icon(
                    ft.Icons.CHECK_ROUNDED, size=16, color=theme.ON_ACCENT
                )
                caption.color = theme.TEXT_SECONDARY
                caption.weight = theme.WEIGHT_MEDIUM
            elif i == self._current:  # active
                circle.bgcolor = theme.ACCENT
                circle.content = ft.Text(
                    str(i + 1),
                    color=theme.ON_ACCENT,
                    size=theme.FONT_BODY,
                    weight=theme.WEIGHT_SEMIBOLD,
                    text_align=ft.TextAlign.CENTER,
                )
                caption.color = theme.TEXT_PRIMARY
                caption.weight = theme.WEIGHT_SEMIBOLD
            else:  # upcoming
                circle.bgcolor = theme.SURFACE_VARIANT
                circle.content = ft.Text(
                    str(i + 1),
                    color=theme.TEXT_MUTED,
                    size=theme.FONT_BODY,
                    text_align=ft.TextAlign.CENTER,
                )
                caption.color = theme.TEXT_MUTED
                caption.weight = theme.WEIGHT_REGULAR
        for i, connector in enumerate(self._connectors):
            connector.bgcolor = theme.SUCCESS if i < self._current else theme.BORDER

    def set_active(self, index: int):
        """Move the active step. Caller triggers the page.update()."""
        self._current = index
        self._apply()
