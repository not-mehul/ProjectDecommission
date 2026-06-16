"""Home / dashboard screen.

With the persistent sidebar now owning navigation, org/session chips, and
logout, Home is a compact landing dashboard rather than the app's primary
navigation surface: a short intro, a tidy row of tool cards, and a keyboard
shortcut hint. The session countdown and auto-logout live in `ShellView`.
"""

import flet as ft

import theme
from components import banner, card
from pages.app_shell import ShellView

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


class HomeView(ShellView):
    def __init__(self, push_route, pop_route, **kwargs):
        super().__init__(
            route="/home",
            title="Home",
            subtitle="Pick a tool to get started.",
            push_route=push_route,
            pop_route=pop_route,
            **kwargs,
        )
        self._build_ui()

    def _build_ui(self):
        cards_row = ft.Row(
            [self._tool_card(*t) for t in _TOOLS],
            spacing=theme.SPACE_LG,
        )

        body = ft.Column(
            [
                cards_row,
                ft.Container(height=theme.SPACE_XL),
                banner(
                    "Tip: press Cmd/Ctrl-K to jump Home, Esc to go back, "
                    "and Cmd/Ctrl-, to log out.",
                    kind="info",
                ),
            ],
        )
        self.render(body)

    def _tool_card(self, route, title, icon, brand, description) -> ft.Control:
        inner = card(
            ft.Column(
                [
                    ft.Container(
                        width=44,
                        height=44,
                        border_radius=theme.RADIUS_MD,
                        bgcolor=theme.palette.tint(brand, 0.16),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=22, color=brand),
                    ),
                    ft.Container(height=theme.SPACE_LG),
                    ft.Text(
                        title,
                        size=theme.FONT_SUBTITLE,
                        color=theme.TEXT_PRIMARY,
                        weight=theme.WEIGHT_SEMIBOLD,
                    ),
                    ft.Container(height=theme.SPACE_XS),
                    ft.Text(
                        description,
                        size=theme.FONT_CAPTION,
                        color=theme.TEXT_SECONDARY,
                    ),
                ],
            ),
            padding=theme.SPACE_XL,
            expand=True,
            on_click=lambda _, r=route: self.push_route(r),
            ink=True,
        )
        # Hover affordance: accent border + lift.
        inner.animate = ft.Animation(160, ft.AnimationCurve.EASE_IN_OUT)
        wrapper = ft.Container(content=inner, expand=1, height=220)
        wrapper.on_hover = lambda e, c=inner: self._hover(e, c)
        return wrapper

    def _hover(self, e, c: ft.Container):
        if e.data == "true":
            c.border = ft.Border.all(1, theme.ACCENT)
            c.shadow = theme.elevation(2)
        else:
            c.border = ft.Border.all(1, theme.BORDER)
            c.shadow = theme.elevation(1)
        page = getattr(self, "page", None)
        if page:
            page.update()
