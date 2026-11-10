"""PadLink Host 视觉主题：深色、低饱和、单一强调色。"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---- 色板 ----------------------------------------------------------------
BG = "#0b1220"
SIDEBAR = "#0e1628"
CARD = "#131e33"
CARD_ALT = "#17243c"
CARD_HOVER = "#1c2b47"
BORDER = "#22324f"
TEXT = "#e6edf7"
MUTED = "#8da2c0"
FAINT = "#5d7290"
ACCENT = "#3ddc97"
ACCENT_DARK = "#22b87a"
BLUE = "#5aa9ff"
AMBER = "#f5b83d"
RED = "#ff6b6b"
PURPLE = "#a78bfa"

STATUS_COLORS = {
    "ok": ACCENT,
    "warn": AMBER,
    "fail": RED,
    "unknown": FAINT,
}

FONT_FAMILY = "Microsoft YaHei UI"
MONO_FAMILY = "Consolas"


def _pick_family(root: tk.Misc, preferred: str, fallback: str) -> str:
    families = set(tkfont.families(root))
    return preferred if preferred in families else fallback


class Fonts:
    def __init__(self, root: tk.Misc) -> None:
        ui = _pick_family(root, FONT_FAMILY, "Segoe UI")
        mono = _pick_family(root, MONO_FAMILY, "Courier New")
        self.ui = ui
        self.mono = mono
        self.h1 = (ui, 22, "bold")
        self.h2 = (ui, 15, "bold")
        self.h3 = (ui, 11, "bold")
        self.body = (ui, 10)
        self.small = (ui, 9)
        self.tiny = (ui, 8)
        self.mono_body = (mono, 9)
        self.big_number = (ui, 30, "bold")
        self.mid_number = (ui, 18, "bold")


def apply(root: tk.Misc) -> Fonts:
    root.configure(bg=BG)
    fonts = Fonts(root)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=fonts.body)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("Sidebar.TFrame", background=SIDEBAR)
    style.configure("TLabel", background=BG, foreground=TEXT, font=fonts.body)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=fonts.small)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=fonts.body)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=fonts.small)
    style.configure("CardTitle.TLabel", background=CARD, foreground=TEXT, font=fonts.h3)

    style.configure(
        "Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        borderwidth=0,
        bordercolor=CARD,
        lightcolor=CARD,
        darkcolor=CARD,
        rowheight=26,
        font=fonts.body,
    )
    style.configure(
        "Treeview.Heading",
        background=CARD_ALT,
        foreground=MUTED,
        relief="flat",
        font=fonts.small,
    )
    style.map(
        "Treeview",
        background=[("selected", CARD_HOVER)],
        foreground=[("selected", TEXT)],
    )
    style.map("Treeview.Heading", background=[("active", CARD_HOVER)])

    style.configure(
        "Vertical.TScrollbar",
        background=CARD_ALT,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        relief="flat",
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=CARD_ALT,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        relief="flat",
    )
    style.configure(
        "TEntry",
        fieldbackground=CARD_ALT,
        foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
    )
    style.configure(
        "TCombobox",
        fieldbackground=CARD_ALT,
        background=CARD_ALT,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=BORDER,
    )
    style.map("TCombobox", fieldbackground=[("readonly", CARD_ALT)])
    style.configure("TSeparator", background=BORDER)
    return fonts
