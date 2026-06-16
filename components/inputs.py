"""Form input components: text fields and dropdowns.

Centralizes the styling that `login_view._make_text_field` /
`_make_dropdown` (and ad-hoc fields in the other views) duplicated.
"""

from __future__ import annotations

import flet as ft

import theme


def text_field(
    label: str,
    *,
    value: str = "",
    password: bool = False,
    can_reveal_password: bool = False,
    hint: str | None = None,
    on_submit=None,
    on_change=None,
    expand=None,
    width=None,
) -> ft.TextField:
    """A styled TextField matching the app's input language."""
    return ft.TextField(
        label=label,
        value=value,
        password=password,
        can_reveal_password=can_reveal_password,
        hint_text=hint,
        on_submit=on_submit,
        on_change=on_change,
        expand=expand,
        width=width,
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT,
        border_radius=theme.RADIUS_MD,
        color=theme.TEXT_PRIMARY,
        cursor_color=theme.ACCENT,
        label_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
        hint_style=ft.TextStyle(color=theme.TEXT_MUTED),
    )


def dropdown(
    label: str,
    options: list[ft.dropdown.Option],
    *,
    value: str = "",
    on_select=None,
    expand=None,
    width=None,
) -> ft.Dropdown:
    """A styled Dropdown matching the app's input language.

    Note: flet's Dropdown fires `on_select` (not `on_change`) in the API
    version this app targets.
    """
    return ft.Dropdown(
        label=label,
        options=options,
        value=value,
        on_select=on_select,
        expand=expand,
        width=width,
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT,
        border_radius=theme.RADIUS_MD,
        color=theme.TEXT_PRIMARY,
        label_style=ft.TextStyle(color=theme.TEXT_SECONDARY),
    )
