"""Persistent application shell.

`ShellView` is the base class for every authenticated screen. It renders a
fixed left sidebar (brand wordmark, tool navigation, org + session chips,
logout) beside a content area with a title/subtitle header, and runs the
live session countdown so it ticks on *every* tool screen rather than only
Home.

A tool view subclasses `ShellView`, builds its body control, and calls
`self.render(body)` with a title. The public screens (login, 2FA) stay as
plain `ft.View`s — they have no shell.

Why a base class rather than a wrapper function: the session countdown needs
`did_mount`/`will_unmount` lifecycle, and centralizing it here means the four
tool screens don't each re-implement the timer + warning + auto-logout logic
that previously lived only in HomeView.
"""

from __future__ import annotations

import asyncio

import flet as ft

import theme
from constants import APP_VERSION, SESSION_WARNING_MINUTES
from utils.db import load_credentials
from utils.session import (
    can_extend,
    clear_session,
    extend_session,
    get_session_remaining,
    start_session,
)

# Sidebar navigation model: (route, label, icon, brand tint). The brand color
# is used only as a small icon tint — never as a dominant surface color.
NAV_ITEMS = [
    ("/home", "Home", ft.Icons.GRID_VIEW_ROUNDED, theme.ACCENT),
    ("/commission", "Commission", ft.Icons.BUSINESS_ROUNDED, theme.BRAND_COMMISSION),
    ("/users", "Users", ft.Icons.PEOPLE_ALT_ROUNDED, theme.BRAND_USERS),
    (
        "/decommission",
        "Decommission",
        ft.Icons.DELETE_SWEEP_ROUNDED,
        theme.BRAND_DECOMMISSION,
    ),
]

_SIDEBAR_WIDTH = 232

# Set by main.py: a zero-arg callable that flips light/dark and rebuilds the
# view tree. Kept as a module hook so the shell can trigger a theme switch
# without importing main (which would be circular).
_THEME_TOGGLE = None


def set_theme_toggle(fn) -> None:
    global _THEME_TOGGLE
    _THEME_TOGGLE = fn


