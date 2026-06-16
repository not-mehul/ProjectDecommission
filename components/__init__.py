"""Reusable UI building blocks for vCommander.

These wrap the styling patterns that were previously re-implemented in each
view (text fields, dropdowns, buttons, cards, banners). Every component
reads its colors/spacing/radius from `theme`, so a token change or a theme
switch propagates everywhere instead of being copy-pasted per screen.

Import from the package root:

    from components import primary_button, text_field, card, section_header
"""

from components.buttons import (
    danger_button,
    ghost_button,
    primary_button,
    secondary_button,
    set_button_loading,
)
from components.inputs import dropdown, text_field
from components.surfaces import (
    badge,
    banner,
    card,
    section_header,
    stat_row,
)

__all__ = [
    "primary_button",
    "secondary_button",
    "danger_button",
    "ghost_button",
    "set_button_loading",
    "text_field",
    "dropdown",
    "card",
    "section_header",
    "stat_row",
    "banner",
    "badge",
]
