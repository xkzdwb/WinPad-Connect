"""Sunshine 配置页：探测基线、锁定低延迟编码参数、备份与还原。"""

from __future__ import annotations

import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

from ... import sunshine, theme
from .. import widgets


class SunshinePage(tk.Frame):
    title = "Sunshine 配置"
    subtitle = "只做装配：找到基线、写入低延迟参数、保留可回滚的备份"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._target_encoder = ""
        self._build()

    # ---- 构建 -----------------------------------------------------------
    def _build(self) -> None:
        detect = widgets.Card(self, title="基线探测", accent=theme.ACCENT)
        detect.pack(fill="x")
        header = tk.Frame(detect.body, bg=theme.CARD)
        header.pack(fill="x")
        self.state_chip = widgets.Chip(header, "检测中", theme.AMBER)
        self.state_chip.pack(side="left")
        self.version_label = tk.Label(
            header, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8),
        )
        self.version_label.pack(side="left", padx=(8, 0))

        self.detect_grid = tk.Frame(detect.body, bg=theme.CARD)
        self.detect_grid.pack(fill="x", pady=(10, 0))
        self.detect_grid.grid_columnconfigure(0, weight=1, uniform="d")
        self.detect_grid.grid_columnconfigure(1, weight=1, uniform="d")
        self.path_value = widgets.kv_row(self.detect_grid, "安装目录", manage=False)
        self.path_value.master.grid(row=0, column=0, sticky="ew", padx=(0, 18))
        self.conf_value = widgets.kv_row(self.detect_grid, "配置文件", manage=False)
        self.conf_value.master.grid(row=0, column=1, sticky="ew")
        self.state_value = widgets.kv_row(self.detect_grid, "运行状态", manage=False)
        self.state_value.master.grid(row=1, column=0, sticky="ew", padx=(0, 18), pady=(4, 0))
        self.perm_value = widgets.kv_row(self.detect_grid, "配置可写", manage=False)
        self.perm_value.master.grid(row=1, column=1, sticky="ew", pady=(4, 0))

        buttons = tk.Frame(detect.body, bg=theme.CARD)
        buttons.pack(fill="x", pady=(14, 0))
        self.apply_btn = widgets.button(buttons, "应用低延迟配置", self._apply, kind="primary")
        self.apply_btn.pack(side="left")
        widgets.button(buttons, "还原最近备份", self._restore, kind="ghost").pack(side="left", padx=(6, 0))
        self.start_btn = widgets.button(buttons, "启动 Sunshine", self._start, kind="ghost")
        self.start_btn.pack(side="left", padx=(6, 0))
        self.stop_btn = widgets.button(buttons, "停止", self._stop, kind="danger")
        self.stop_btn.pack(side="left", padx=(6, 0))
        widgets.button(buttons, "打开 Web 后台", self._open_web, kind="blue").pack(side="left", padx=(6, 0))

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, pady=(12, 0))
        body.grid_columnconfigure(0, weight=3, uniform="s")
        body.grid_columnconfigure(1, weight=2, uniform="s")
        body.grid_rowconfigure(0, weight=1)

        profile_card = widgets.Card(body, title="编码参数", subtitle="写入前自动备份；只改目标键，保留你的其它配置")
        profile_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        picker = tk.Frame(profile_card.body, bg=theme.CARD)
        picker.pack(fill="x")
        tk.Label(picker, text="目标编码器", bg=theme.CARD, fg=theme.MUTED,
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.encoder_var = tk.StringVar()
        self.encoder_box = ttk.Combobox(
            picker, textvariable=self.encoder_var, state="readonly", width=26,
            values=[f"{key} · {value['label']}" for key, value in sunshine.LOW_LATENCY_PROFILES.items()],
        )
        self.encoder_box.pack(side="left", padx=(10, 0))
        self.encoder_box.bind("<<ComboboxSelected>>", lambda _e: self._on_encoder_changed())
        self.encoder_note = tk.Label(
            profile_card.body, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8), anchor="w", justify="left", wraplength=560,
        )
        self.encoder_note.pack(fill="x", pady=(6, 8))

        table_wrap = tk.Frame(profile_card.body, bg=theme.CARD)
        table_wrap.pack(fill="both", expand=True)
        self.table = widgets.Table(
            table_wrap, [("key", "配置键", 150), ("current", "当前值", 120), ("target", "将写入", 120), ("state", "状态", 80)],
            height=6,
        )
        self.table.pack(fill="both", expand=True)
        notes = tk.Frame(profile_card.body, bg=theme.CARD)
        notes.pack(fill="x", pady=(10, 0))
        for label, detail in [
            ("p4", "NVENC 低延迟预设：编码器优先响应速度，适合远程操作桌面。"),
            ("ll", "低延迟调优：减少帧内缓冲；码率恒定时画质让位于时延。"),
            ("cbr", "恒定码率：避免场景切换瞬间的带宽尖峰造成卡顿。"),
        ]:
            row = tk.Frame(notes, bg=theme.CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=theme.CARD, fg=theme.ACCENT,
                     font=("Consolas", 9, "bold"), width=6, anchor="w").pack(side="left")
            tk.Label(row, text=detail, bg=theme.CARD, fg=theme.FAINT,
                     font=("Microsoft YaHei UI", 8), anchor="w", justify="left",
                     wraplength=560).pack(side="left", fill="x", expand=True)

        self.apply_hint = tk.Label(
            profile_card.body, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8), anchor="w", justify="left", wraplength=560,
        )
        self.apply_hint.pack(fill="x", pady=(8, 0))

        right = tk.Frame(body, bg=theme.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        right.grid_rowconfigure(1, weight=1)

        notes = widgets.Card(right, title="说明与许可", accent=theme.PURPLE)
        notes.grid(row=0, column=0, sticky="ew")
        for text in [
            "基线：Foundation Sunshine（GPL-3.0），带 ZakoVDD 虚拟显示器。",
            "参数写入 config/sunshine.conf，重启 Sunshine 后生效。",
            "Web 后台：https://localhost:47990（首次登录需创建账号）。",
            "若安装目录在 Program Files，写配置需要管理员权限。",
            "Win-Pad Connect 不修改串流协议，只调整 Sunshine 官方配置项。",
        ]:
            row = tk.Frame(notes.body, bg=theme.CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="·", bg=theme.CARD, fg=theme.ACCENT,
                     font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(0, 6))
            tk.Label(row, text=text, bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 8),
                     anchor="w", justify="left", wraplength=358).pack(side="left", fill="x", expand=True)

        log_card = widgets.Card(right, title="Sunshine 日志", accent=theme.BLUE)
        log_card.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        log_head = tk.Frame(log_card.body, bg=theme.CARD)
        log_head.pack(fill="x")
        widgets.button(log_head, "刷新日志", self._refresh_log, kind="ghost").pack(side="left")
        self.log_hint = tk.Label(log_head, text="", bg=theme.CARD, fg=theme.FAINT,
                                 font=("Microsoft YaHei UI", 8))
        self.log_hint.pack(side="left", padx=(8, 0))
        self.log_view = widgets.LogView(log_card.body, height=8)
        self.log_view.pack(fill="both", expand=True, pady=(8, 0))
        self.log_view.set_placeholder("未检测到 Sunshine 日志。安装并启动一次后，这里显示日志尾部。")

    # ---- 数据刷新 -------------------------------------------------------
    def update_data(self, snapshot, checks, score) -> None:
        state = snapshot.sunshine
        if state.installed:
            self.state_chip.configure(text="已安装", bg=widgets._tint(theme.ACCENT, 0.16), fg=theme.ACCENT)
        else:
            self.state_chip.configure(text="未检测到", bg=widgets._tint(theme.AMBER, 0.16), fg=theme.AMBER)
        self.version_label.configure(text=f"Foundation Sunshine · 推荐 {snapshot.encoder_label}")
        self.path_value.configure(text=state.root or "—")
        self.conf_value.configure(text=state.conf or "—")
        self.state_value.configure(
            text=("运行中" if state.running else "未运行") if state.installed else "—",
            fg=theme.ACCENT if state.running else theme.MUTED,
        )
        writable = state.config_writable
        self.perm_value.configure(
            text="可写" if writable else ("只读，需管理员" if state.conf else "—"),
            fg=theme.ACCENT if writable else theme.AMBER,
        )
        if not self._target_encoder:
            self._target_encoder = snapshot.encoder or snapshot.recommended_encoder
            self._select_encoder(self._target_encoder)
        self.apply_hint.configure(
            text="写入前会在配置目录留时间戳备份；还原时取最近一份。"
            if state.installed else "完成 Sunshine 安装后，这里会自动识别安装目录与配置文件。"
        )
        self._fill_table()
        self._refresh_buttons()

    def _select_encoder(self, encoder: str) -> None:
        values = list(sunshine.LOW_LATENCY_PROFILES.keys())
        if encoder not in values:
            encoder = "software"
        index = values.index(encoder)
        self.encoder_box.current(index)
        self._target_encoder = encoder
        profile = sunshine.LOW_LATENCY_PROFILES[encoder]
        self.encoder_note.configure(text=f"{profile['label']} · 典型延迟 {profile['delay']} — {profile['notes']}")

    def _on_encoder_changed(self) -> None:
        index = self.encoder_box.current()
        values = list(sunshine.LOW_LATENCY_PROFILES.keys())
        if 0 <= index < len(values):
            self._target_encoder = values[index]
            profile = sunshine.LOW_LATENCY_PROFILES[self._target_encoder]
            self.encoder_note.configure(
                text=f"{profile['label']} · 典型延迟 {profile['delay']} — {profile['notes']}"
            )
            self._fill_table()

    def _fill_table(self) -> None:
        snapshot = self.app.snapshot
        if snapshot is None or not self._target_encoder:
            return
        current = snapshot.sunshine.config
        profile = sunshine.LOW_LATENCY_PROFILES[self._target_encoder]
        rows = []
        states = []
        for key, value in profile["keys"]:
            now = current.get(key, "—")
            same = now == value
            rows.append((key, now, value, "一致" if same else "将修改"))
            states.append("ok" if same else "warn")
        self.table.set_rows(rows, states)

    def _refresh_buttons(self) -> None:
        snapshot = self.app.snapshot
        installed = bool(snapshot and snapshot.sunshine.installed)
        widgets.set_button_enabled(self.apply_btn, installed)
        widgets.set_button_enabled(self.start_btn, installed and not snapshot.sunshine.running)
        widgets.set_button_enabled(self.stop_btn, bool(snapshot and snapshot.sunshine.running))

    # ---- 动作 -----------------------------------------------------------
    def _apply(self) -> None:
        snapshot = self.app.snapshot
        if snapshot is None or not snapshot.sunshine.installed:
            messagebox.showinfo("未检测到 Sunshine", "请先安装 Foundation Sunshine 基线。")
            return
        conf = snapshot.sunshine.conf
        encoder = self._target_encoder
        if not conf:
            messagebox.showerror("没有配置文件", "没有找到 sunshine.conf，请先在 Sunshine Web 后台完成一次保存。")
            return
        if not messagebox.askyesno(
            "写入低延迟配置",
            f"将向\n{conf}\n写入 {encoder} 的低延迟参数。\n\n写入前会自动备份，可随时还原。继续？",
        ):
            return
        self.apply_hint.configure(text="正在写入…", fg=theme.MUTED)

        def work():
            return sunshine.apply_profile(conf, encoder)

        def done(result):
            ok, message = result
            self.apply_hint.configure(text=message, fg=theme.ACCENT if ok else theme.RED)
            self.app.log(("配置已应用：" if ok else "配置写入失败：") + message, "ok" if ok else "error")
            if ok:
                self.app.refresh_all()

        self.app.run_async(work, done)

    def _restore(self) -> None:
        snapshot = self.app.snapshot
        if snapshot is None or not snapshot.sunshine.conf:
            messagebox.showinfo("没有配置", "尚未检测到 Sunshine 配置文件。")
            return
        backup = sunshine.latest_backup(snapshot.sunshine.conf)
        if backup is None:
            messagebox.showinfo("没有备份", "没有找到可用的 .bak 备份。")
            return
        if not messagebox.askyesno("还原备份", f"用 {backup.name} 覆盖当前配置？\n覆盖后需重启 Sunshine。"):
            return

        def work():
            return sunshine.restore_backup(snapshot.sunshine.conf)

        def done(result):
            ok, message = result
            self.apply_hint.configure(text=message, fg=theme.ACCENT if ok else theme.RED)
            self.app.log(("已还原配置：" if ok else "还原失败：") + message, "ok" if ok else "error")
            if ok:
                self.app.refresh_all()

        self.app.run_async(work, done)

    def _start(self) -> None:
        snapshot = self.app.snapshot
        if snapshot is None:
            return

        def work():
            return sunshine.start(snapshot.sunshine)

        def done(result):
            ok, message = result
            self.app.log(("Sunshine 启动：" if ok else "Sunshine 启动失败：") + message, "ok" if ok else "error")
            self.after(1200, self.app.refresh_all)

        self.app.run_async(work, done)

    def _stop(self) -> None:
        if not messagebox.askyesno("停止 Sunshine", "结束 sunshine.exe？正在串流的会话会中断。"):
            return
        self.app.run_async(sunshine.stop, lambda result: self.after(800, self.app.refresh_all))

    def _open_web(self) -> None:
        import webbrowser

        webbrowser.open("https://localhost:47990")

    def _refresh_log(self) -> None:
        snapshot = self.app.snapshot
        if snapshot is None:
            return
        tail, error = sunshine.log_tail(snapshot.sunshine, lines=120)
        self.log_view.clear()
        if error:
            self.log_hint.configure(text=error, fg=theme.AMBER)
            return
        self.log_hint.configure(text="最近 120 行", fg=theme.FAINT)
        for line in tail.splitlines():
            tag = "error" if "error" in line.lower() or "fatal" in line.lower() else "info"
            self.log_view.append(line, tag)
