"""总览页：一眼看清基线状态、体检得分与平板接入方式。"""

from __future__ import annotations

import tkinter as tk

from ... import checks as checks_mod
from ... import theme
from .. import widgets


def shorten(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class CheckRow(tk.Frame):
    def __init__(self, parent: tk.Misc, check) -> None:
        super().__init__(parent, bg=theme.CARD)
        color = theme.STATUS_COLORS.get(check.status, theme.FAINT)
        widgets.StatusDot(self, color, 8).pack(side="left", padx=(0, 9), pady=11)
        label = tk.Label(
            self, text=check.title, bg=theme.CARD, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 9), anchor="w", width=12,
        )
        label.pack(side="left")
        detail = tk.Label(
            self, text=shorten(check.detail, 52), bg=theme.CARD, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 8), anchor="w",
        )
        detail.pack(side="left", fill="x", expand=True)
        chip = tk.Label(
            self, text={"ok": "通过", "warn": "提醒", "fail": "未完成", "unknown": "未知"}.get(check.status, check.status),
            bg=theme.CARD, fg=color, font=("Microsoft YaHei UI", 8, "bold"), width=5, anchor="e",
        )
        chip.pack(side="right")


class OverviewPage(tk.Frame):
    title = "总览"
    subtitle = "Windows 被控端基线状态与平板接入入口"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._hero_state = None
        self._build()

    # ---- 构建 -----------------------------------------------------------
    def _build(self) -> None:
        outer, self.body = widgets.scrollable(self)
        outer.pack(fill="both", expand=True)
        self.hero = widgets.Card(self.body, accent=theme.ACCENT, pad=0)
        self.hero.pack(fill="x", pady=(0, 14))
        hero_inner = tk.Frame(self.hero.body, bg=theme.CARD)
        hero_inner.pack(fill="both", expand=True)

        left = tk.Frame(hero_inner, bg=theme.CARD, padx=22, pady=16)
        left.pack(side="left", fill="both", expand=True)
        self.hero_chip_row = tk.Frame(left, bg=theme.CARD)
        self.hero_chip_row.pack(fill="x")
        self.state_chip = widgets.Chip(self.hero_chip_row, "正在检测", theme.AMBER)
        self.state_chip.pack(side="left")
        self.hero_title = tk.Label(
            left, text="正在读取主机状态…", bg=theme.CARD, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 20, "bold"), anchor="w",
        )
        self.hero_title.pack(fill="x", pady=(9, 2))
        self.hero_host = tk.Label(
            left, text="", bg=theme.CARD, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 9), anchor="w",
        )
        self.hero_host.pack(fill="x")
        self.hero_chips = tk.Frame(left, bg=theme.CARD)
        self.hero_chips.pack(fill="x", pady=(12, 0))
        self.hero_hint = tk.Label(
            left, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8), anchor="w", justify="left", wraplength=560,
        )
        self.hero_hint.pack(fill="x", pady=(9, 0))

        right = tk.Frame(hero_inner, bg=theme.CARD, padx=18, pady=16)
        right.pack(side="right")
        self.gauge = widgets.ScoreGauge(right, size=150)
        self.gauge.pack()

        # 关键指标
        self.stats = tk.Frame(self.body, bg=theme.BG)
        self.stats.pack(fill="x")
        for index in range(4):
            self.stats.grid_columnconfigure(index, weight=1, uniform="stat")
        self.tile_encoder = widgets.StatTile(self.stats, "推荐编码器", "--", "", theme.BLUE)
        self.tile_display = widgets.StatTile(self.stats, "虚拟显示器", "--", "", theme.PURPLE)
        self.tile_network = widgets.StatTile(self.stats, "网络路径", "--", "", theme.ACCENT)
        self.tile_service = widgets.StatTile(self.stats, "平板接入服务", "--", "", theme.AMBER)
        for index, tile in enumerate(
            (self.tile_encoder, self.tile_display, self.tile_network, self.tile_service)
        ):
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0))

        # 下半区
        bottom = tk.Frame(self.body, bg=theme.BG)
        bottom.pack(fill="both", expand=True, pady=(10, 0))
        bottom.grid_columnconfigure(0, weight=3, uniform="col")
        bottom.grid_columnconfigure(1, weight=2, uniform="col")
        bottom.grid_rowconfigure(0, weight=1)

        checks_card = widgets.Card(bottom, title="基线体检", subtitle="9 项前置条件，按对串流质量的影响排序")
        checks_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.check_rows = tk.Frame(checks_card.body, bg=theme.CARD)
        self.check_rows.pack(fill="both", expand=True)
        self.check_footer = tk.Label(
            checks_card.body, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8), anchor="w", justify="left", wraplength=560,
        )
        self.check_footer.pack(fill="x", pady=(8, 0))

        right_col = tk.Frame(bottom, bg=theme.BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        right_col.grid_rowconfigure(1, weight=1)

        access = widgets.Card(right_col, title="平板接入", accent=theme.BLUE)
        access.grid(row=0, column=0, sticky="ew")
        status_row = tk.Frame(access.body, bg=theme.CARD)
        status_row.pack(fill="x")
        self.service_dot = widgets.StatusDot(status_row, theme.FAINT, 9)
        self.service_dot.pack(side="left", padx=(0, 6))
        self.service_state = tk.Label(
            status_row, text="未启动", bg=theme.CARD, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 9, "bold"), anchor="w",
        )
        self.service_state.pack(side="left")
        self.service_addr = tk.Label(
            access.body, text="", bg=theme.CARD, fg=theme.TEXT,
            font=("Consolas", 9), anchor="w", justify="left",
        )
        self.service_addr.pack(fill="x", pady=(6, 0))
        code_row = tk.Frame(access.body, bg=theme.CARD)
        code_row.pack(fill="x", pady=(8, 0))
        tk.Label(code_row, text="配对码", bg=theme.CARD, fg=theme.MUTED,
                 font=("Microsoft YaHei UI", 8)).pack(side="left")
        self.code_label = tk.Label(
            code_row, text="------", bg=theme.CARD, fg=theme.ACCENT,
            font=("Consolas", 16, "bold"), anchor="w",
        )
        self.code_label.pack(side="left", padx=(10, 0))
        self.code_state = tk.Label(
            code_row, text="", bg=theme.CARD, fg=theme.FAINT,
            font=("Microsoft YaHei UI", 8),
        )
        self.code_state.pack(side="right")

        buttons = tk.Frame(access.body, bg=theme.CARD)
        buttons.pack(fill="x", pady=(12, 0))
        self.service_btn = widgets.button(buttons, "启动接入服务", self.app.toggle_service, kind="primary")
        self.service_btn.pack(side="left")
        widgets.button(buttons, "复制配对码", self._copy_code, kind="ghost").pack(side="left", padx=(6, 0))
        widgets.button(buttons, "查看报告", lambda: self.app.show_page("report"), kind="ghost").pack(
            side="left", padx=(6, 0)
        )

        log_card = widgets.Card(right_col, title="最近活动", accent=theme.BLUE)
        log_card.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.log = widgets.LogView(log_card.body, height=7)
        self.log.pack(fill="both", expand=True)
        self.append_log("Win-Pad Connect 已启动，等待首次体检", "info")

    # ---- 交互 -----------------------------------------------------------
    def _copy_code(self) -> None:
        code = self.app.settings.pairing_code if self.app.settings.pairing_enabled else "未启用"
        self.app.copy(code, "配对码")

    def append_log(self, message: str, tag: str = "info") -> None:
        self.log.append(message, tag)

    # ---- 数据 -----------------------------------------------------------
    def update_data(self, snapshot, checks, score) -> None:
        state = self._hero_state
        ready = score >= 85
        headline = checks_mod.headline(score, checks)
        if state != (ready, headline):
            self._hero_state = (ready, headline)
            color = theme.ACCENT if ready else theme.AMBER if score >= 60 else theme.RED
            self.state_chip.configure(
                text="基线就绪" if ready else "待完善",
                bg=widgets._tint(color, 0.16),
                fg=color,
            )
            self.hero_title.configure(text=headline)
            self.hero_hint.configure(
                text=(
                    "下一步：在平板上打开 Win-Pad Connect Pad，自动发现本机后按提示连接。"
                    if ready
                    else "按体检报告中的提醒逐项处理；Sunshine 未安装时，先按官方步骤完成基线安装。"
                )
            )
        self.hero_host.configure(
            text=f"{snapshot.os.hostname}　·　{snapshot.os.name} {snapshot.os.version}　·　"
                 f"{snapshot.cpu}"
        )
        self.gauge.set(score, "就绪度")

        for child in self.hero_chips.winfo_children():
            child.destroy()
        chips = [
            (snapshot.encoder_label, theme.BLUE),
            (snapshot.vdd_kind or "无虚拟显示器", theme.PURPLE if snapshot.vdd_kind else theme.FAINT),
            (snapshot.lan_ips()[0] if snapshot.lan_ips() else "无局域网 IP", theme.ACCENT),
            (snapshot.tailscale.link, theme.ACCENT if snapshot.tailscale.running else theme.FAINT),
            ("管理员" if snapshot.admin else "普通权限", theme.ACCENT if snapshot.admin else theme.AMBER),
        ]
        for text, color in chips:
            widgets.Chip(self.hero_chips, text, color).pack(side="left", padx=(0, 6))

        self.tile_encoder.set(snapshot.encoder_label, "按显卡自动选择低延迟预设")
        self.tile_display.set(
            snapshot.vdd_kind or "未检测到",
            "随串流创建/销毁" if snapshot.supports_pad_native else "建议启用 ZakoVDD",
        )
        if snapshot.tailscale.running:
            direct = snapshot.tailscale.peers_direct
            relay = snapshot.tailscale.peers_relay
            self.tile_network.set("Tailscale", f"直连 {direct} · 中继 {relay}")
        else:
            self.tile_network.set("仅局域网", "异地需叠加 Tailscale")
        self.tile_service.set(
            "运行中" if self.app.service.running else "未启动",
            f"端口 {self.app.settings.port} · 配对码{'开启' if self.app.settings.pairing_enabled else '关闭'}",
        )

        for child in self.check_rows.winfo_children():
            child.destroy()
        for check in checks:
            CheckRow(self.check_rows, check).pack(fill="x")
        issues = [c for c in checks if c.status in ("fail", "warn")]
        self.check_footer.configure(
            text=(
                f"共 {len(checks)} 项检查，{len(issues)} 项需要处理。"
                + (f" 最先处理：{issues[0].title}。" if issues else " 基线状态良好。")
            )
        )
        self.refresh_service()

    def refresh_service(self) -> None:
        service = self.app.service
        running = service.running
        self.service_state.configure(
            text="运行中 · 等待平板连接" if running else "未启动",
            fg=theme.ACCENT if running else theme.MUTED,
        )
        self.service_dot.set_color(theme.ACCENT if running else theme.FAINT)
        ips = self.app.snapshot.lan_ips() if self.app.snapshot else []
        if running:
            address = ips[0] if ips else "127.0.0.1"
            self.service_addr.configure(text=f"http://{address}:{self.app.settings.port}\n"
                                               f"请求 {service.request_count} · 发现 {service.discovery_count}")
        else:
            self.service_addr.configure(text="启动后平板可自动发现本机")
        self.service_btn.configure(text="停止接入服务" if running else "启动接入服务")
        settings = self.app.settings
        if settings.pairing_enabled:
            self.code_label.configure(text=settings.pairing_code, fg=theme.ACCENT)
            self.code_state.configure(text="已开启")
        else:
            self.code_label.configure(text="— — —", fg=theme.FAINT)
            self.code_state.configure(text="已关闭")
        self.tile_service.set(
            "运行中" if running else "未启动",
            f"端口 {self.app.settings.port} · 配对码{'开启' if settings.pairing_enabled else '关闭'}",
        )
