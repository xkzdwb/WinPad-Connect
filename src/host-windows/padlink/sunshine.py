"""Foundation Sunshine 基线的探测、配置与进程控制。

这里只做「装配」而不重写串流：
* 找到安装位置（注册表 + 常见目录）
* 读取 / 备份 / 增量修改 ``config/sunshine.conf``
* 锁定各硬件编码器的低延迟参数
* 读取日志尾部，供诊断页展示
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import platform_windows as win
from .paths import backups_dir

# 每个编码器写入的键值。键名与 Sunshine 官方配置项一致；
# 未识别的键会被 Sunshine 忽略并在日志中提示，不会破坏启动。
LOW_LATENCY_PROFILES: dict[str, dict] = {
    "nvenc": {
        "label": "NVIDIA NVENC",
        "delay": "10–15 ms",
        "keys": [
            ("encoder", "nvenc"),
            ("nvenc_preset", "p4"),
            ("nvenc_tune", "ll"),
            ("nvenc_rc", "cbr"),
            ("nvenc_realtime_hags", "enabled"),
        ],
        "notes": "p4 为低延迟档，ll 让 NVENC 放弃 B 帧与前瞻，cbr 稳定码率。",
    },
    "qsv": {
        "label": "Intel Quick Sync",
        "delay": "12–18 ms",
        "keys": [
            ("encoder", "qsv"),
            ("qsv_preset", "fast"),
            ("qsv_slow", "disabled"),
        ],
        "notes": "fast 预设 + 关闭 slow 模式，牺牲少量压缩率换编码延迟。",
    },
    "amdvce": {
        "label": "AMD AMF / VCE",
        "delay": "15–20 ms",
        "keys": [
            ("encoder", "amdvce"),
            ("amd_quality", "speed"),
            ("amd_rc", "cbr"),
            ("amd_preanalysis", "disabled"),
            ("amd_vbaq", "disabled"),
        ],
        "notes": "关闭预分析（preanalysis）与 VBAQ，避免编码器排队。",
    },
    "software": {
        "label": "软件编码（不推荐）",
        "delay": "> 25 ms",
        "keys": [
            ("encoder", "software"),
            ("sw_preset", "superfast"),
        ],
        "notes": "仅在无可用硬件编码器时作为兜底，CPU 占用高、延迟大。",
    },
}

PADLINK_MARKER = "# --- PadLink low-latency profile (managed) ---"

# Pad（3392×2400，3:2）常用串流档位
CLIENT_RESOLUTIONS = ["1920×1080", "2560×1600", "3392×2400"]


@dataclass
class SunshineState:
    installed: bool = False
    root: str = ""
    exe: str = ""
    conf: str = ""
    version: str = ""
    running: bool = False
    web_http: bool = False
    web_https: bool = False
    source: str = ""
    config: dict[str, str] = field(default_factory=dict)
    config_error: str = ""

    @property
    def web_url(self) -> str:
        return "https://localhost:47990"

    @property
    def config_writable(self) -> bool:
        if not self.conf:
            return False
        path = Path(self.conf)
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            return os.access(path.parent, os.W_OK)
        except OSError:
            return False

    def encoder(self) -> str:
        return (self.config.get("encoder") or "").strip().lower()


UNINSTALL_KEYS = [
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 64),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", 32),
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 32),
]


def _scan_registry() -> list[dict]:
    import winreg

    found: list[dict] = []
    for subkey, _bits in UNINSTALL_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as root:
                count = winreg.QueryInfoKey(root)[0]
                for index in range(count):
                    try:
                        name = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, subkey + "\\" + name) as entry:
                            display = winreg.QueryValueEx(entry, "DisplayName")[0]
                            if not isinstance(display, str) or "sunshine" not in display.lower():
                                continue
                            location = ""
                            try:
                                location = winreg.QueryValueEx(entry, "InstallLocation")[0]
                            except OSError:
                                pass
                            version = ""
                            try:
                                version = winreg.QueryValueEx(entry, "DisplayVersion")[0]
                            except OSError:
                                pass
                            found.append({
                                "display": display,
                                "location": location or "",
                                "version": str(version or ""),
                            })
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        for name in (
            "Sunshine",
            "Foundation Sunshine",
            Path("Programs") / "Sunshine",
            Path("Programs") / "Foundation Sunshine",
        ):
            roots.append(Path(base) / name)
    roots.append(Path(r"C:\Sunshine"))
    return roots


def detect(override_path: str = "", running: bool | None = None) -> SunshineState:
    state = SunshineState()
    roots: list[Path] = []
    if override_path:
        candidate = Path(override_path)
        if candidate.is_file():
            roots.append(candidate.parent)
        else:
            roots.append(candidate)
        state.source = "手动指定"

    if not roots:
        for entry in _scan_registry():
            location = entry.get("location", "")
            if location:
                roots.append(Path(location))
                state.source = f"注册表：{entry['display']}"
                if not state.version:
                    state.version = entry.get("version", "")
        if not roots:
            for candidate in _candidate_roots():
                if candidate.exists():
                    roots.append(candidate)
            if roots:
                state.source = "常见安装目录"

    for root in roots:
        exe = root / "sunshine.exe"
        if not exe.exists():
            # 有些安装包直接放在子目录 bin/ 下
            alt = root / "bin" / "sunshine.exe"
            if alt.exists():
                exe = alt
            else:
                continue
        state.installed = True
        state.root = str(root)
        state.exe = str(exe)
        break

    if state.installed:
        conf_candidates = [
            Path(state.root) / "config" / "sunshine.conf",
            Path(state.root) / "sunshine.conf",
        ]
        for conf in conf_candidates:
            if conf.exists():
                state.conf = str(conf)
                break
        if not state.conf:
            state.conf = str(Path(state.root) / "config" / "sunshine.conf")
        state.config, state.config_error = read_conf(state.conf)
        if not state.version:
            state.version = file_version(state.exe)

    if running is None:
        running = win.process_running("sunshine.exe", "sunshine-service.exe")
    state.running = running
    if state.installed or running:
        state.web_http = win.port_open("127.0.0.1", 47989, 0.35)
        state.web_https = win.port_open("127.0.0.1", 47990, 0.35)
    return state


def file_version(exe: str) -> str:
    if not exe or not os.path.exists(exe):
        return ""
    try:
        info = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Item -LiteralPath '{exe}').VersionInfo.FileVersion"],
            capture_output=True,
            timeout=8,
            creationflags=win.CREATE_NO_WINDOW,
        )
        text = win._decode(info.stdout).strip()
        return text.splitlines()[0] if text else ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# 配置文件读写
# --------------------------------------------------------------------------- #

def read_conf(path: str) -> tuple[dict[str, str], str]:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return {}, str(exc)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("mbcs", "replace")
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values, ""


def preview_profile(encoder: str) -> list[str]:
    profile = LOW_LATENCY_PROFILES.get(encoder) or LOW_LATENCY_PROFILES["software"]
    return [f"{key} = {value}" for key, value in profile["keys"]]


def apply_profile(conf_path: str, encoder: str) -> tuple[bool, str]:
    """把低延迟参数增量写入配置文件，返回 (成功, 说明)。

    * 只改目标键，保留用户其它配置与注释顺序
    * 写入前在配置目录（不可写时在 %APPDATA%\\PadLink\\backups）留一份时间戳备份
    """
    profile = LOW_LATENCY_PROFILES.get(encoder)
    if not profile:
        return False, f"未知编码器：{encoder}"
    path = Path(conf_path)
    if not path.exists():
        return False, f"配置文件不存在：{conf_path}"

    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("mbcs", "replace")
        encoding = "mbcs"

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path: Path | None = None
    for target in (path.with_name(path.name + f".{stamp}.bak"), backups_dir() / f"sunshine.conf.{stamp}.bak"):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            backup_path = target
            break
        except OSError:
            continue
    if backup_path is None:
        return False, "无法创建配置备份，已中止写入"

    updates = dict(profile["keys"])
    lines = text.splitlines()
    seen: set[str] = set()
    rebuilt: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                rebuilt.append(f"{key} = {updates[key]}")
                seen.add(key)
                continue
        rebuilt.append(line)

    missing = [(key, value) for key, value in profile["keys"] if key not in seen]
    if missing:
        if rebuilt and rebuilt[-1].strip():
            rebuilt.append("")
        rebuilt.append(PADLINK_MARKER)
        rebuilt.extend(f"{key} = {value}" for key, value in missing)
        rebuilt.append("# 由 PadLink Host 写入；恢复：删除以上键或还原同目录 .bak 文件")

    newline = "\r\n" if "\r\n" in text else "\n"
    payload = newline.join(rebuilt) + newline
    try:
        path.write_text(payload, encoding=encoding, newline="")
    except OSError as exc:
        return False, f"写入失败：{exc}（可尝试以管理员身份运行）"
    return True, f"已写入 {len(profile['keys'])} 个键，备份：{backup_path}"


def latest_backup(conf_path: str) -> Path | None:
    if not conf_path:
        return None
    folder = Path(conf_path).parent
    candidates: list[Path] = []
    try:
        candidates.extend(folder.glob(Path(conf_path).name + ".*.bak"))
    except OSError:
        pass
    try:
        candidates.extend(backups_dir().glob("sunshine.conf.*.bak"))
    except OSError:
        pass
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def restore_backup(conf_path: str) -> tuple[bool, str]:
    backup = latest_backup(conf_path)
    if backup is None:
        return False, "没有找到可用的配置备份"
    try:
        shutil.copy2(backup, conf_path)
    except OSError as exc:
        return False, f"还原失败：{exc}"
    return True, f"已从 {backup.name} 还原（重启 Sunshine 后生效）"


# --------------------------------------------------------------------------- #
# 进程与日志
# --------------------------------------------------------------------------- #

def start(state: SunshineState) -> tuple[bool, str]:
    if not state.installed:
        return False, "尚未检测到 Sunshine 安装目录"
    if state.running:
        return True, "Sunshine 已在运行"
    try:
        subprocess.Popen(
            [state.exe],
            cwd=state.root,
            creationflags=win.CREATE_NO_WINDOW | 0x00000008,  # DETACHED_PROCESS
            close_fds=True,
        )
    except OSError as exc:
        return False, f"启动失败：{exc}"
    return True, "已发出启动请求，稍候刷新状态"


def stop() -> tuple[bool, str]:
    code, out = win.run(["taskkill", "/IM", "sunshine.exe", "/F"], timeout=8)
    if code == 0:
        return True, "已结束 Sunshine 进程"
    return False, out or "Sunshine 未在运行"


def log_candidates(state: SunshineState) -> list[Path]:
    paths: list[Path] = []
    if state.root:
        paths.append(Path(state.root) / "config" / "sunshine.log")
        paths.append(Path(state.root) / "sunshine.log")
    for env in ("LOCALAPPDATA", "PROGRAMDATA"):
        base = os.environ.get(env)
        if base:
            paths.append(Path(base) / "Sunshine" / "sunshine.log")
            paths.append(Path(base) / "Sunshine" / "config" / "sunshine.log")
    return paths


def find_log(state: SunshineState) -> Path | None:
    for path in log_candidates(state):
        try:
            if path.exists():
                return path
        except OSError:
            continue
    return None


def log_tail(state: SunshineState, lines: int = 160) -> tuple[str, str]:
    path = find_log(state)
    if path is None:
        return "", "未找到 sunshine.log（Sunshine 运行后才会生成）"
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 96 * 1024))
            payload = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        return "", f"读取日志失败：{exc}"
    tail = payload.splitlines()[-lines:]
    return "\n".join(tail), ""
