"""关于页：版本、数据位置、许可与致谢。"""

from __future__ import annotations

import os
import sys
import tkinter as tk
import webbrowser
from pathlib import Path

from ... import paths, theme
from ...version import APP_NAME, APP_VERSION, AUTHOR, GITHUB_URL, PROTOCOL_VERSION, REPO_URL
from .. import widgets

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class AboutPage(tk.Frame):
    title = "关于"
    subtitle = "作者 lzx_xkzdwb · 在 Moonlight / Sunshine 生态上做最小有效改进"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._build()

    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=1, uniform="ab")
        top.grid_columnconfigure(1, weight=1, uniform="ab")

        intro = widgets.Card(top, accent=theme.ACCENT)
        intro.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(
            intro.body, text=APP_NAME, bg=theme.CARD, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 18, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            intro.body,
            text=f"版本 {APP_VERSION} · 协议 v{PROTOCOL_VERSION} · Windows 主机端\n"
                 "配套应用：Win-Pad Connect Pad（OPPO Pad 4 Pro / Android 10+）",
            bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 9),
            anchor="w", justify="left",
        ).pack(fill="x", pady=(4, 12))
        widgets.Divider(intro.body)
        tk.Label(
            intro.body,
            text="Win-Pad Connect 不实现串流协议，也不修改 Moonlight 的传输层。\n"
                 "它负责三件事：把 Sunshine 基线的低延迟参数配置好、在平板连上来之前"
                 "把主机体检一遍、把接入参数交给平板。真正的画面与输入仍由 "
                 "Sunshine + Moonlight 客户端完成——这条链路的延迟优势是整条方案的根基。",
            bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 9),
            anchor="w", justify="left", wraplength=470,
        ).pack(fill="x", pady=(10, 0))

        author = tk.Frame(intro.body, bg=theme.CARD)
        author.pack(fill="x", pady=(12, 0))
        tk.Label(
            author, text=f"作者  {AUTHOR}", bg=theme.CARD, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 9), anchor="w",
        ).pack(side="left")
        link = tk.Label(
            author, text="主页 github.com/xkzdwb", bg=theme.CARD, fg=theme.BLUE,
            font=("Microsoft YaHei UI", 9, "underline"), cursor="hand2", anchor="w",
        )
        link.pack(side="left", padx=(12, 0))
        link.bind("<Button-1>", lambda _event: webbrowser.open(GITHUB_URL))

        repo = tk.Frame(intro.body, bg=theme.CARD)
        repo.pack(fill="x", pady=(4, 0))
        tk.Label(
            repo, text="项目仓库", bg=theme.CARD, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 9), anchor="w",
        ).pack(side="left")
        repo_link = tk.Label(
            repo, text="github.com/xkzdwb/WinPad-Connect", bg=theme.CARD, fg=theme.BLUE,
            font=("Microsoft YaHei UI", 9, "underline"), cursor="hand2", anchor="w",
        )
        repo_link.pack(side="left", padx=(12, 0))
        repo_link.bind("<Button-1>", lambda _event: webbrowser.open(REPO_URL))

        data = widgets.Card(top, title="数据与文件", accent=theme.BLUE)
        data.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        try:
            app_dir = str(paths.app_data_dir())
        except OSError as exc:
            app_dir = f"不可用（{exc}）"
        def pretty(text: str, limit: int = 64) -> str:
            if len(text) <= limit:
                return text
            head = (limit - 1) // 2
            tail = limit - 1 - head
            return text[:head] + "…" + text[-tail:]

        self._rows = []
        for label, value in [
            ("数据目录", app_dir),
            ("设置文件", str(paths.settings_file())),
            ("配置备份", str(paths.backups_dir())),
            ("体检报告", str(paths.reports_dir())),
        ]:
            self._rows.append(widgets.kv_row(data.body, label, pretty(value), value_font=("Consolas", 8), label_width=9))
        buttons = tk.Frame(data.body, bg=theme.CARD)
        buttons.pack(fill="x", pady=(12, 0))
        widgets.button(buttons, "打开数据目录", self._open_data, kind="ghost").pack(side="left")
        widgets.button(buttons, "打开项目目录", self._open_project, kind="ghost").pack(side="left", padx=(6, 0))
        widgets.button(buttons, "复制版本信息", self._copy_info, kind="ghost").pack(side="right")

        bottom = tk.Frame(self, bg=theme.BG)
        bottom.pack(fill="both", expand=True, pady=(12, 0))
        bottom.grid_columnconfigure(0, weight=1, uniform="ab2")
        bottom.grid_columnconfigure(1, weight=1, uniform="ab2")
        bottom.grid_rowconfigure(0, weight=1)

        lic = widgets.Card(bottom, title="许可与致谢", accent=theme.PURPLE)
        lic.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        credits = [
            ("Foundation Sunshine", "GPL-3.0 · ZakoVDD 虚拟显示器与自动生命周期"),
            ("moonlight-android 触控 fork", "GPL-3.0 · 触控板模式与手势基线"),
            ("Sunshine", "GPL-3.0 · 编码与串流服务端"),
            ("Tailscale", "BSD-3-Clause · 叠加式组网，不改 NAT 逻辑"),
        ]
        for name, note in credits:
            row = tk.Frame(lic.body, bg=theme.CARD)
            row.pack(fill="x", pady=(0, 6))
            tk.Label(row, text=name, bg=theme.CARD, fg=theme.TEXT,
                     font=("Microsoft YaHei UI", 9, "bold"), anchor="w", width=26).pack(side="left")
            tk.Label(row, text=note, bg=theme.CARD, fg=theme.MUTED,
                     font=("Microsoft YaHei UI", 8), anchor="w", justify="left").pack(side="left")
        tk.Label(
            lic.body,
            text="Win-Pad Connect 自身代码以 MIT 许可发布。若随包分发 Foundation Sunshine 或 "
                 "Moonlight fork 的修改版，需按 GPL-3.0 开源相应修改；仅内部使用不触发分发义务。",
            bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
            anchor="w", justify="left", wraplength=470,
        ).pack(fill="x", pady=(8, 0))
        tk.Label(
            lic.body,
            text="免责声明：Win-Pad Connect 只读写 Sunshine 的官方配置文件，不包含破解、绕过授权或修改串流协议的代码；"
                 "请确保你对被控电脑拥有合法操作权限。",
            bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
            anchor="w", justify="left", wraplength=470,
        ).pack(fill="x", pady=(10, 0))

        cli = widgets.Card(bottom, title="命令行与自检", accent=theme.AMBER)
        cli.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(
            cli.body,
            text="从源码运行时（需要 Python 3.10+，只依赖标准库）：",
            bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 9), anchor="w",
        ).pack(fill="x")
        code = tk.Label(
            cli.body,
            text="python -m padlink\npython -m padlink --smoke-test\npython -m unittest discover -s tests -v",
            bg=theme.CARD_ALT, fg=theme.ACCENT, font=("Consolas", 9),
            anchor="w", justify="left", padx=10, pady=8,
        )
        code.pack(fill="x", pady=(6, 10))
        tk.Label(
            cli.body,
            text="--smoke-test 会跑一遍探测、体检、报告生成与协议下发，不打开窗口，"
                 "适合在远程会话或 CI 里确认环境。",
            bg=theme.CARD, fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
            anchor="w", justify="left", wraplength=470,
        ).pack(fill="x")
        tk.Label(
            cli.body,
            text=f"Python {sys.version.split()[0]} · {sys.platform}",
            bg=theme.CARD, fg=theme.FAINT, font=("Consolas", 8), anchor="w",
        ).pack(fill="x", pady=(10, 0))

    # ---- 动作 -----------------------------------------------------------
    def _open(self, path: Path) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except OSError as exc:
            self.app.log(f"无法打开 {path}：{exc}", "warn")

    def _open_data(self) -> None:
        try:
            self._open(paths.app_data_dir())
        except OSError as exc:
            self.app.log(f"数据目录不可用：{exc}", "warn")

    def _open_project(self) -> None:
        self._open(PROJECT_ROOT)

    def _copy_info(self) -> None:
        snapshot = self.app.snapshot
        lines = [
            f"{APP_NAME} {APP_VERSION} (protocol v{PROTOCOL_VERSION})",
            f"作者: {AUTHOR}  {GITHUB_URL}",
            f"项目仓库: {REPO_URL}",
            f"Python {sys.version.split()[0]} on {sys.platform}",
        ]
        if snapshot is not None:
            lines += [
                f"OS: {snapshot.os.name} build {snapshot.os.build}",
                f"Encoder: {snapshot.encoder_label}",
                f"VDD: {snapshot.vdd_kind or 'none'}",
                f"Tailscale: {snapshot.tailscale.link}",
                f"Score: {self.app.score}",
            ]
        self.app.copy("\n".join(lines), "版本信息")
