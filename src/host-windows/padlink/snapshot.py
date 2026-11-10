"""把散落在各模块里的探测结果收成一份快照。

界面刷新、诊断报告、下发给平板端的 profile 都读同一份快照，
避免「页面显示 A、体检结论 B」这类不一致。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import platform_windows as win
from . import sunshine as sunshine_mod
from . import tailscale as tailscale_mod
from .sunshine import SunshineState
from .tailscale import TailscaleState


PAD_NATIVE = (3392, 2400)
PAD_TIERS = [
    {"label": "流畅 1080p", "width": 1920, "height": 1080, "fps": 60, "bitrate_kbps": 20000},
    {"label": "均衡 2.5K", "width": 2560, "height": 1600, "fps": 60, "bitrate_kbps": 40000},
    {"label": "原生 3.4K", "width": 3392, "height": 2400, "fps": 60, "bitrate_kbps": 70000},
]


@dataclass
class Snapshot:
    os: win.OsInfo
    cpu: str
    ram_gb: float
    gpus: list[dict]
    displays: list[win.DisplayInfo]
    ips: list[str]
    admin: bool
    sunshine: SunshineState
    tailscale: TailscaleState
    firewall_rule: bool | None = None
    recommended_encoder: str = "software"
    generated_at: float = 0.0
    error: str = ""

    # -- 派生信息 ---------------------------------------------------------

    @property
    def gpu_names(self) -> list[str]:
        return [gpu["name"] for gpu in self.gpus]

    @property
    def primary_gpu(self) -> str:
        for gpu in self.gpus:
            if not win.gpu_is_virtual(gpu["name"]):
                return gpu["name"]
        return self.gpus[0]["name"] if self.gpus else "未知"

    @property
    def encoder(self) -> str:
        configured = self.sunshine.encoder()
        if configured in sunshine_mod.LOW_LATENCY_PROFILES:
            return configured
        return self.recommended_encoder

    @property
    def encoder_gpu(self) -> str:
        tokens = {
            "nvenc": ("nvidia",),
            "qsv": ("intel", "arc"),
            "amdvce": ("amd", "radeon"),
        }.get(self.recommended_encoder, ())
        for gpu in self.gpus:
            name = gpu["name"].lower()
            if any(token in name for token in tokens):
                return gpu["name"]
        return self.primary_gpu

    @property
    def encoder_label(self) -> str:
        return sunshine_mod.LOW_LATENCY_PROFILES.get(self.encoder, {}).get("label", self.encoder)

    @property
    def virtual_display(self) -> win.DisplayInfo | None:
        for display in self.displays:
            if display.virtual and (display.width or display.modes):
                return display
        for display in self.displays:
            if display.virtual:
                return display
        return None

    @property
    def vdd_kind(self) -> str:
        display = self.virtual_display
        if display is None:
            return "未检测到"
        text = (display.adapter + " " + display.monitor).lower()
        if "zako" in text:
            return "ZakoVDD"
        if "spacedesk" in text:
            return "spacedesk"
        return display.adapter or "虚拟显示器"

    @property
    def supports_pad_native(self) -> bool:
        display = self.virtual_display
        if display is None:
            return False
        return display.supports(*PAD_NATIVE)

    def lan_ips(self) -> list[str]:
        return [ip for ip in self.ips if not win.is_tailscale_ip(ip)]

    def tailscale_ip(self) -> str:
        return self.tailscale.ipv4 or next((ip for ip in self.ips if win.is_tailscale_ip(ip)), "")

    def to_report(self) -> str:
        lines = [
            "PadLink Host 诊断报告",
            f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.generated_at or time.time()))}",
            "",
            f"主机名：{self.os.hostname}",
            f"系统：{self.os.display}（支持：{'是' if self.os.supported else '否'}）",
            f"CPU：{self.cpu or '未知'}",
            f"内存：{self.ram_gb} GB",
            f"GPU：{'、'.join(self.gpu_names) or '未知'}",
            f"推荐编码器：{self.encoder_label}",
            f"管理员权限：{'是' if self.admin else '否'}",
            "",
            f"Sunshine：{'已安装' if self.sunshine.installed else '未安装'}"
            f" / {'运行中' if self.sunshine.running else '未运行'}",
            f"  路径：{self.sunshine.root or '-'}",
            f"  版本：{self.sunshine.version or '-'}",
            f"  配置：{self.sunshine.conf or '-'}"
            f"（{'可写' if self.sunshine.config_writable else '不可写'}）",
            f"  encoder：{self.sunshine.encoder() or '未设置'}",
            "",
            f"虚拟显示器：{self.vdd_kind}",
        ]
        display = self.virtual_display
        if display is not None:
            lines.extend([
                f"  设备：{display.adapter}",
                f"  当前模式：{display.resolution} @ {display.refresh}Hz",
                f"  支持 3392×2400：{'是' if self.supports_pad_native else '否'}",
            ])
        lines.extend([
            "",
            f"IPv4：{'、'.join(self.ips) or '未获取'}",
            f"Tailscale：{self.tailscale.link}"
            f"（IP {self.tailscale.ipv4 or '-'}，直连 {self.tailscale.peers_direct} / 中继 {self.tailscale.peers_relay}）",
            f"防火墙规则：{'已存在' if self.firewall_rule else ('不存在' if self.firewall_rule is False else '未知')}",
            "",
            "显示器：",
        ])
        for item in self.displays:
            flags = []
            if item.primary:
                flags.append("主屏")
            if item.virtual:
                flags.append("虚拟")
            lines.append(
                f"  {item.device} {item.adapter} / {item.monitor or '-'} "
                f"{item.resolution} @ {item.refresh}Hz {' '.join(flags)}".rstrip()
            )
        return "\n".join(lines)


def _firewall_rule_present() -> bool | None:
    code, out = win.run(
        ["netsh", "advfirewall", "firewall", "show", "rule", "name=PadLink Host"],
        timeout=8,
    )
    if code != 0:
        return None
    lowered = out.lower()
    if "padlink" not in lowered:
        return False
    markers = ("no rules match", "没有与指定条件相匹配的规则", "没有与指定条件匹配的规则")
    if any(marker in lowered for marker in markers):
        return False
    return True


def collect(sunshine_override: str = "", include_modes: bool = True) -> Snapshot:
    started = time.time()
    try:
        os_info = win.get_os_info()
        gpus = win.get_gpus()
        snapshot = Snapshot(
            os=os_info,
            cpu=win.get_cpu_name(),
            ram_gb=win.get_ram_gb(),
            gpus=gpus,
            displays=win.get_displays(include_modes=include_modes),
            ips=win.get_ipv4_addresses(),
            admin=win.is_admin(),
            sunshine=sunshine_mod.detect(sunshine_override),
            tailscale=tailscale_mod.status(),
            firewall_rule=_firewall_rule_present(),
            recommended_encoder=win.pick_encoder(gpus),
            generated_at=started,
        )
        return snapshot
    except Exception as exc:  # 任何一项探测失败都不应让界面空掉
        return Snapshot(
            os=win.OsInfo(hostname=""),
            cpu="",
            ram_gb=0.0,
            gpus=[],
            displays=[],
            ips=[],
            admin=win.is_admin(),
            sunshine=SunshineState(),
            tailscale=TailscaleState(),
            generated_at=started,
            error=f"{type(exc).__name__}: {exc}",
        )
