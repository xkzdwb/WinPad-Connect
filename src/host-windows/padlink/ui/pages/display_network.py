"""显示与网络页：虚拟显示器、Tailscale 链路、网关延迟。"""

from __future__ import annotations

import os
import subprocess
import tkinter as tk

from ... import platform_windows as win
from ... import theme
from .. import widgets


class DisplayNetworkPage(tk.Frame):
    title = "显示与网络"
    subtitle = "熄屏串流依赖虚拟显示器；异地串流依赖 Tailscale 直连"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._gateway = ""
        self._build()

    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill="both", expand=True)
        top.grid_columnconfigure(0, weight=3, uniform="dn")
        top.grid_columnconfigure(1, weight=2, uniform="dn")
        top.grid_rowconfigure(0, weight=3)
        top.grid_rowconfigure(1, weight=2)

        displays = widgets.Card(top, title="显示器与虚拟屏", subtitle="串流时可自动创建 3392×2400 的虚拟显示器")
        displays.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.display_table = widgets.Table(
            displays.body,
            [
                ("device", "设备", 92),
                ("adapter", "适配器", 230),
                ("mode", "当前分辨率", 108),
                ("refresh", "刷新率", 74),
                ("type", "类型", 64),
            ],
            height=4,
        )
        self.display_table.pack(fill="both", expand=True)
        tk.Label(
            displays.body, text="只显示处于活动状态的输出；虚拟屏在串流期间才会出现。",
            bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8), anchor="w",
        ).pack(fill="x", pady=(6, 0))

        vdd = widgets.Card(top, title="虚拟显示器（VDD）", accent=theme.PURPLE)
        vdd.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.vdd_chip = widgets.Chip(vdd.body, "检测中", theme.AMBER)
        self.vdd_chip.pack(anchor="w")
        self.vdd_text = tk.Label(
            vdd.body, text="", bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 8),
            justify="left", anchor="w", wraplength=330,
        )
        self.vdd_text.pack(fill="x", pady=(8, 0))
        vdd_buttons = tk.Frame(vdd.body, bg=theme.CARD)
        vdd_buttons.pack(fill="x", pady=(10, 0))
        widgets.button(vdd_buttons, "设备管理器", self._open_devmgmt, kind="ghost").pack(side="left")
        widgets.button(vdd_buttons, "显示设置", self._open_display_settings, kind="ghost").pack(side="left", padx=(6, 0))

        widgets.Divider(vdd.body)
        tk.Label(vdd.body, text="熄屏串流检查清单", bg=theme.CARD, fg=theme.MUTED,
                 font=("Microsoft YaHei UI", 8, "bold"), anchor="w").pack(fill="x", pady=(2, 4))
        for step in [
            "1  设备管理器 → 显示适配器，确认虚拟显示器已启用；",
            "2  保持物理显示器关闭，发起一次串流；",
            "3  串流结束后确认虚拟显示器被自动移除。",
        ]:
            tk.Label(vdd.body, text=step, bg=theme.CARD, fg=theme.FAINT,
                     font=("Microsoft YaHei UI", 8), anchor="w", justify="left",
                     wraplength=330).pack(fill="x", pady=1)

        tail = widgets.Card(top, title="Tailscale 叠加", accent=theme.ACCENT)
        tail.grid(row=1, column=0, sticky="nsew", padx=(0, 7), pady=(12, 0))
        head = tk.Frame(tail.body, bg=theme.CARD)
        head.pack(fill="x")
        self.ts_chip = widgets.Chip(head, "检测中", theme.FAINT)
        self.ts_chip.pack(side="left")
        self.ts_version = tk.Label(head, text="", bg=theme.CARD, fg=theme.FAINT,
                                   font=("Microsoft YaHei UI", 8))
        self.ts_version.pack(side="left", padx=(8, 0))
        widgets.button(head, "刷新状态", self._refresh_tailscale, kind="ghost").pack(side="right")

        self.ts_rows = tk.Frame(tail.body, bg=theme.CARD)
        self.ts_rows.pack(fill="x", pady=(8, 0))
        self.ts_hint = tk.Label(
            tail.body, text="", bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
            justify="left", anchor="w", wraplength=560,
        )
        self.ts_hint.pack(fill="x", pady=(8, 0))

        diag = widgets.Card(top, title="链路诊断", accent=theme.BLUE)
        diag.grid(row=1, column=1, sticky="nsew", padx=(7, 0), pady=(12, 0))
        self.gw_label = widgets.kv_row(diag.body, "默认网关", "检测中")
        self.lan_label = widgets.kv_row(diag.body, "本机地址", "—")
        self.ts_ping_label = widgets.kv_row(diag.body, "Tailscale", "—")
        buttons = tk.Frame(diag.body, bg=theme.CARD)
        buttons.pack(fill="x", pady=(10, 0))
        self.ping_btn = widgets.button(buttons, "测试网关延迟", self._test_gateway, kind="primary")
        self.ping_btn.pack(side="left")
        self.ping_result = tk.Label(
            diag.body, text="点按钮测一次网关延迟，作为局域网底噪参考。", bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 8),
            justify="left", anchor="w", wraplength=330,
        )
        self.ping_result.pack(fill="x", pady=(8, 0))

    # ---- 动作 -----------------------------------------------------------
    def _open_devmgmt(self) -> None:
        try:
            subprocess.Popen(["devmgmt.msc"], shell=True)
        except OSError:
            self.app.log("无法打开设备管理器", "warn")

    def _open_display_settings(self) -> None:
        try:
            os.startfile("ms-settings:display")  # type: ignore[attr-defined]
        except OSError:
            self.app.log("无法打开系统显示设置", "warn")

    def _refresh_tailscale(self) -> None:
        self.app.refresh_all()

    def _test_gateway(self) -> None:
        gateway = self._gateway or win.default_gateway()
        if not gateway:
            self.ping_result.configure(text="没有找到默认网关，请检查是否已连上 Wi-Fi。", fg=theme.AMBER)
            return
        self.ping_result.configure(text=f"正在 ping {gateway}…", fg=theme.MUTED)
        self.ping_btn.configure(state="disabled")

        def work():
            return win.ping_ms(gateway, count=4)

        def done(result):
            self.ping_btn.configure(state="normal")
            if result.get("ok"):
                self.ping_result.configure(
                    text=f"网关平均延迟 {result['avg']} ms，丢包 {result['loss']}%。"
                         "局域网内 Moonlight 端到端通常在 10 ms 上下；Wi-Fi 6 下超过 30 ms 需要检查信道。",
                    fg=theme.ACCENT if result["avg"] < 20 else theme.AMBER,
                )
            else:
                self.ping_result.configure(
                    text="系统 ping 不可用或网关无响应。可直接在 PadLink Pad 上用 TCP 体检替代。",
                    fg=theme.AMBER,
                )

        self.app.run_async(work, done, lambda exc: self.ping_result.configure(text=f"测试失败：{exc}", fg=theme.RED))

    # ---- 刷新 -----------------------------------------------------------
    def update_data(self, snapshot, checks, score) -> None:
        rows = []
        for display in snapshot.displays:
            if not display.width and not display.primary:
                continue
            rows.append((
                display.device.rsplit("\\", 1)[-1],
                display.adapter,
                f"{display.width}×{display.height}" if display.width else "—",
                f"{display.refresh} Hz" if display.refresh else "—",
                "虚拟" if display.virtual else "物理",
            ))
        if not rows:
            rows = [("—", "未检测到活动显示器", "—", "—", "—")]
        self.display_table.set_rows(rows)

        kind = snapshot.vdd_kind
        if kind:
            self.vdd_chip.configure(text=kind, bg=widgets._tint(theme.PURPLE, 0.2), fg=theme.PURPLE)
            self.vdd_text.configure(
                text=f"已检测到虚拟显示器驱动（{kind}）。串流开始时创建、结束时销毁，"
                     "无需保持物理显示器开启。若切换设备后黑屏，先在设备管理器禁用再启用一次。"
            )
        else:
            self.vdd_chip.configure(text="未检测到", bg=widgets._tint(theme.AMBER, 0.16), fg=theme.AMBER)
            self.vdd_text.configure(
                text="没有虚拟显示器驱动。Foundation Sunshine 自带 ZakoVDD，安装后在设备管理器"
                     "「显示适配器」中启用；也可以先用 spacedesk 等现有方案。"
            )

        ts = snapshot.tailscale
        color = theme.ACCENT if ts.running else theme.FAINT
        if ts.peers_relay and not ts.peers_direct:
            color = theme.AMBER
        self.ts_chip.configure(text=ts.link, bg=widgets._tint(color, 0.16), fg=color)
        self.ts_version.configure(text=f"v{ts.version}" if ts.version else ("" if not ts.installed else "已安装"))

        for child in self.ts_rows.winfo_children():
            child.destroy()
        if ts.installed:
            values = [
                ("虚拟 IP", ", ".join(ts.ips) or "未分配"),
                ("在线节点", f"{ts.peers_online} 个（直连 {ts.peers_direct} / 中继 {ts.peers_relay}）"),
                ("后端状态", ts.backend or "未知"),
            ]
        else:
            values = [
                ("安装", "未检测到 Tailscale"),
                ("用途", "异地串流：把虚拟 IP 当作局域网地址"),
            ]
        for label, value in values:
            widgets.kv_row(self.ts_rows, label, value)
        if not ts.installed:
            tk.Label(
                self.ts_rows, text="安装步骤", bg=theme.CARD, fg=theme.MUTED,
                font=("Microsoft YaHei UI", 8, "bold"), anchor="w",
            ).pack(fill="x", pady=(8, 2))
            for step in [
                "1  电脑与平板各自安装 Tailscale 并登录同一账号；",
                "2  在管理后台确认两台设备都在线；",
                "3  平板连接时直接填电脑的 100.x 虚拟 IP。",
            ]:
                tk.Label(
                    self.ts_rows, text=step, bg=theme.CARD, fg=theme.FAINT,
                    font=("Microsoft YaHei UI", 8), anchor="w", justify="left", wraplength=560,
                ).pack(fill="x", pady=1)
        self.ts_ping_label.configure(text=ts.link if ts.running else "—")
        if not ts.installed:
            self.ts_hint.configure(
                text="安装并登录 Tailscale 后，Pad 与电脑会自动组网；PadLink 只读取状态，不修改任何 NAT 规则。"
            )
        elif ts.peers_relay and not ts.peers_direct:
            self.ts_hint.configure(text="当前走 DERP 中继，延迟会明显升高。优先检查两端 NAT 类型，直连后体验才接近局域网。")
        else:
            self.ts_hint.configure(text="Tailscale 直连可用；异地时 Pad 可直接填写虚拟 IP 连接。")

        gateway = win.default_gateway()
        self._gateway = gateway
        self.gw_label.configure(text=gateway or "未找到")
        lan = snapshot.lan_ips()
        self.lan_label.configure(text=", ".join(lan) or "—")
