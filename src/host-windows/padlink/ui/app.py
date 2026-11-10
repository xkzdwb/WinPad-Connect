"""PadLink Host — Windows 主机端桌面程序。

职责：
1. 探测并说明 Sunshine 基线是否就绪；
2. 把低延迟编码参数安全地写入 Sunshine 配置（带备份/还原）；
3. 通过 HTTP+UDP 把本机接入参数与体检结果交给 PadLink Pad（安卓端）；
4. 展示虚拟显示器、Tailscale、防火墙等前置条件。
"""

from __future__ import annotations

import datetime
import json
import queue
import sys
import threading
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from .. import checks as checks_mod
from .. import handoff, paths, platform_windows as win, profile, sunshine, theme
from ..settings import Settings
from ..snapshot import collect
from ..version import APP_NAME, APP_VERSION, PROTOCOL_VERSION
from . import widgets
from .pages import about, display_network, overview, report, service, sunshine_page

NAV_ITEMS = [
    ("overview", "总览", "◈"),
    ("service", "接入服务", "⇄"),
    ("sunshine", "Sunshine 配置", "▣"),
    ("network", "显示与网络", "◎"),
    ("report", "体检报告", "✓"),
    ("about", "关于", "i"),
]

PAGE_CLASSES = {
    "overview": overview.OverviewPage,
    "service": service.ServicePage,
    "sunshine": sunshine_page.SunshinePage,
    "network": display_network.DisplayNetworkPage,
    "report": report.ReportPage,
    "about": about.AboutPage,
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        self.settings.save()  # 首次启动即落盘，保证配对码等信息可复用
        self.fonts = theme.apply(self)
        self.title(f"{APP_NAME} · Windows 主机端  v{APP_VERSION}")
        self.configure(bg=theme.BG)
        self.minsize(1060, 700)

        width, height = self._initial_geometry()
        self.geometry(f"{width}x{height}")
        self._center(width, height)

        win.enable_dpi_awareness()

        self.snapshot = None
        self.checks = []
        self.score = 0
        self.profile_payload: dict | None = None
        self.service = handoff.HandoffService(
            profile_provider=self.build_profile,
            code_provider=lambda: self.settings.pairing_code,
            code_required_provider=lambda: self.settings.pairing_enabled,
        )
        self._queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._activity: deque[tuple[str, str]] = deque(maxlen=200)
        self._busy = False
        self.pages: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Frame] = {}
        self.current_page = "overview"

        self._build_shell()
        self._build_pages()
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self.refresh_all)
        self.after(200, self._bind_service_events)

    # ---- 生命周期 --------------------------------------------------------
    def _initial_geometry(self) -> tuple[int, int]:
        try:
            if self.settings.geometry:
                parts = self.settings.geometry.lower().split("x")
                return max(1060, int(parts[0])), max(700, int(parts[1]))
        except (ValueError, IndexError):
            pass
        return 1340, 900

    def _center(self, width: int, height: int) -> None:
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _on_close(self) -> None:
        try:
            self.settings.geometry = f"{self.winfo_width()}x{self.winfo_height()}"
            self.settings.save()
        except Exception:
            pass
        try:
            self.service.stop()
        except Exception:
            pass
        self.destroy()

    # ---- 界面骨架 --------------------------------------------------------
    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg=theme.SIDEBAR, width=244)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=theme.SIDEBAR, padx=22, pady=24)
        brand.pack(fill="x")
        logo = tk.Canvas(brand, width=40, height=40, bg=theme.SIDEBAR, highlightthickness=0)
        logo.pack(side="left")
        logo.create_rectangle(2, 2, 38, 38, fill=theme.ACCENT, outline="")
        logo.create_text(20, 21, text="P", fill="#062018", font=("Segoe UI", 18, "bold"))
        text = tk.Frame(brand, bg=theme.SIDEBAR)
        text.pack(side="left", padx=(11, 0))
        brand_size = 15 if len(APP_NAME) <= 9 else 13
        tk.Label(text, text=APP_NAME, bg=theme.SIDEBAR, fg=theme.TEXT,
                 font=("Microsoft YaHei UI", brand_size, "bold"), anchor="w").pack(fill="x")
        tk.Label(text, text="HOST · WINDOWS", bg=theme.SIDEBAR, fg=theme.FAINT,
                 font=("Segoe UI", 7, "bold"), anchor="w").pack(fill="x")

        tk.Frame(self.sidebar, bg=theme.BORDER, height=1).pack(fill="x", padx=20, pady=(4, 14))

        self.nav_host = tk.Frame(self.sidebar, bg=theme.SIDEBAR)
        self.nav_host.pack(fill="x", padx=10)
        for key, label, glyph in NAV_ITEMS:
            self._make_nav_button(key, glyph, label)

        tk.Frame(self.sidebar, bg=theme.SIDEBAR).pack(fill="both", expand=True)

        tip = tk.Frame(self.sidebar, bg=theme.SIDEBAR, padx=18, pady=16)
        tip.pack(fill="x")
        card = tk.Frame(tip, bg=theme.CARD, highlightbackground=theme.BORDER, highlightthickness=1)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=theme.CARD, padx=12, pady=11)
        inner.pack(fill="x")
        tk.Label(inner, text="给平板安装", bg=theme.CARD, fg=theme.ACCENT,
                 font=("Microsoft YaHei UI", 9, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            inner, text="Pad 与电脑连同一 Wi-Fi，打开 PadLink 即可自动发现。",
            bg=theme.CARD, fg=theme.MUTED, font=("Microsoft YaHei UI", 8),
            justify="left", wraplength=168, anchor="w",
        ).pack(fill="x", pady=(4, 0))
        tk.Label(
            self.sidebar, text=f"协议 v{PROTOCOL_VERSION} · 本地直连",
            bg=theme.SIDEBAR, fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
        ).pack(side="bottom", pady=14)

        # 主区域
        self.main = tk.Frame(self, bg=theme.BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.topbar = tk.Frame(self.main, bg=theme.BG, padx=28)
        self.topbar.pack(fill="x", pady=(18, 10))
        title_wrap = tk.Frame(self.topbar, bg=theme.BG)
        title_wrap.pack(side="left", fill="x", expand=True)
        self.page_title = tk.Label(
            title_wrap, text="总览", bg=theme.BG, fg=theme.TEXT,
            font=("Microsoft YaHei UI", 20, "bold"), anchor="w",
        )
        self.page_title.pack(fill="x")
        self.page_subtitle = tk.Label(
            title_wrap, text="", bg=theme.BG, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 9), anchor="w",
        )
        self.page_subtitle.pack(fill="x", pady=(2, 0))

        actions = tk.Frame(self.topbar, bg=theme.BG)
        actions.pack(side="right")
        self.busy_label = tk.Label(actions, text="", bg=theme.BG, fg=theme.AMBER,
                                   font=("Microsoft YaHei UI", 8))
        self.busy_label.pack(side="left", padx=(0, 10))
        self.refresh_btn = widgets.button(actions, "重新体检", self.refresh_all, kind="primary")
        self.refresh_btn.pack(side="left")

        self.container = tk.Frame(self.main, bg=theme.BG, padx=28)

        self.statusbar = tk.Frame(self.main, bg=theme.SIDEBAR, height=30)
        self.statusbar.pack(fill="x", side="bottom")
        self.status_dot = widgets.StatusDot(self.statusbar, theme.FAINT, 8)
        self.status_dot.pack(side="left", padx=(16, 6), pady=10)
        self.status_text = tk.Label(
            self.statusbar, text="正在初始化…", bg=theme.SIDEBAR, fg=theme.MUTED,
            font=("Microsoft YaHei UI", 8), anchor="w",
        )
        self.status_text.pack(side="left")
        tk.Label(
            self.statusbar, text=f"{APP_NAME} v{APP_VERSION}", bg=theme.SIDEBAR,
            fg=theme.FAINT, font=("Microsoft YaHei UI", 8),
        ).pack(side="right", padx=16)
        self.container.pack(fill="both", expand=True)

    def _make_nav_button(self, key: str, glyph: str, label: str) -> None:
        row = tk.Frame(self.nav_host, bg=theme.SIDEBAR, cursor="hand2")
        row.pack(fill="x", pady=1)
        bar = tk.Frame(row, bg=theme.SIDEBAR, width=3)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(row, bg=theme.SIDEBAR, padx=10, pady=9)
        inner.pack(side="left", fill="x", expand=True)
        icon = tk.Label(inner, text=glyph, bg=theme.SIDEBAR, fg=theme.FAINT,
                        font=("Segoe UI Symbol", 11), width=2, anchor="center")
        icon.pack(side="left")
        text = tk.Label(inner, text=label, bg=theme.SIDEBAR, fg=theme.MUTED,
                        font=("Microsoft YaHei UI", 10), anchor="w")
        text.pack(side="left", fill="x", expand=True)

        def select(_event=None, page=key):
            self.show_page(page)

        for widget in (row, inner, icon, text):
            widget.bind("<Button-1>", select)
            widget.bind("<Enter>", lambda _e, r=row: self._hover_nav(r, True))
            widget.bind("<Leave>", lambda _e, r=row: self._hover_nav(r, False))
        self.nav_buttons[key] = row
        row._parts = (bar, icon, text)  # type: ignore[attr-defined]

    def _hover_nav(self, row: tk.Frame, entering: bool) -> None:
        if getattr(row, "_active", False):
            return
        color = theme.CARD if entering else theme.SIDEBAR
        row.configure(bg=color)
        for child in row.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=color)
                for sub in child.winfo_children():
                    sub.configure(bg=color)

    def _build_pages(self) -> None:
        for key, cls in PAGE_CLASSES.items():
            page = cls(self.container, self)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[key] = page
        self.show_page(self.settings.last_page or "overview")

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            key = "overview"
        self.current_page = key
        page = self.pages[key]
        page.lift()
        self.page_title.configure(text=getattr(page, "title", key))
        self.page_subtitle.configure(text=getattr(page, "subtitle", ""))
        for other, row in self.nav_buttons.items():
            active = other == key
            row._active = active  # type: ignore[attr-defined]
            bar, icon, text = row._parts  # type: ignore[attr-defined]
            row.configure(bg=theme.CARD if active else theme.SIDEBAR)
            for child in row.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=theme.CARD if active else theme.SIDEBAR)
                    for sub in child.winfo_children():
                        sub.configure(bg=theme.CARD if active else theme.SIDEBAR)
            bar.configure(bg=theme.ACCENT if active else (theme.CARD if active else theme.SIDEBAR))
            icon.configure(fg=theme.ACCENT if active else theme.FAINT)
            text.configure(fg=theme.TEXT if active else theme.MUTED,
                           font=("Microsoft YaHei UI", 10, "bold" if active else "normal"))
        self.settings.last_page = key
        on_show = getattr(page, "on_show", None)
        if callable(on_show):
            on_show()

    # ---- 数据刷新 --------------------------------------------------------
    def refresh_all(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.refresh_btn.configure(state="disabled", text="检测中…")
        self.busy_label.configure(text="正在读取硬件/服务状态…")

        def work():
            snapshot = collect(self.settings.sunshine_path or None)
            result, score = checks_mod.evaluate(snapshot, self.service)
            return snapshot, result, score

        def done(payload):
            self.snapshot, self.checks, self.score = payload
            self.profile_payload = profile.build(
                self.snapshot, self.service, self.checks, self.score
            )
            self._busy = False
            self.refresh_btn.configure(state="normal", text="重新体检")
            self.busy_label.configure(text="")
            for page in self.pages.values():
                update = getattr(page, "update_data", None)
                if callable(update):
                    try:
                        update(self.snapshot, self.checks, self.score)
                    except Exception as exc:  # 单页失败不拖垮整个刷新
                        self.log(f"{type(page).__name__} 刷新失败：{exc}", "error")
            self.log(
                f"体检完成：{self.score}/100 · {checks_mod.headline(self.score, self.checks)}",
                "ok" if self.score >= 85 else "warn",
            )
            self.set_status(f"就绪 · 体检得分 {self.score}/100", theme.ACCENT if self.score >= 85 else theme.AMBER)

        def failed(exc: Exception):
            self._busy = False
            self.refresh_btn.configure(state="normal", text="重新体检")
            self.busy_label.configure(text="")
            self.log(f"检测失败：{exc}", "error")
            self.set_status("检测失败，请查看日志", theme.RED)

        self.run_async(work, done, failed)

    def run_async(
        self,
        work: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        def runner():
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - 交给 UI 展示
                captured = exc
                callback = on_error or (lambda e: self.log(f"后台任务失败：{e}", "error"))
                self._queue.put(lambda: callback(captured))
            else:
                self._queue.put(lambda: on_success(result))

        threading.Thread(target=runner, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                callback = self._queue.get_nowait()
                try:
                    callback()
                except Exception as exc:
                    self.log(f"界面回调异常：{exc}", "error")
        except queue.Empty:
            pass
        self.after(70, self._poll_queue)

    # ---- 业务动作 --------------------------------------------------------
    def build_profile(self) -> dict:
        if self.profile_payload is None:
            snapshot = collect(self.settings.sunshine_path or None)
            result, score = checks_mod.evaluate(snapshot, self.service)
            self.profile_payload = profile.build(snapshot, self.service, result, score)
        else:
            # 端口/配对码可能已经变化，下发前刷新这两个字段
            self.profile_payload = profile.build(
                self.snapshot, self.service, self.checks, self.score
            )
        return self.profile_payload

    def toggle_service(self) -> None:
        if self.service.running:
            self.service.stop()
            self.log("接入服务已停止", "warn")
            self.set_status("接入服务已停止", theme.FAINT)
            self._refresh_service_pages()
            return

        def work():
            return self.service.start(self.settings.port)

        def done(result):
            ok, message = result
            if ok:
                self.log(f"接入服务已启动：{message}", "ok")
                self.set_status(f"接入服务运行中 · 端口 {self.settings.port}", theme.ACCENT)
            else:
                self.log(f"接入服务启动失败：{message}", "error")
                self.set_status("接入服务启动失败", theme.RED)
                messagebox.showerror("无法启动接入服务", message)
            self._refresh_service_pages()

        self.run_async(work, done)

    def _refresh_service_pages(self) -> None:
        for key in ("service", "overview", "report"):
            page = self.pages.get(key)
            update = getattr(page, "refresh_service", None)
            if callable(update):
                update()
        if self.snapshot is not None:
            result, score = checks_mod.evaluate(self.snapshot, self.service)
            self.checks, self.score = result, score
            for page in self.pages.values():
                update = getattr(page, "update_data", None)
                if callable(update):
                    update(self.snapshot, self.checks, self.score)

    def _bind_service_events(self) -> None:
        def sink(event: str, message: str) -> None:
            tone = "ok" if event == "request" else "info"
            self.log(message, tone)
            for key in ("service", "overview"):
                page = self.pages.get(key)
                refresh = getattr(page, "refresh_service", None)
                if callable(refresh):
                    refresh()

        self.service.set_event_sink(sink)

    def copy(self, text: str, what: str = "内容") -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.set_status(f"已复制{what}到剪贴板", theme.ACCENT)
        self.log(f"已复制{what}", "info")

    def log(self, message: str, tag: str = "info") -> None:
        self._activity.append((tag, message))
        for key in ("overview",):
            page = self.pages.get(key)
            sink = getattr(page, "append_log", None)
            if callable(sink):
                sink(message, tag)

    def set_status(self, text: str, color: str = theme.MUTED) -> None:
        self.status_text.configure(text=text)
        self.status_dot.set_color(color)

    def save_report(self, fmt: str = "txt") -> Path:
        reports = paths.reports_dir()
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports / f"padlink-report-{stamp}.{fmt}"
        if fmt == "json":
            payload = profile.build(self.snapshot, self.service, self.checks, self.score)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            path.write_text(self.report_text(), encoding="utf-8")
        self.log(f"报告已保存：{path}", "ok")
        return path

    def report_text(self) -> str:
        if self.snapshot is None:
            return "尚未完成体检。"
        snapshot = self.snapshot
        lines = [
            f"{APP_NAME} 体检报告  v{APP_VERSION}",
            f"生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
            "=" * 56,
            f"主机：{snapshot.os.hostname}    {snapshot.os.name} {snapshot.os.version} (build {snapshot.os.build})",
            f"CPU：{snapshot.cpu}",
            f"内存：{snapshot.ram_gb:.1f} GB",
            f"显卡：{' / '.join(g['name'] for g in snapshot.gpus) or '未识别'}",
            f"推荐编码器：{snapshot.encoder_label}",
            f"局域网地址：{', '.join(snapshot.lan_ips()) or '未发现'}",
            f"Tailscale：{snapshot.tailscale.link} {', '.join(snapshot.tailscale.ips) or ''}",
            f"虚拟显示器：{snapshot.vdd_kind or '未检测到'}",
            f"管理员权限：{'是' if snapshot.admin else '否'}",
            "",
            f"体检得分：{self.score}/100",
            "-" * 56,
        ]
        for check in self.checks:
            lines.append(f"[{check.status.upper():7}] {check.title}：{check.detail}")
            if check.status != "ok" and check.hint:
                lines.append(f"          → {check.hint}")
        lines += [
            "",
            "接入方式：平板与电脑在同一局域网，打开 PadLink Pad 自动发现；",
            f"或手动填写 http://{snapshot.lan_ips()[0] if snapshot.lan_ips() else '<本机IP>'}:{self.settings.port}。",
            f"配对码：{self.settings.pairing_code if self.settings.pairing_enabled else '已关闭'}",
        ]
        return "\n".join(lines)


def main() -> int:
    if sys.platform != "win32":
        print("PadLink Host 仅支持 Windows。")
        return 1
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
