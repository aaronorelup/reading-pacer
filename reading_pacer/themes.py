"""
themes.py — Catppuccin colour palettes (Mocha dark, Latte light).
Single source of truth for all UI colours; the active palette is chosen
from config at startup (restart to apply a theme change).
"""

from reading_pacer.config import config

MOCHA = {
    "base":     "#1e1e2e",
    "mantle":   "#181825",
    "crust":    "#11111b",
    "surface0": "#313244",
    "surface1": "#45475a",
    "surface2": "#585b70",
    "overlay0": "#6c7086",
    "subtext0": "#a6adc8",
    "subtext1": "#bac2de",
    "text":     "#cdd6f4",
    "lavender": "#b4befe",
    "blue":     "#89b4fa",
    "green":    "#a6e3a1",
    "peach":    "#fab387",
    "red":      "#f38ba8",
    "line_hl":  "#252538",
}

LATTE = {
    "base":     "#eff1f5",
    "mantle":   "#e6e9ef",
    "crust":    "#dce0e8",
    "surface0": "#ccd0da",
    "surface1": "#bcc0cc",
    "surface2": "#acb0be",
    "overlay0": "#9ca0b0",
    "subtext0": "#6c6f85",
    "subtext1": "#5c5f77",
    "text":     "#4c4f69",
    "lavender": "#7287fd",
    "blue":     "#1e66f5",
    "green":    "#40a02b",
    "peach":    "#fe640b",
    "red":      "#d20f39",
    "line_hl":  "#e2e4f2",
}

# Active palette for this session
C = LATTE if config.theme == "latte" else MOCHA

# On light theme, colored buttons need light text; "crust" works for both:
# dark crust on light palette's vivid accents, near-black on mocha's pastels.
BTN_FG = MOCHA["crust"] if config.theme == "mocha" else LATTE["base"]
