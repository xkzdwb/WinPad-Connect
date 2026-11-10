"""下发给平板端的 profile（协议 v1）。

平板端只依赖这一个 JSON：它既是「连接说明书」，也是「体检结论」。
字段一旦发布就不要改名，新增字段保持向后兼容。
"""

from __future__ import annotations

import time

from . import sunshine as sunshine_mod
from .snapshot import PAD_TIERS, Snapshot
from .version import APP_NAME, APP_VERSION, PROTOCOL_VERSION


def _display(snapshot: Snapshot) -> dict:
    display = snapshot.virtual_display
    if display is None:
        return {"detected": False, "kind": "未检测到", "resolution": "", "supports_pad": False}
    return {
        "detected": True,
        "kind": snapshot.vdd_kind,
        "name": display.adapter,
        "resolution": display.resolution,
        "refresh": display.refresh,
        "supports_pad": snapshot.supports_pad_native,
    }


def build(snapshot: Snapshot, service, checks: list, score: int) -> dict:
    ts = snapshot.tailscale
    lan = snapshot.lan_ips()
    service_info = {
        "running": bool(getattr(service, "running", False)),
        "port": int(getattr(service, "port", 47800)),
        "code_required": bool(getattr(service, "code_required", True)),
    }
    return {
        "service": "padlink",
        "protocol": PROTOCOL_VERSION,
        "app": f"{APP_NAME} {APP_VERSION}",
        "generated_at": int(time.time()),
        "host": {
            "name": snapshot.os.hostname,
            "os": snapshot.os.display,
            "cpu": snapshot.cpu,
            "ram_gb": snapshot.ram_gb,
            "gpu": snapshot.primary_gpu,
            "encoder": snapshot.encoder,
            "encoder_label": snapshot.encoder_label,
            "admin": snapshot.admin,
        },
        "sunshine": {
            "installed": snapshot.sunshine.installed,
            "running": snapshot.sunshine.running,
            "version": snapshot.sunshine.version,
            "web": snapshot.sunshine.web_url if snapshot.sunshine.installed else "",
            "locked": bool(
                snapshot.sunshine.config
                and all(
                    snapshot.sunshine.config.get(key) == value
                    for key, value in sunshine_mod.LOW_LATENCY_PROFILES.get(
                        snapshot.encoder, {"keys": []}
                    )["keys"]
                )
            ),
        },
        "display": _display(snapshot),
        "network": {
            "lan": lan,
            "primary": lan[0] if lan else "",
            "tailscale": {
                "installed": ts.installed,
                "state": ts.link,
                "ipv4": ts.ipv4,
                "direct": ts.peers_direct,
                "relay": ts.peers_relay,
            },
            "service_port": service_info["port"],
        },
        "client": {
            "tiers": PAD_TIERS,
            "fps": 60,
            "codec": "HEVC" if snapshot.encoder == "nvenc" else "H.264",
            "note": "码率为 60fps 的起点值，实际以平板端体检测得的吞吐为准。",
        },
        "readiness": {
            "score": score,
            "checks": [
                {
                    "key": check.key,
                    "title": check.title,
                    "status": check.status,
                    "detail": check.detail,
                }
                for check in checks
            ],
        },
        "service_info": service_info,
        "code_required": service_info["code_required"],
    }
