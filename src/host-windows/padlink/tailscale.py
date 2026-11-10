"""Tailscale 状态读取（只读，不修改任何 Tailscale 配置）。

PadLink 的网络策略是「叠加」：不改 Moonlight/Sunshine 的 NAT 穿透逻辑，
只把 Tailscale 的虚拟地址当成局域网地址使用。因此这里只需要回答三个问题：
装了吗、直连还是中继、虚拟 IP 是多少。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import platform_windows as win


@dataclass
class TailscaleState:
    installed: bool = False
    exe: str = ""
    backend: str = ""
    ips: list[str] = field(default_factory=list)
    peers_online: int = 0
    peers_direct: int = 0
    peers_relay: int = 0
    version: str = ""
    health: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ipv4(self) -> str:
        for ip in self.ips:
            if win.is_tailscale_ip(ip):
                return ip
        return ""

    @property
    def running(self) -> bool:
        return self.backend == "Running"

    @property
    def link(self) -> str:
        if not self.installed:
            return "未安装"
        if not self.running:
            return self.backend or "未运行"
        if self.peers_direct and not self.peers_relay:
            return "直连"
        if self.peers_relay and not self.peers_direct:
            return "中继"
        if self.peers_direct and self.peers_relay:
            return "部分中继"
        return "已登录"

    @property
    def link_ok(self) -> bool:
        return self.running and self.peers_relay == 0


def find_exe() -> str:
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if not base:
            continue
        candidate = Path(base) / "Tailscale" / "tailscale.exe"
        if candidate.exists():
            return str(candidate)
    code, out = win.run(["where", "tailscale"], timeout=4)
    if code == 0 and out:
        first = out.splitlines()[0].strip()
        if first:
            return first
    return ""


def status() -> TailscaleState:
    state = TailscaleState()
    exe = find_exe()
    if not exe:
        return state
    state.installed = True
    state.exe = exe
    code, out = win.run([exe, "status", "--json"], timeout=8)
    if code != 0 or not out.strip().startswith("{"):
        state.error = out.strip() or "tailscale status 失败（服务可能未启动）"
        # 服务未启动时仍可确认「已安装」
        if win.process_running("tailscaled.exe"):
            state.backend = "服务已启动，但未登录"
        return state
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        state.error = f"无法解析 status JSON：{exc}"
        return state

    state.backend = str(data.get("BackendState") or "")
    state.version = str(data.get("Version") or "")
    self_info = data.get("Self") or {}
    for ip in self_info.get("TailscaleIPs") or []:
        if isinstance(ip, str):
            state.ips.append(ip)
    for item in data.get("Health") or []:
        if isinstance(item, str):
            state.health.append(item)

    peers = data.get("Peer") or {}
    if isinstance(peers, dict):
        for peer in peers.values():
            if not isinstance(peer, dict):
                continue
            online = bool(peer.get("Online"))
            if not online:
                continue
            state.peers_online += 1
            if peer.get("CurAddr"):
                state.peers_direct += 1
            else:
                state.peers_relay += 1
    return state
