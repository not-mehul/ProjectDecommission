"""Button components and the shared loading-state helper.

Four variants cover every button in the app:
  - primary    : filled accent, the screen's main action
  - secondary  : outlined, neutral secondary action
  - danger     : filled danger, destructive confirmation (Decommission)
  - ghost      : text-only, low-emphasis (links, "Add participant")

`set_button_loading` swaps a button between a spinner+label state and its
normal label, preserving the project's semibold weight.
"""

from __future__ import annotations

import flet as ft

import theme

_DEFAULT_HEIGHT = 44


def _shape() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=theme.RADIUS_MD)


def primary_button(
    label: str,
    *,
    on_click=None,
    height: int = _DEFAULT_HEIGHT,
    expand=None,
    width=None,
) -> ft.ElevatedButton:
    """Filled accent button for the primary action on a screen."""
    return ft.ElevatedButton(
        content=ft.Text(
            label, color=theme.ON_ACCENT, weight=theme.WEIGHT_SEMIBOLD
        ),
        bgcolor=theme.ACCENT,
        style=ft.ButtonStyle(shape=_shape()),
        height=height,
        on_click=on_click,
        expand=expand,
        width=width,
    )


def secondary_button(
    label: str,
    *,
    on_click=None,
    height: int = _DEFAULT_HEIGHT,
    expand=None,
    width=None,
) -> ft.OutlinedButton:
    """Outlined neutral button for secondary actions."""
    return ft.OutlinedButton(
        content=ft.Text(
            label, color=theme.TEXT_SECONDARY, weight=theme.WEIGHT_SEMIBOLD
        ),
        style=ft.ButtonStyle(
            side=ft.BorderSide(1, theme.BORDER),
            shape=_shape(),
        ),
        height=height,
        on_click=on_click,
        expand=expand,
        width=width,
    )


def danger_button(
    label: str,
    *,
    on_click=None,
    height: int = _DEFAULT_HEIGHT,
    expand=None,
    width=None,
) -> ft.ElevatedButton:
    """Filled danger button for destructive confirmations."""
    return ft.ElevatedButton(
        content=ft.Text(label, color="#ffffff", weight=theme.WEIGHT_SEMIBOLD),
        bgcolor=theme.DANGER,
        style=ft.ButtonStyle(shape=_shape()),
        height=height,
        on_click=on_click,
        expand=expand,
        width=width,
    )


def ghost_button(
    label: str,
    *,
    on_click=None,
    color: str | None = None,
) -> ft.TextButton:
    """Low-emphasis text button (e.g. '+ Add participant')."""
    return ft.TextButton(
        content=ft.Text(
            label, color=color or theme.ACCENT, weight=theme.WEIGHT_MEDIUM
        ),
        style=ft.ButtonStyle(shape=_shape()),
        on_click=on_click,
    )


def set_button_loading(
    btn: ft.ElevatedButton, loading: bool, label: str, auto_update: bool = True
):
    """Toggle a filled button between a spinner state and its normal label.

    The restored label uses the project's semibold weight and the accent's
    on-color so a failed round-trip doesn't leave the button looking
    lighter than its siblings.
    """
    text_color = theme.ON_ACCENT
    if loading:
        btn.content = ft.Row(
            [
                ft.ProgressRing(
                    width=16, height=16, stroke_width=2, color=text_color
                ),
                ft.Text(f"  {label}...", color=text_color),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        btn.disabled = True
    else:
        btn.content = ft.Text(
            label, color=text_color, weight=theme.WEIGHT_SEMIBOLD
        )
        btn.disabled = False
    if auto_update:
        page = getattr(btn, "page", None)
        if page:
            page.update()
