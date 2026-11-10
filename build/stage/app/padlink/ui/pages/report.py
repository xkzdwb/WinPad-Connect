"""体检报告页：完整检查项、下一步建议、导出 TXT/JSON。"""

from __future__ import annotations

import os
import tkinter as tk

from ... import paths
from ... import theme
from .. import widgets


STATUS_TEXT = {"ok": "通过", "warn": "可改进", "fail": "未完成", "unknown": "未知"}


class ReportPage(tk.Frame):
    title = "体检报告"
    subtitle = "导出一份可交付的基线报告，记录当前配置与改进项"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._build()

    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=3, uniform="rep")
        top.grid_columnconfigure(1, weight=2, uniform="rep")

        summary = widgets.Card(top, title="基线摘要", accent=theme.ACCENT)
        summary.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        body = tk.Frame(summary.body, bg=theme.CARD)
        body.pack(fill="x")
        self.gauge = widgets.ScoreGauge(body, size=140)
        self.gauge.pack(side="left", padx=(0, 18))
        info = tk.Frame(body, bg=theme.CARD)
        info.pack(side="left", fill="both", expand=True)
        self.headline = tk.Label(
            info, text="", bg=theme.CARD, fg=theme.TEXT, font=("Microsoft YaHei UI", 11, "bold"),
            anchor="w", justify="left", wraplength=420,
        )
        self.headline.pack(fill="x")
        self.counts = tk.Label(
            info, text="", bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 9),
            anchor="w", justify="left",
        )
        self.counts.pack(fill="x", pady=(6, 0))
        self.meta = tk.Label(
            info, text="", bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
            anchor="w", justify="left", wraplength=420,
        )
        self.meta.pack(fill="x", pady=(6, 0))

        todo = widgets.Card(top, title="下一步建议", accent=theme.AMBER)
        todo.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.todo_box = tk.Frame(todo.body, bg=theme.CARD)
        self.todo_box.pack(fill="both", expand=True)

        preview = widgets.Card(self, title="报告预览", subtitle="纯文本，可直接粘贴给同事或存档")
        preview.pack(fill="both", expand=True, pady=(12, 0))
        actions = tk.Frame(preview.body, bg=theme.CARD)
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        text_wrap = tk.Frame(preview.body, bg=theme.BORDER)
        text_wrap.pack(fill="both", expand=True)
        self.text = tk.Text(
            text_wrap, bg=theme.CARD_ALT, fg=theme.TEXT, insertbackground=theme.TEXT,
            font=("Consolas", 9), relief="flat", wrap="none", padx=12, pady=10,
            selectbackground=theme.BLUE, selectforeground="#08101f",
        )
        self.text.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        scroll = tk.Scrollbar(
            text_wrap, command=self.text.yview, width=10, bg=theme.CARD_ALT,
            troughcolor=theme.CARD, activebackground=theme.BORDER, relief="flat",
            bd=0, highlightthickness=0,
        )
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set, state="disabled")
        widgets.button(actions, "保存 TXT", lambda: self._save("txt"), kind="primary").pack(side="left")
        widgets.button(actions, "保存 JSON", lambda: self._save("json"), kind="blue").pack(side="left", padx=(6, 0))
        widgets.button(actions, "复制全文", self._copy, kind="ghost").pack(side="left", padx=(6, 0))
        widgets.button(actions, "打开报告目录", self._open_dir, kind="ghost").pack(side="right")
        self.saved = tk.Label(actions, text="", bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8))
        self.saved.pack(side="right", padx=10)

    # ---- 动作 -----------------------------------------------------------
    def _save(self, fmt: str) -> None:
        try:
            path = self.app.save_report(fmt)
        except OSError as exc:
            self.saved.configure(text=f"保存失败：{exc}", fg=theme.RED)
            return
        self.saved.configure(text=f"已保存 {path.name}", fg=theme.ACCENT)

    def _copy(self) -> None:
        self.app.copy(self.app.report_text(), "体检报告")

    def _open_dir(self) -> None:
        try:
            os.startfile(str(paths.reports_dir()))  # type: ignore[attr-defined]
        except OSError as exc:
            self.app.log(f"无法打开报告目录：{exc}", "warn")

    # ---- 刷新 -----------------------------------------------------------
    def update_data(self, snapshot, checks, score) -> None:
        from ... import checks as checks_mod

        self.gauge.set(score, "就绪度")
        self.headline.configure(text=checks_mod.headline(score, checks))
        counts = checks_mod.summary(checks)
        self.counts.configure(
            text=f"通过 {counts['ok']} 项 · 可改进 {counts['warn']} 项 · "
                 f"未完成 {counts['fail']} 项 · 未知 {counts['unknown']} 项"
        )
        self.meta.configure(
            text=f"{snapshot.os.hostname} · {snapshot.os.name} build {snapshot.os.build}\n"
                 f"{snapshot.cpu} · {snapshot.ram_gb:.0f} GB · {snapshot.encoder_label}"
        )

        for child in self.todo_box.winfo_children():
            child.destroy()
        actionable = [check for check in checks if check.status != "ok"]
        if not actionable:
            tk.Label(
                self.todo_box, text="全部检查通过，可以开始串流了。\n\n"
                     "异地使用前，再确认 Tailscale 显示为「直连」。" ,
                bg=theme.CARD, fg=theme.ACCENT, font=("Microsoft YaHei UI", 9),
                justify="left", anchor="w", wraplength=380,
            ).pack(fill="x")
        else:
            for index, check in enumerate(actionable[:5], start=1):
                color = theme.STATUS_COLORS.get(check.status, theme.FAINT)
                row = tk.Frame(self.todo_box, bg=theme.CARD)
                row.pack(fill="x", pady=(0, 9))
                tk.Label(
                    row, text=str(index), bg=widgets._tint(color, 0.22), fg=color,
                    font=("Microsoft YaHei UI", 8, "bold"), width=2,
                ).pack(side="left", anchor="n")
                text = tk.Frame(row, bg=theme.CARD)
                text.pack(side="left", fill="x", expand=True, padx=(8, 0))
                tk.Label(
                    text, text=f"{check.title}（{STATUS_TEXT.get(check.status, check.status)}）",
                    bg=theme.CARD, fg=theme.TEXT, font=("Microsoft YaHei UI", 9, "bold"),
                    anchor="w", justify="left", wraplength=330,
                ).pack(fill="x")
                tk.Label(
                    text, text=check.hint or check.detail, bg=theme.CARD, fg=theme.MUTED,
                    font=("Microsoft YaHei UI", 8), anchor="w", justify="left", wraplength=330,
                ).pack(fill="x")

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.app.report_text())
        self.text.configure(state="disabled")
