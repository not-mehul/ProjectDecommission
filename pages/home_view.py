"""Home / dashboard screen.

With the persistent sidebar now owning navigation, org/session chips, and
logout, Home is a compact landing dashboard rather than the app's primary
navigation surface: a short intro, a tidy row of tool cards, and a keyboard
shortcut hint. The session countdown and auto-logout live in `ShellView`.
"""

import flet as ft

import theme
from components import card
from pages.app_shell import ToolView

# (route, title, icon, brand tint, description) for the three tool cards.
_TOOLS = [
    (
        "/commission",
        "Commission",
        ft.Icons.BUSINESS_ROUNDED,
        theme.BRAND_COMMISSION,
        "Set up sites, claim devices, and configure templates.",
    ),
    (
        "/users",
        "User Management",
        ft.Icons.PEOPLE_ALT_ROUNDED,
        theme.BRAND_USERS,
        "Import and invite guest participants from external orgs.",
    ),
    (
        "/decommission",
        "Decommission",
        ft.Icons.DELETE_SWEEP_ROUNDED,
        theme.BRAND_DECOMMISSION,
        "Scan and remove assets with dependency-aware ordering.",
    ),
]


class HomeView(ToolView):
    def __init__(self, push_route, pop_route):
        super().__init__(
            push_route,
            pop_route,
            route="/home",
            title="Home",
            subtitle="Pick a tool to get started.",
        )
        self._build_ui()

    def _build_ui(self):
        # Three tall tiles that fill the content area down to the bottom.
        cards_row = ft.Row(
            [self._tool_card(*t) for t in _TOOLS],
            spacing=theme.SPACE_LG,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
        self.mount(cards_row)

    def _tool_card(self, route, title, icon, brand, description) -> ft.Control:
        chevron = ft.Icon(
            ft.Icons.ARROW_FORWARD_ROUNDED, size=18, color=theme.TEXT_MUTED
        )
        inner = card(
            ft.Column(
                [
                    # Icon tile + navigate arrow pinned to the top edge…
                    ft.Row(
                        [
                            ft.Container(
                                width=48,
                                height=48,
                                border_radius=theme.RADIUS_MD,
                                bgcolor=theme.palette.tint(brand, 0.16),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(icon, size=24, color=brand),
                            ),
                            chevron,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # …a flexible spacer pushes the label block to the bottom.
                    ft.Container(expand=True),
                    ft.Text(
                        title,
                        size=theme.FONT_HEADING,
                        color=theme.TEXT_PRIMARY,
                        weight=theme.WEIGHT_SEMIBOLD,
                    ),
                    ft.Container(height=theme.SPACE_XS),
                    ft.Text(
                        description,
                        size=theme.FONT_BODY,
                        color=theme.TEXT_SECONDARY,
                    ),
                ],
                spacing=0,
                expand=True,
            ),
            padding=theme.SPACE_XL,
            expand=True,
            on_click=lambda _, r=route: self.push_route(r),
            ink=True,
        )
        inner.animate = ft.Animation(160, ft.AnimationCurve.EASE_IN_OUT)
        wrapper = ft.Container(content=inner, expand=1)
        wrapper.on_hover = lambda e, c=inner, ch=chevron: self._hover(e, c, ch)
        return wrapper

    def _hover(self, e, c: ft.Container, chevron: ft.Icon):
        active = e.data == "true"
        c.border = ft.Border.all(1, theme.ACCENT if active else theme.BORDER)
        c.shadow = theme.elevation(2 if active else 1)
        chevron.color = theme.ACCENT if active else theme.TEXT_MUTED
        page = getattr(self, "page", None)
        if page:
            page.update()