class ShellView(ft.View):
    def __init__(
        self,
        *,
        route: str,
        title: str,
        push_route,
        pop_route,
        subtitle: str | None = None,
        **kwargs,
    ):
        super().__init__(route=route, bgcolor=theme.BG, padding=0, **kwargs)
        self.active_route = route
        self.title_text = title
        self.subtitle_text = subtitle
        self.push_route = push_route
        self.pop_route = pop_route
        self._session_text = ft.Text(
            "", size=theme.FONT_CAPTION, color=theme.TEXT_SECONDARY
        )
        self._timer_task: asyncio.Task | None = None
        # Non-blocking pre-expiry banner (replaces the old modal warning).
        self._session_banner_text = ft.Text(
            "", size=theme.FONT_CAPTION, color=theme.TEXT_PRIMARY, expand=True
        )
        self._extend_btn = ft.TextButton(
            content=ft.Text(
                "Extend session", color=theme.ACCENT, weight=theme.WEIGHT_MEDIUM
            ),
            on_click=self._on_extend,
        )
        self._session_banner = ft.Container(
            visible=False,
            bgcolor=theme.palette.tint(theme.WARNING, 0.12),
            border=ft.Border.all(1, theme.palette.tint(theme.WARNING, 0.4)),
            border_radius=theme.RADIUS_MD,
            margin=ft.Margin.only(bottom=theme.SPACE_LG),
            padding=ft.Padding.symmetric(
                horizontal=theme.SPACE_LG, vertical=theme.SPACE_SM
            ),
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.WARNING_AMBER_ROUNDED, color=theme.WARNING, size=18
                    ),
                    self._session_banner_text,
                    self._extend_btn,
                ],
                spacing=theme.SPACE_MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------
    def render(self, body: ft.Control):
        """Mount `body` inside the shell. Call this at the end of _build_ui."""
        self.controls = [
            ft.Row(
                [self._build_sidebar(), self._build_content(body)],
                spacing=0,
                expand=True,
            )
        ]

    def _build_content(self, body: ft.Control) -> ft.Control:
        header_texts = [
            ft.Text(
                self.title_text,
                size=theme.FONT_TITLE,
                color=theme.TEXT_PRIMARY,
                weight=theme.WEIGHT_SEMIBOLD,
            )
        ]
        if self.subtitle_text:
            header_texts.append(
                ft.Text(
                    self.subtitle_text,
                    size=theme.FONT_CAPTION,
                    color=theme.TEXT_SECONDARY,
                )
            )
        return ft.Container(
            expand=True,
            padding=ft.Padding.all(theme.SPACE_2XL),
            content=ft.Column(
                [
                    self._session_banner,
                    ft.Column(header_texts, spacing=theme.SPACE_XS),
                    ft.Container(height=theme.SPACE_XL),
                    ft.Container(content=body, expand=True),
                ],
                expand=True,
            ),
        )

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> ft.Control:
        nav = [self._nav_item(*item) for item in NAV_ITEMS]

        wordmark = ft.Column(
            [
                ft.Text(
                    "vCommander",
                    size=theme.FONT_HEADING,
                    color=theme.ACCENT,
                    weight=theme.WEIGHT_BOLD,
                ),
                ft.Text(
                    f"v{APP_VERSION}", size=theme.FONT_MICRO, color=theme.TEXT_MUTED
                ),
            ],
            spacing=2,
        )

        footer = ft.Column(
            [
                ft.Divider(height=1, color=theme.BORDER_SUBTLE),
                ft.Container(height=theme.SPACE_SM),
                self._chip(ft.Icons.CORPORATE_FARE_ROUNDED, self._org_name()),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.SCHEDULE_ROUNDED,
                                size=14,
                                color=theme.TEXT_MUTED,
                            ),
                            self._session_text,
                        ],
                        spacing=theme.SPACE_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(
                        horizontal=theme.SPACE_MD, vertical=theme.SPACE_XS
                    ),
                ),
                ft.Container(
                    content=ft.Row(
                        [self._build_theme_toggle()],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ),
                ft.OutlinedButton(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.LOGOUT_ROUNDED,
                                size=16,
                                color=theme.TEXT_SECONDARY,
                            ),
                            ft.Text("Logout", color=theme.TEXT_SECONDARY),
                        ],
                        spacing=theme.SPACE_SM,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, theme.BORDER),
                        shape=ft.RoundedRectangleBorder(radius=theme.RADIUS_MD),
                    ),
                    on_click=self._on_logout,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        return ft.Container(
            width=_SIDEBAR_WIDTH,
            bgcolor=theme.SURFACE,
            border=ft.Border.only(
                right=ft.BorderSide(1, theme.BORDER_SUBTLE)
            ),
            padding=ft.Padding.symmetric(
                horizontal=theme.SPACE_MD, vertical=theme.SPACE_XL
            ),
            content=ft.Column(
                [
                    ft.Container(
                        content=wordmark,
                        padding=ft.Padding.symmetric(horizontal=theme.SPACE_MD),
                    ),
                    ft.Container(height=theme.SPACE_2XL),
                    ft.Column(nav, spacing=theme.SPACE_XS),
                    ft.Container(expand=True),
                    footer,
                ],
                expand=True,
            ),
        )

    def _nav_item(self, route, label, icon, brand) -> ft.Control:
        active = route == self.active_route
        item = ft.Container(
            border_radius=theme.RADIUS_MD,
            bgcolor=theme.palette.tint(theme.ACCENT, 0.13) if active else None,
            padding=ft.Padding.symmetric(
                horizontal=theme.SPACE_MD, vertical=theme.SPACE_SM + 2
            ),
            content=ft.Row(
                [
                    ft.Icon(icon, size=18, color=brand),
                    ft.Text(
                        label,
                        size=theme.FONT_BODY,
                        color=theme.TEXT_PRIMARY if active else theme.TEXT_SECONDARY,
                        weight=theme.WEIGHT_SEMIBOLD
                        if active
                        else theme.WEIGHT_MEDIUM,
                    ),
                ],
                spacing=theme.SPACE_MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=None if active else (lambda _, r=route: self.push_route(r)),
            ink=not active,
            animate=ft.Animation(120, ft.AnimationCurve.EASE_IN_OUT),
        )
        if not active:
            item.on_hover = lambda e, c=item: self._hover_nav(e, c)
        return item

    def _hover_nav(self, e, container: ft.Container):
        container.bgcolor = (
            theme.palette.tint(theme.TEXT_PRIMARY, 0.06)
            if e.data == "true"
            else None
        )
        page = getattr(self, "page", None)
        if page:
            page.update()

    def _chip(self, icon, text: str) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(
                horizontal=theme.SPACE_MD, vertical=theme.SPACE_XS
            ),
            content=ft.Row(
                [
                    ft.Icon(icon, size=14, color=theme.TEXT_MUTED),
                    ft.Text(
                        text,
                        size=theme.FONT_CAPTION,
                        color=theme.TEXT_SECONDARY,
                        no_wrap=True,
                    ),
                ],
                spacing=theme.SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _build_theme_toggle(self) -> ft.Control:
        is_dark = theme.palette.mode == "dark"
        return ft.IconButton(
            icon=ft.Icons.LIGHT_MODE_ROUNDED
            if is_dark
            else ft.Icons.DARK_MODE_ROUNDED,
            icon_color=theme.TEXT_SECONDARY,
            icon_size=18,
            tooltip="Switch to light theme" if is_dark else "Switch to dark theme",
            on_click=self._on_toggle_theme,
        )

    def _on_toggle_theme(self, e):
        if _THEME_TOGGLE is not None:
            _THEME_TOGGLE()

    def _org_name(self) -> str:
        creds = load_credentials() or {}
        return creds.get("org_short_name") or "—"

    # ------------------------------------------------------------------
    # Session timer (runs on every authed screen)
    # ------------------------------------------------------------------
    def did_mount(self):
        start_session()
        self._timer_task = asyncio.create_task(self._run_timer())

    def will_unmount(self):
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()

    async def _run_timer(self):
        """Tick the sidebar session chip, warn at the threshold, log out at 0.

        Every page-touching step is guarded so a tick can't fire after the
        view unmounts during navigation (see HomeView's original notes).
        """
        try:
            while True:
                page = getattr(self, "page", None)
                if page is None:
                    return
                remaining = get_session_remaining()
                if remaining <= 0:
                    clear_session()
                    self.push_route("/login")
                    return
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                self._session_text.value = f"Session {mins:02d}:{secs:02d}"
                in_warning = remaining <= SESSION_WARNING_MINUTES * 60
                # Tint the chip as it nears expiry.
                self._session_text.color = (
                    theme.WARNING if in_warning else theme.TEXT_SECONDARY
                )
                # Non-blocking banner instead of a modal: surface it inside the
                # warning window with an Extend action (when extensions remain).
                if in_warning:
                    self._session_banner_text.value = (
                        f"Your session expires in {mins:02d}:{secs:02d}."
                    )
                    self._extend_btn.visible = can_extend()
                    self._session_banner.visible = True
                else:
                    self._session_banner.visible = False
                try:
                    page.update()
                except Exception:
                    return
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def _on_extend(self, e):
        if extend_session():
            self._session_banner.visible = False
            page = getattr(self, "page", None)
            if page:
                page.update()

    def _on_logout(self, e):
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        clear_session()
        self.push_route("/login")
