"""基线体检规则。

每条检查只回答两件事：现在处于什么状态、下一步该做什么。
页面的「就绪度」与下发给平板端的结论都从这里算，保证口径一致。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import platform_windows as win
from . import sunshine as sunshine_mod
from .snapshot import Snapshot


STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"

STATUS_TEXT = {
    STATUS_OK: "通过",
    STATUS_WARN: "待优化",
    STATUS_FAIL: "未通过",
    STATUS_UNKNOWN: "未知",
}

# 各检查对「就绪度」的权重，合计 100
WEIGHTS = {
    "windows": 5,
    "encoder": 10,
    "install": 15,
    "running": 10,
    "lock": 15,
    "vdd": 10,
    "network": 20,
    "service": 10,
    "firewall": 5,
}


@dataclass
class Check:
    key: str
    title: str
    status: str
    detail: str
    hint: str = ""
    target: str = ""

    @property
    def status_text(self) -> str:
        return STATUS_TEXT.get(self.status, self.status)


def _locked(snapshot: Snapshot) -> tuple[bool, str]:
    profile = sunshine_mod.LOW_LATENCY_PROFILES.get(snapshot.encoder)
    if not profile or not snapshot.sunshine.config:
        return False, "配置尚为空"
    mismatches = [
        f"{key}={snapshot.sunshine.config.get(key, '未设置')}（期望 {value}）"
        for key, value in profile["keys"]
        if snapshot.sunshine.config.get(key) != value
    ]
    if mismatches:
        return False, "；".join(mismatches[:3])
    return True, "已锁定 " + "、".join(key for key, _ in profile["keys"])


def evaluate(snapshot: Snapshot, service) -> tuple[list[Check], int]:
    checks: list[Check] = []

    # 1. 系统版本
    if snapshot.os.supported:
        checks.append(Check(
            "windows", "Windows 版本", STATUS_OK, snapshot.os.display,
            "满足 Windows 10 22H2 及以上要求。", "",
        ))
    else:
        checks.append(Check(
            "windows", "Windows 版本", STATUS_FAIL, snapshot.os.display or "无法识别",
            "Foundation Sunshine 要求 Windows 10 22H2（Build 19045）及以上。", "",
        ))

    # 2. 硬件编码器
    encoder = snapshot.recommended_encoder
    if encoder == "software":
        checks.append(Check(
            "encoder", "硬件编码器", STATUS_FAIL,
            "未识别到 NVIDIA / Intel / AMD 显卡",
            "远程桌面依赖硬件编码；请安装显卡驱动后重新检测。", "",
        ))
    else:
        label = sunshine_mod.LOW_LATENCY_PROFILES[encoder]["label"]
        delay = sunshine_mod.LOW_LATENCY_PROFILES[encoder]["delay"]
        checks.append(Check(
            "encoder", "硬件编码器", STATUS_OK,
            f"{snapshot.encoder_gpu} · 推荐 {label}（典型 {delay}）",
            "", "",
        ))

    # 3. Sunshine 是否安装
    if snapshot.sunshine.installed:
        checks.append(Check(
            "install", "Sunshine 基线", STATUS_OK,
            f"{snapshot.sunshine.root} · {snapshot.sunshine.version or '版本未知'}",
            "", "",
        ))
    else:
        checks.append(Check(
            "install", "Sunshine 基线", STATUS_FAIL, "未检测到 Sunshine",
            "安装 Foundation Sunshine（含 ZakoVDD）后再回到本页一键装配。", "baseline",
        ))

    # 4. 是否在运行
    if snapshot.sunshine.running or snapshot.sunshine.web_https:
        checks.append(Check(
            "running", "Sunshine 服务", STATUS_OK,
            "进程/管理后台可达" + ("（47990）" if snapshot.sunshine.web_https else ""),
            "", "",
        ))
    elif snapshot.sunshine.installed:
        checks.append(Check(
            "running", "Sunshine 服务", STATUS_WARN, "已安装但未运行",
            "在「基线装配」页启动，或让 Sunshine 随系统启动。", "baseline",
        ))
    else:
        checks.append(Check("running", "Sunshine 服务", STATUS_FAIL, "不可用", "", ""))

    # 5. 低延迟参数
    if snapshot.sunshine.installed:
        locked, detail = _locked(snapshot)
        if locked:
            checks.append(Check("lock", "低延迟编码参数", STATUS_OK, detail, "", ""))
        else:
            checks.append(Check(
                "lock", "低延迟编码参数", STATUS_WARN, detail,
                "在「基线装配」页写入推荐参数，然后重启 Sunshine。", "baseline",
            ))
    else:
        checks.append(Check("lock", "低延迟编码参数", STATUS_FAIL, "等待安装基线", "", ""))

    # 6. 虚拟显示器
    kind = snapshot.vdd_kind
    if kind == "ZakoVDD":
        checks.append(Check(
            "vdd", "虚拟显示器", STATUS_OK,
            f"ZakoVDD · {snapshot.virtual_display.resolution if snapshot.virtual_display else ''}",
            "支持随串流创建/销毁，熄屏或无头可串流。", "",
        ))
    elif kind == "未检测到":
        checks.append(Check(
            "vdd", "虚拟显示器", STATUS_WARN, "未检测到虚拟显示器",
            "安装 ZakoVDD（Foundation Sunshine 自带）后可熄屏串流；否则需保持显示器开启。", "baseline",
        ))
    else:
        checks.append(Check(
            "vdd", "虚拟显示器", STATUS_WARN, f"{kind}（非 ZakoVDD）",
            "可以串流，但不会随串流自动创建/销毁，熄屏场景需手动切换显示模式。", "baseline",
        ))

    # 7. 网络
    ts = snapshot.tailscale
    if ts.running and ts.link_ok:
        checks.append(Check(
            "network", "网络链路", STATUS_OK,
            f"Tailscale 直连 · {ts.ipv4 or '无 IPv4'}",
            "异地可当作局域网使用。", "",
        ))
    elif ts.running and ts.peers_relay:
        checks.append(Check(
            "network", "网络链路", STATUS_WARN,
            f"Tailscale 中继 · 直连 {ts.peers_direct} / 中继 {ts.peers_relay}",
            "中继会明显抬高延迟；检查两端 NAT 类型，优先恢复直连。", "network",
        ))
    elif ts.installed:
        checks.append(Check(
            "network", "网络链路", STATUS_WARN,
            f"Tailscale：{ts.link}",
            "登录并确认 tailscale status 中出现 direct，再用异地地址连接。", "network",
        ))
    else:
        checks.append(Check(
            "network", "网络链路", STATUS_WARN,
            f"仅局域网 · {'、'.join(snapshot.lan_ips()) or '无地址'}",
            "跨网络需要 Tailscale（或其它叠加网络）；局域网内可直接使用。", "network",
        ))

    # 8. 接入服务
    if service is not None and getattr(service, "running", False):
        checks.append(Check(
            "service", "平板接入服务", STATUS_OK,
            f"监听 0.0.0.0:{getattr(service, 'port', 47800)}",
            "", "",
        ))
    else:
        checks.append(Check(
            "service", "平板接入服务", STATUS_WARN, "未启动",
            "启动后平板端可自动发现并读取本机参数。", "network",
        ))

    # 9. 防火墙
    if snapshot.firewall_rule is True:
        checks.append(Check("firewall", "防火墙规则", STATUS_OK, "Win-Pad Connect 放行规则存在", "", ""))
    elif snapshot.firewall_rule is False:
        checks.append(Check(
            "firewall", "防火墙规则", STATUS_WARN, "未添加放行规则",
            "首次启动时若系统弹窗请选择「允许访问」；也可一键添加入站规则。", "network",
        ))
    else:
        checks.append(Check("firewall", "防火墙规则", STATUS_UNKNOWN, "无法查询（可能缺少权限）", "", ""))

    # 权重得分
    total = 0.0
    earned = 0.0
    factor = {STATUS_OK: 1.0, STATUS_WARN: 0.5, STATUS_UNKNOWN: 0.3, STATUS_FAIL: 0.0}
    for check in checks:
        weight = WEIGHTS.get(check.key, 0)
        total += weight
        earned += weight * factor.get(check.status, 0.0)
    score = int(round(100 * earned / total)) if total else 0
    return checks, score


def summary(checks: list[Check]) -> dict:
    counts = {STATUS_OK: 0, STATUS_WARN: 0, STATUS_FAIL: 0, STATUS_UNKNOWN: 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    return counts


def headline(score: int, checks: list[Check]) -> str:
    if score >= 90:
        return "基线就绪，可以开始串流"
    blocking = [check for check in checks if check.status == STATUS_FAIL]
    if blocking:
        return f"还差 {len(blocking)} 项才能开始"
    return "可用，但仍有可优化项"
