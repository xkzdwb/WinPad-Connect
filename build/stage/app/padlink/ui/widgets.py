"""可复用的小部件：卡片、按钮、状态点、评分环、日志、表格。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Sequence

from .. import theme


class Card(tk.Frame):
    """带左侧强调条、标题和正文区域的容器。"""

    def __init__(
        self,
        parent: tk.Misc,
        title: str = "",
        subtitle: str = "",
        accent: str = theme.ACCENT,
        pad: int = 16,
        **kwargs,
    ) -> None:
        super().__init__(
            parent, bg=theme.CARD, highlightbackground=theme.BORDER,
            highlightthickness=1, bd=0, **kwargs,
        )
        self.accent = accent
        if accent:
            tk.Frame(self, bg=accent, width=3).pack(side="left", fill="y")
        content = tk.Frame(self, bg=theme.CARD, padx=pad, pady=pad)
        content.pack(side="left", fill="both", expand=True)
        self.content = content
        if title:
            head = tk.Frame(content, bg=theme.CARD)
            head.pack(fill="x")
            tk.Label(
                head, text=title, bg=theme.CARD, fg=theme.TEXT,
                font=("Microsoft YaHei UI", 11, "bold"), anchor="w",
            ).pack(side="left")
            self.title_label = head
            if subtitle:
                tk.Label(
                    content, text=subtitle, bg=theme.CARD, fg=theme.MUTED,
                    font=("Microsoft YaHei UI", 9), anchor="w", justify="left",
                    wraplength=760,
                ).pack(fill="x", pady=(3, 0))
        self.body = tk.Frame(content, bg=theme.CARD)
        self.body.pack(fill="both", expand=True, pady=(10, 0) if title else 0)


class Chip(tk.Label):
    def __init__(self, parent: tk.Misc, text: str, tone: str = theme.ACCENT, font=None, **kwargs):
        super().__init__(
            parent, text=text, bg=_tint(tone, 0.16), fg=tone, font=font or ("Microsoft YaHei UI", 8, "bold"),
            padx=8, pady=2, bd=0, **kwargs,
        )


def _tint(color: str, ratio: float) -> str:
    """把强调色与卡片底色混合，得到柔和的底色。"""
    def parse(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    r1, g1, b1 = parse(color)
    r2, g2, b2 = parse(theme.CARD)
    mix = lambda a, b: int(b + (a - b) * ratio)
    return f"#{mix(r1, r2):02x}{mix(g1, g2):02x}{mix(b1, b2):02x}"


class StatusDot(tk.Canvas):
    def __init__(self, parent: tk.Misc, color: str = theme.ACCENT, size: int = 10, **kwargs):
        super().__init__(parent, width=size, height=size, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, **kwargs)
        self._size = size
        self._dot = self.create_oval(0, 0, size, size, fill=color, outline="")
        self.color = color

    def set_color(self, color: str) -> None:
        self.color = color
        self.itemconfigure(self._dot, fill=color)


def button(
    parent: tk.Misc, text: str, command: Callable[[], None],
    kind: str = "primary", width: int = 0, font=None,
) -> tk.Button:
    palette = {
        "primary": (theme.ACCENT, "#08231a", theme.ACCENT_DARK),
        "blue": (theme.BLUE, "#04182c", "#3f8fe0"),
        "ghost": (theme.CARD_ALT, theme.TEXT, theme.CARD_HOVER),
        "danger": (_tint(theme.RED, 0.22), theme.RED, _tint(theme.RED, 0.32)),
    }
    background, foreground, hover = palette.get(kind, palette["primary"])
    btn = tk.Button(
        parent, text=text, command=command, bg=background, fg=foreground,
        activebackground=hover, activeforeground=foreground, font=font or ("Microsoft YaHei UI", 9, "bold"),
        relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
        highlightthickness=0, width=width,
    )
    btn.bind("<Enter>", lambda _e: btn.configure(bg=hover) if btn["state"] != "disabled" else None)
    btn.bind("<Leave>", lambda _e: btn.configure(bg=background) if btn["state"] != "disabled" else None)
    btn._base_bg = background  # type: ignore[attr-defined]
    btn._hover_bg = hover  # type: ignore[attr-defined]
    return btn


def set_button_enabled(btn: tk.Button, enabled: bool) -> None:
    if enabled:
        btn.configure(state="normal", bg=getattr(btn, "_base_bg", theme.ACCENT))
    else:
        btn.configure(state="disabled", bg=theme.CARD_ALT)


class ScoreGauge(tk.Canvas):
    """270° 圆环评分，中心显示分数与标签。"""

    def __init__(self, parent: tk.Misc, size: int = 168, bg: str | None = None, **kwargs):
        super().__init__(
            parent, width=size, height=size, bg=bg or theme.CARD,
            highlightthickness=0, bd=0, **kwargs,
        )
        self.size = size
        self._arc = None
        self._score_text = self.create_text(
            size / 2, size / 2 - 6, text="--", fill=theme.TEXT,
            font=("Microsoft YaHei UI", 30, "bold"),
        )
        self._label_text = self.create_text(
            size / 2, size / 2 + 26, text="", fill=theme.MUTED,
            font=("Microsoft YaHei UI", 8),
        )
        self._draw_ring(theme.BORDER, 0)

    def _draw_ring(self, color: str, extent: float) -> None:
        pad = 12
        if self._arc is not None:
            self.delete(self._arc)
        self._arc = self.create_arc(
            pad, pad, self.size - pad, self.size - pad,
            start=225, extent=-extent, style="arc", outline=color,
            width=11,
        )

    def set(self, score: int, label: str = "") -> None:
        score = max(0, min(100, int(score)))
        color = theme.ACCENT if score >= 85 else theme.AMBER if score >= 60 else theme.RED
        self._draw_ring(color, 270 * score / 100)
        self.itemconfigure(self._score_text, text=str(score), fill=color)
        self.itemconfigure(self._label_text, text=label)


class StatTile(tk.Frame):
    def __init__(self, parent: tk.Misc, label: str, value: str = "--", hint: str = "", accent: str = theme.BLUE):
        super().__init__(parent, bg=theme.CARD_ALT, highlightbackground=theme.BORDER, highlightthickness=1)
        inner = tk.Frame(self, bg=theme.CARD_ALT, padx=14, pady=11)
        inner.pack(fill="both", expand=True)
        tk.Frame(inner, bg=accent, height=2).pack(fill="x", pady=(0, 8))
        self.value_label = tk.Label(
            inner, text=value, bg=theme.CARD_ALT, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 15, "bold"), anchor="w",
        )
        self.value_label.pack(fill="x")
        tk.Label(
            inner, text=label, bg=theme.CARD_ALT, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 9), anchor="w",
        ).pack(fill="x", pady=(4, 0))
        self.hint_label = tk.Label(
            inner, text=hint, bg=theme.CARD_ALT, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8), anchor="w", justify="left",
            wraplength=200,
        )
        self.hint_label.pack(fill="x")

    def set(self, value: str, hint: str | None = None) -> None:
        self.value_label.configure(text=value)
        if hint is not None:
            self.hint_label.configure(text=hint)


class LogView(tk.Frame):
    def __init__(self, parent: tk.Misc, height: int = 8, bg: str = theme.CARD):
        super().__init__(parent, bg=bg)
        self.text = tk.Text(
            self, height=height, bg=bg, fg=theme.MUTED, insertbackground=theme.TEXT,
            relief="flat", bd=0, font=("Consolas", 9), wrap="word", padx=8, pady=6,
            selectbackground=theme.CARD_HOVER,
        )
        self.text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure("info", foreground=theme.MUTED)
        self.text.tag_configure("ok", foreground=theme.ACCENT)
        self.text.tag_configure("warn", foreground=theme.AMBER)
        self.text.tag_configure("error", foreground=theme.RED)
        self.text.tag_configure("title", foreground=theme.TEXT)
        self.text.tag_configure("placeholder", foreground=theme.FAINT)
        self.text.configure(state="disabled")
        self._placeholder = None

    def set_placeholder(self, message: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", message, "placeholder")
        self._placeholder = message
        self.text.configure(state="disabled")

    def append(self, message: str, tag: str = "info") -> None:
        import datetime

        if self._placeholder is not None:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self._placeholder = None
            self.text.configure(state="disabled")
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", f"{stamp}  {message}\n", tag)
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > 400:
            self.text.delete("1.0", f"{lines - 400}.0")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class Table(tk.Frame):
    def __init__(self, parent: tk.Misc, columns: Sequence[tuple[str, str, int]], height: int = 5, bg: str = theme.CARD):
        super().__init__(parent, bg=bg)
        self.columns = list(columns)
        self.tree = ttk.Treeview(
            self, columns=[c[0] for c in columns], show="headings", height=height,
        )
        for key, title, width in columns:
            self.tree.heading(key, text=title, anchor="w")
            self.tree.column(key, width=width, anchor="w", stretch=True)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack_forget()
        self.tree.tag_configure("muted", foreground=theme.MUTED)
        self.tree.tag_configure("warn", foreground=theme.AMBER)
        self.tree.tag_configure("ok", foreground=theme.ACCENT)

    def set_rows(self, rows: Iterable[Sequence[str]], tags: Iterable[str] | None = None) -> None:
        rows = list(rows)
        tag_list = list(tags) if tags is not None else []
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(rows):
            tag = tag_list[index] if index < len(tag_list) else "muted"
            self.tree.insert("", "end", values=list(row), tags=(tag,) if tag else ())
        self.tree.configure(height=max(1, min(12, len(rows))))
        if len(rows) > 12 and not self.scroll.winfo_ismapped():
            self.scroll.pack(side="right", fill="y", before=self.tree)
        elif len(rows) <= 12 and self.scroll.winfo_ismapped():
            self.scroll.pack_forget()


class Divider(tk.Frame):
    def __init__(self, parent: tk.Misc, bg: str = theme.CARD):
        super().__init__(parent, bg=bg)
        tk.Frame(self, bg=theme.BORDER, height=1).pack(fill="x", pady=6)


def kv_row(parent: tk.Misc, label: str, value: str = "--", bg: str = theme.CARD, value_font=None,
           manage: bool = True, wrap: int = 0, label_width: int = 14) -> tk.Label:
    row = tk.Frame(parent, bg=bg)
    if manage:
        row.pack(fill="x", pady=2)
    tk.Label(row, text=label, bg=bg, fg=theme.MUTED, font=("Microsoft YaHei UI", 9), width=label_width, anchor="w").pack(side="left")
    value_label = tk.Label(
        row, text=value, bg=bg, fg=theme.TEXT, font=value_font or ("Microsoft YaHei UI", 9), anchor="w",
        justify="left", wraplength=wrap or 0,
    )
    value_label.pack(side="left", fill="x", expand=True)
    return value_label


def scrollable(parent: tk.Misc, bg: str = theme.BG) -> tuple[tk.Frame, tk.Frame]:
    """返回 (outer, inner)：inner 是可滚动的页面容器。"""
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    canvas.pack(side="left", fill="both", expand=True)
    bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)

    inner = tk.Frame(canvas, bg=bg)
    window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def sync_bar() -> None:
        bbox = canvas.bbox("all")
        needed = bool(bbox) and bbox[3] > canvas.winfo_height() + 2
        if needed and not bar.winfo_ismapped():
            bar.pack(side="right", fill="y", before=canvas)
        elif not needed and bar.winfo_ismapped():
            bar.pack_forget()

    def on_configure(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(window, width=canvas.winfo_width())
        sync_bar()

    inner.bind("<Configure>", on_configure)
    canvas.bind("<Configure>", on_configure)

    def on_wheel(event):
        delta = -1 if event.delta > 0 else 1
        canvas.yview_scroll(delta * 3, "units")

    def bind_wheel(_event):
        canvas.bind_all("<MouseWheel>", on_wheel)

    def unbind_wheel(_event):
        canvas.unbind_all("<MouseWheel>")

    canvas.bind("<Enter>", bind_wheel)
    canvas.bind("<Leave>", unbind_wheel)
    return outer, inner
