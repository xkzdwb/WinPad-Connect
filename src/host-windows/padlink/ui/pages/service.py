"""接入服务页：启动/停止、配对码、地址与平板连接步骤。"""

from __future__ import annotations

import json
import time
import tkinter as tk
import urllib.request

from ... import theme
from ...settings import new_pairing_code
from .. import widgets


class ServicePage(tk.Frame):
    title = "接入服务"
    subtitle = "把本机接入参数交给平板；只读、局域网内、带可选配对码"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._build()
        self.refresh_service()

    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill="both", expand=True)
        top.grid_columnconfigure(0, weight=3, uniform="col")
        top.grid_columnconfigure(1, weight=2, uniform="col")
        top.grid_rowconfigure(0, weight=1)

        left = tk.Frame(top, bg=theme.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

        status_card = widgets.Card(left, title="服务状态", accent=theme.ACCENT)
        status_card.pack(fill="x")
        row = tk.Frame(status_card.body, bg=theme.CARD)
        row.pack(fill="x")
        self.dot = widgets.StatusDot(row, theme.FAINT, 10)
        self.dot.pack(side="left", padx=(0, 8))
        self.state_label = tk.Label(
            row, text="未启动", bg=theme.CARD, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 13, "bold"), anchor="w",
        )
        self.state_label.pack(side="left")
        self.uptime = tk.Label(row, text="", bg=theme.CARD, fg=theme.FAINT,
                               font=("Microsoft YaHei UI", 8))
        self.uptime.pack(side="right")

        self.endpoint = tk.Label(
            status_card.body, text="", bg=theme.CARD, fg=theme.BLUE,
            font=("Consolas", 10), anchor="w",
        )
        self.endpoint.pack(fill="x", pady=(10, 2))
        self.counters = tk.Label(
            status_card.body, text="请求 0 · 平板发现 0 · 最近客户端 —", bg=theme.CARD,
            fg=theme.MUTED, font=("Microsoft YaHei UI", 8), anchor="w",
        )
        self.counters.pack(fill="x")

        buttons = tk.Frame(status_card.body, bg=theme.CARD)
        buttons.pack(fill="x", pady=(14, 0))
        self.toggle_btn = widgets.button(buttons, "启动接入服务", self.app.toggle_service, kind="primary")
        self.toggle_btn.pack(side="left")
        widgets.button(buttons, "打开说明页", self._open_browser, kind="ghost").pack(side="left", padx=(6, 0))
        widgets.button(buttons, "自测 HTTP", self._self_test, kind="ghost").pack(side="left", padx=(6, 0))
        self.self_test_label = tk.Label(
            buttons, text="", bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 8),
        )
        self.self_test_label.pack(side="left", padx=(10, 0))

        config_card = widgets.Card(left, title="监听与配对", accent=theme.BLUE)
        config_card.pack(fill="x", pady=(12, 0))
        port_row = tk.Frame(config_card.body, bg=theme.CARD)
        port_row.pack(fill="x")
        tk.Label(port_row, text="监听端口", bg=theme.CARD, fg=theme.MUTED,
                 font=("Microsoft YaHei UI", 9), width=10, anchor="w").pack(side="left")
        self.port_var = tk.StringVar(value=str(self.app.settings.port))
        port_entry = tk.Entry(
            port_row, textvariable=self.port_var, width=10, bg=theme.CARD_ALT, fg=theme.TEXT,
            insertbackground=theme.TEXT, relief="flat", font=("Consolas", 10),
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.BLUE,
        )
        port_entry.pack(side="left", ipady=4)
        widgets.button(port_row, "应用", self._apply_port, kind="ghost").pack(side="left", padx=(8, 0))
        self.port_hint = tk.Label(
            port_row, text="修改后需重启服务", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8),
        )
        self.port_hint.pack(side="left", padx=(10, 0))

        pair_row = tk.Frame(config_card.body, bg=theme.CARD)
        pair_row.pack(fill="x", pady=(12, 0))
        tk.Label(pair_row, text="配对码", bg=theme.CARD, fg=theme.MUTED,
                 font=("Microsoft YaHei UI", 9), width=10, anchor="w").pack(side="left")
        self.code_var = tk.BooleanVar(value=self.app.settings.pairing_enabled)
        check = tk.Checkbutton(
            pair_row, text="平板连接时需要 6 位配对码", variable=self.code_var,
            command=self._toggle_pairing, bg=theme.CARD, fg=theme.TEXT,
            activebackground=theme.CARD, activeforeground=theme.TEXT,
            selectcolor=theme.CARD_ALT, font=("Microsoft YaHei UI", 9),
            highlightthickness=0, bd=0, cursor="hand2",
        )
        check.pack(side="left")

        code_row = tk.Frame(config_card.body, bg=theme.CARD)
        code_row.pack(fill="x", pady=(10, 0))
        self.code_label = tk.Label(
            code_row, text="------", bg=theme.CARD, fg=theme.ACCENT,
            font=("Consolas", 26, "bold"), anchor="w",
        )
        self.code_label.pack(side="left")
        widgets.button(code_row, "换一个", self._regenerate, kind="ghost").pack(side="left", padx=(14, 0))
        widgets.button(code_row, "复制", lambda: self.app.copy(self.app.settings.pairing_code, "配对码"),
                       kind="ghost").pack(side="left", padx=(6, 0))
        tk.Label(
            config_card.body, text="配对码只用于同一局域网内的一次性连接，不参与视频链路加密。",
            bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8), anchor="w",
        ).pack(fill="x", pady=(8, 0))

        trouble = widgets.Card(left, title="连不上时先看这里", accent=theme.AMBER)
        trouble.pack(fill="both", expand=True, pady=(12, 0))
        for head, body in [
            ("同一网段？", "平板与电脑的 IP 前三段应一致；不同网段需先接 Tailscale。"),
            ("服务开着？", "上方状态必须是「运行中」；防火墙首次会弹窗，需允许专用网络。"),
            ("发现被禁？", "部分系统会屏蔽 UDP 广播；此时在 Pad 上手动填上方地址与配对码。"),
        ]:
            block = tk.Frame(trouble.body, bg=theme.CARD)
            block.pack(fill="x", pady=(0, 8))
            tk.Label(block, text=head, bg=theme.CARD, fg=theme.TEXT,
                     font=("Microsoft YaHei UI", 9, "bold"), anchor="w").pack(fill="x")
            tk.Label(block, text=body, bg=theme.CARD, fg=theme.MUTED,
                     font=("Microsoft YaHei UI", 8), anchor="w", justify="left",
                     wraplength=560).pack(fill="x")

        right = tk.Frame(top, bg=theme.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        steps = widgets.Card(right, title="平板连接步骤", accent=theme.PURPLE)
        steps.pack(fill="x")
        for index, (head, body) in enumerate([
            ("1  连同一网络", "把 Pad 和这台电脑接到同一个 Wi-Fi；异地场景先开启 Tailscale。"),
            ("2  打开 PadLink Pad", "应用会自动广播发现本机，点选主机即可。"),
            ("3  输入配对码", "六位数字，在 Pad 上输入一次即可保存。"),
            ("4  读取体检结果", "Pad 会显示主机编码器、分辨率档位与待处理项。"),
        ]):
            block = tk.Frame(steps.body, bg=theme.CARD)
            block.pack(fill="x", pady=(0, 10))
            tk.Label(block, text=head, bg=theme.CARD, fg=theme.TEXT,
                     font=("Microsoft YaHei UI", 9, "bold"), anchor="w").pack(fill="x")
            tk.Label(block, text=body, bg=theme.CARD, fg=theme.MUTED,
                     font=("Microsoft YaHei UI", 8), anchor="w", justify="left",
                     wraplength=330).pack(fill="x")

        addr_card = widgets.Card(right, title="本机可用地址", accent=theme.BLUE)
        addr_card.pack(fill="x", pady=(12, 0))
        self.addr_box = tk.Frame(addr_card.body, bg=theme.CARD)
        self.addr_box.pack(fill="x")
        self.addr_hint = tk.Label(
            addr_card.body, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8), anchor="w", wraplength=330, justify="left",
        )
        self.addr_hint.pack(fill="x", pady=(8, 0))

        log_card = widgets.Card(right, title="接入日志", accent=theme.ACCENT)
        log_card.pack(fill="both", expand=True, pady=(12, 0))
        self.log = widgets.LogView(log_card.body, height=6)
        self.log.pack(fill="both", expand=True)
        self.log.set_placeholder("等待平板请求。启动服务后，这里会记录发现、配对与下载活动。")

    # ---- 动作 -----------------------------------------------------------
    def _apply_port(self) -> None:
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.port_hint.configure(text="端口必须是数字", fg=theme.RED)
            return
        if not 1024 <= port <= 65535:
            self.port_hint.configure(text="端口范围 1024–65535", fg=theme.RED)
            return
        self.app.settings.port = port
        self.app.settings.save()
        self.port_hint.configure(text="已保存，重启服务后生效", fg=theme.ACCENT)
        self.log.append(f"监听端口改为 {port}", "ok")
        self.refresh_service()

    def _toggle_pairing(self) -> None:
        self.app.settings.pairing_enabled = bool(self.code_var.get())
        self.app.settings.save()
        self.refresh_service()
        self.log.append("配对码校验已" + ("开启" if self.code_var.get() else "关闭"), "warn")

    def _regenerate(self) -> None:
        self.app.settings.pairing_code = new_pairing_code()
        self.app.settings.save()
        self.refresh_service()
        self.log.append("已生成新的配对码", "ok")

    def _open_browser(self) -> None:
        import webbrowser

        if not self.app.service.running:
            self.self_test_label.configure(text="先启动服务", fg=theme.AMBER)
            return
        webbrowser.open(f"http://127.0.0.1:{self.app.settings.port}/")

    def _self_test(self) -> None:
        if not self.app.service.running:
            self.self_test_label.configure(text="先启动服务", fg=theme.AMBER)
            return
        url = f"http://127.0.0.1:{self.app.settings.port}/padlink/ping"
        self.self_test_label.configure(text="测试中…", fg=theme.MUTED)

        def work():
            started = time.perf_counter()
            with urllib.request.urlopen(url, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return (time.perf_counter() - started) * 1000, payload

        def done(result):
            elapsed, payload = result
            self.self_test_label.configure(
                text=f"HTTP 正常 · {elapsed:.1f} ms · 协议 v{payload.get('protocol')}", fg=theme.ACCENT,
            )
            self.log.append(f"自测成功：{elapsed:.1f} ms，协议 v{payload.get('protocol')}", "ok")

        def failed(exc):
            self.self_test_label.configure(text="自测失败", fg=theme.RED)
            self.log.append(f"自测失败：{exc}", "error")

        self.app.run_async(work, done, failed)

    # ---- 刷新 -----------------------------------------------------------
    def update_data(self, snapshot, checks, score) -> None:
        self.refresh_addresses()
        self.refresh_service()

    def refresh_addresses(self) -> None:
        for child in self.addr_box.winfo_children():
            child.destroy()
        snapshot = self.app.snapshot
        port = self.app.settings.port
        ips = snapshot.lan_ips() if snapshot else []
        if not ips:
            tk.Label(self.addr_box, text="还没有可用的局域网地址", bg=theme.CARD,
                     fg=theme.AMBER, font=("Microsoft YaHei UI", 9), anchor="w").pack(fill="x")
        for ip in ips:
            self._address_row(f"http://{ip}:{port}", "局域网")
        if snapshot and snapshot.tailscale.ipv4:
            self._address_row(f"http://{snapshot.tailscale.ipv4}:{port}", "Tailscale")
        elif snapshot:
            self.addr_hint.configure(
                text="异地使用需要安装 Tailscale 并登录；PadLink 不修改 Sunshine 的 NAT 穿透逻辑。"
            )
        if snapshot and snapshot.tailscale.running:
            self.addr_hint.configure(text=f"Tailscale 链路：{snapshot.tailscale.link}")

    def _address_row(self, address: str, tag: str) -> None:
        row = tk.Frame(self.addr_box, bg=theme.CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=address, bg=theme.CARD, fg=theme.TEXT,
                 font=("Consolas", 9), anchor="w").pack(side="left")
        tk.Label(row, text=tag, bg=theme.CARD, fg=theme.FAINT,
                 font=("Microsoft YaHei UI", 7), padx=6).pack(side="left")
        btn = tk.Label(row, text="复制", bg=theme.CARD, fg=theme.BLUE,
                       font=("Microsoft YaHei UI", 8), cursor="hand2")
        btn.pack(side="right")
        btn.bind("<Button-1>", lambda _e: self.app.copy(address, "地址"))

    def refresh_service(self) -> None:
        service = self.app.service
        running = service.running
        self.state_label.configure(
            text="运行中" if running else "未启动",
            fg=theme.TEXT if running else theme.MUTED,
        )
        self.dot.set_color(theme.ACCENT if running else theme.FAINT)
        self.toggle_btn.configure(text="停止接入服务" if running else "启动接入服务")
        self.endpoint.configure(
            text=f"http://0.0.0.0:{self.app.settings.port}/padlink/ping" if running else "服务未监听任何端口"
        )
        if running:
            self.uptime.configure(text=f"已运行 {int(time.time() - service.started_at)} 秒" if service.started_at else "")
            last = service.last_client
            last_text = f"{last['ip']} {last['path']}" if last else "—"
            self.counters.configure(
                text=f"请求 {service.request_count} · 平板发现 {service.discovery_count} · 最近客户端 {last_text}"
            )
        else:
            self.uptime.configure(text="")
            self.counters.configure(text="启动后平板才能发现本机")

        settings = self.app.settings
        self.port_var.set(str(settings.port))
        self.code_var.set(settings.pairing_enabled)
        if settings.pairing_enabled:
            self.code_label.configure(text=settings.pairing_code, fg=theme.ACCENT)
        else:
            self.code_label.configure(text="— — —", fg=theme.FAINT)
        self.refresh_addresses()

    def append_log(self, message: str, tag: str = "info") -> None:
        self.log.append(message, tag)
