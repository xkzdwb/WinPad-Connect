"""Windows 平台能力封装。

只依赖标准库与 ctypes：
* 系统 / CPU / 内存 / GPU / 显示器信息
* 进程枚举（Toolhelp32，不需要管理员权限）
* 端口探测、网卡地址、提权重启

GUI 与 ``--smoke-test`` 共用这一层，任何函数在受限环境下都应返回空值
而不是抛异常，让界面能照常显示「未知」。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import socket
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CREATE_NO_WINDOW = 0x08000000
SW_SHOWNORMAL = 1
MAX_PATH = 260


# --------------------------------------------------------------------------- #
# 进程执行
# --------------------------------------------------------------------------- #

def _decode(raw: bytes | None) -> str:
    if not raw:
        return ""
    for enc in ("utf-8-sig", "mbcs"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def run(args: Iterable[str], timeout: float = 10.0, cwd: str | None = None) -> tuple[int, str]:
    """执行命令，返回 (退出码, 合并后的输出)。失败不抛异常。"""
    argv = [str(a) for a in args]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return 127, f"未找到程序：{argv[0] if argv else ''}"
    except subprocess.TimeoutExpired:
        return 124, "命令执行超时"
    except OSError as exc:
        return 1, str(exc)
    return proc.returncode, (_decode(proc.stdout) + _decode(proc.stderr)).strip()


def open_path(path: str | os.PathLike) -> None:
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except OSError:
        pass


def open_url(url: str) -> None:
    try:
        os.startfile(url)  # type: ignore[attr-defined]
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 权限 / 提权
# --------------------------------------------------------------------------- #

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return False


def elevation_command() -> tuple[str, str, str] | None:
    """返回 (exe, params, cwd)，供 ShellExecuteW runas 以管理员身份重启自身。"""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            exe = exe[: -len("python.exe")] + "pythonw.exe"
            if not os.path.exists(exe):
                exe = sys.executable
        script = os.path.abspath(sys.argv[0])
        params = subprocess.list2cmdline([script, *sys.argv[1:], "--elevated"])
    return exe, params, os.getcwd()


def relaunch_as_admin() -> tuple[bool, str]:
    spec = elevation_command()
    if spec is None:
        return False, "无法构造提权命令"
    exe, params, cwd = spec
    try:
        result = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
            None, "runas", exe, params, cwd, SW_SHOWNORMAL
        )
    except Exception as exc:  # pragma: no cover - 依赖桌面环境
        return False, str(exc)
    # ShellExecuteW 返回值 > 32 表示成功
    if result > 32:
        return True, "已请求管理员权限"
    return False, f"提权被拒绝或取消（{result}）"


def enable_dpi_awareness() -> None:
    """在创建 Tk 根窗口之前调用，避免高 DPI 下字体发糊。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 系统信息
# --------------------------------------------------------------------------- #

@dataclass
class OsInfo:
    name: str = "Windows"
    version: str = ""
    build: int = 0
    ubr: int = 0
    arch: str = ""
    hostname: str = ""

    @property
    def display(self) -> str:
        v = f" {self.version}" if self.version else ""
        b = f" · Build {self.build}" if self.build else ""
        return f"{self.name}{v}{b}"

    @property
    def supported(self) -> bool:
        return self.build >= 19045


def _reg_value(root: int, path: str, name: str):
    import winreg  # 局部导入：非 Windows 平台上导入失败也不影响其它函数

    try:
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return None


def get_os_info() -> OsInfo:
    import winreg

    product = _reg_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "ProductName",
    ) or "Windows"
    version = _reg_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "DisplayVersion",
    ) or ""
    build_raw = _reg_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "CurrentBuildNumber",
    )
    try:
        build = int(str(build_raw))
    except (TypeError, ValueError):
        build = 0
    try:
        ubr = int(_reg_value(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            "UBR",
        ) or 0)
    except (TypeError, ValueError):
        ubr = 0

    # Windows 11 的 ProductName 一直写作 "Windows 10 ..."，以 build 号为准。
    if build >= 22000:
        product = product.replace("Windows 10", "Windows 11")
    return OsInfo(
        name=product,
        version=version,
        build=build,
        ubr=ubr,
        arch=os.environ.get("PROCESSOR_ARCHITECTURE", ""),
        hostname=socket.gethostname(),
    )


def get_cpu_name() -> str:
    import winreg

    value = _reg_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        "ProcessorNameString",
    )
    return str(value).strip() if value else ""


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wt.DWORD),
        ("dwMemoryLoad", wt.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_ram_gb() -> float:
    try:
        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0


GPU_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


def get_gpus() -> list[dict]:
    """从注册表读取显示适配器，绕开在受限环境下会被拒绝的 WMI。"""
    import winreg

    gpus: list[dict] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, GPU_CLASS_KEY) as key:
            count = winreg.QueryInfoKey(key)[0]
            for index in range(count):
                try:
                    sub_name = winreg.EnumKey(key, index)
                except OSError:
                    break
                if not sub_name.isdigit():
                    continue
                sub_path = GPU_CLASS_KEY + "\\" + sub_name
                desc = _reg_value(winreg.HKEY_LOCAL_MACHINE, sub_path, "DriverDesc")
                if not desc:
                    continue
                vendor = _reg_value(winreg.HKEY_LOCAL_MACHINE, sub_path, "ProviderName") or ""
                version = _reg_value(winreg.HKEY_LOCAL_MACHINE, sub_path, "DriverVersion") or ""
                gpus.append({
                    "name": str(desc).strip(),
                    "vendor": str(vendor).strip(),
                    "driver": str(version).strip(),
                })
    except OSError:
        pass

    # 去重（同一张卡可能出现多个实例键），保留顺序
    seen: set[str] = set()
    unique: list[dict] = []
    for gpu in gpus:
        key = gpu["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(gpu)
    return unique


VIRTUAL_GPU_HINTS = (
    "spacedesk", "virtual", "zako", "parsec", "meta", "oppo", "displaydriver",
    "idd", "usb display", "remote",
)


def gpu_is_virtual(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in VIRTUAL_GPU_HINTS)


def pick_encoder(gpus: list[dict]) -> str:
    names = " ".join(g["name"].lower() for g in gpus)
    if "nvidia" in names:
        return "nvenc"
    if "intel" in names or "arc" in names:
        return "qsv"
    if "amd" in names or "radeon" in names:
        return "amdvce"
    return "software"


# --------------------------------------------------------------------------- #
# 显示器
# --------------------------------------------------------------------------- #

class _DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("DeviceName", wt.WCHAR * 32),
        ("DeviceString", wt.WCHAR * 128),
        ("StateFlags", wt.DWORD),
        ("DeviceID", wt.WCHAR * 128),
        ("DeviceKey", wt.WCHAR * 128),
    ]


class _DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wt.WCHAR * 32),
        ("dmSpecVersion", wt.WORD),
        ("dmDriverVersion", wt.WORD),
        ("dmSize", wt.WORD),
        ("dmDriverExtra", wt.WORD),
        ("dmFields", wt.DWORD),
        ("dmPositionX", wt.LONG),
        ("dmPositionY", wt.LONG),
        ("dmDisplayOrientation", wt.DWORD),
        ("dmDisplayFixedOutput", wt.DWORD),
        ("dmColor", wt.SHORT),
        ("dmDuplex", wt.SHORT),
        ("dmYResolution", wt.SHORT),
        ("dmTTOption", wt.SHORT),
        ("dmCollate", wt.SHORT),
        ("dmFormName", wt.WCHAR * 32),
        ("dmLogPixels", wt.WORD),
        ("dmBitsPerPel", wt.DWORD),
        ("dmPelsWidth", wt.DWORD),
        ("dmPelsHeight", wt.DWORD),
        ("dmDisplayFlags", wt.DWORD),
        ("dmDisplayFrequency", wt.DWORD),
        ("dmICMMethod", wt.DWORD),
        ("dmICMIntent", wt.DWORD),
        ("dmMediaType", wt.DWORD),
        ("dmDitherType", wt.DWORD),
        ("dmReserved1", wt.DWORD),
        ("dmReserved2", wt.DWORD),
        ("dmPanningWidth", wt.DWORD),
        ("dmPanningHeight", wt.DWORD),
    ]


ENUM_CURRENT_SETTINGS = -1
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x1
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x4
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x8


@dataclass
class DisplayInfo:
    device: str
    adapter: str
    monitor: str
    primary: bool = False
    width: int = 0
    height: int = 0
    refresh: int = 0
    virtual: bool = False
    modes: list[tuple[int, int, int]] = field(default_factory=list)

    @property
    def resolution(self) -> str:
        if not self.width or not self.height:
            return "未启用"
        return f"{self.width}×{self.height}"

    def supports(self, width: int, height: int) -> bool:
        return any(w == width and h == height for w, h, _ in self.modes)


def _enum_display_devices(device: str | None, index: int) -> _DISPLAY_DEVICEW | None:
    dd = _DISPLAY_DEVICEW()
    dd.cb = ctypes.sizeof(dd)
    ok = ctypes.windll.user32.EnumDisplayDevicesW(  # type: ignore[attr-defined]
        device, index, ctypes.byref(dd), 0
    )
    return dd if ok else None


def _current_mode(device: str) -> _DEVMODEW | None:
    dm = _DEVMODEW()
    dm.dmSize = ctypes.sizeof(dm)
    ok = ctypes.windll.user32.EnumDisplaySettingsW(  # type: ignore[attr-defined]
        device, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)
    )
    return dm if ok else None


def _modes(device: str, limit: int = 200) -> list[tuple[int, int, int]]:
    found: set[tuple[int, int, int]] = set()
    dm = _DEVMODEW()
    dm.dmSize = ctypes.sizeof(dm)
    index = 0
    while index < limit:
        ok = ctypes.windll.user32.EnumDisplaySettingsW(  # type: ignore[attr-defined]
            device, index, ctypes.byref(dm)
        )
        if not ok:
            break
        if dm.dmPelsWidth >= 1280 and dm.dmPelsHeight >= 720:
            found.add((int(dm.dmPelsWidth), int(dm.dmPelsHeight), int(dm.dmDisplayFrequency)))
        index += 1
    return sorted(found, key=lambda item: (item[0] * item[1], item[2]), reverse=True)


def get_displays(include_modes: bool = True) -> list[DisplayInfo]:
    displays: list[DisplayInfo] = []
    try:
        index = 0
        while True:
            adapter = _enum_display_devices(None, index)
            if adapter is None:
                break
            index += 1
            if adapter.StateFlags & DISPLAY_DEVICE_MIRRORING_DRIVER:
                continue
            attached = bool(adapter.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP)
            info = DisplayInfo(
                device=adapter.DeviceName,
                adapter=adapter.DeviceString,
                monitor="",
                primary=bool(adapter.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE),
                virtual=gpu_is_virtual(adapter.DeviceString),
            )
            monitor = _enum_display_devices(adapter.DeviceName, 0)
            if monitor is not None and monitor.DeviceString:
                info.monitor = monitor.DeviceString
            if attached:
                mode = _current_mode(adapter.DeviceName)
                if mode is not None:
                    info.width = int(mode.dmPelsWidth)
                    info.height = int(mode.dmPelsHeight)
                    info.refresh = int(mode.dmDisplayFrequency)
                if include_modes:
                    info.modes = _modes(adapter.DeviceName)
            displays.append(info)
    except Exception:
        return displays
    return displays


def find_display_for(displays: list[DisplayInfo], name_hint: str) -> DisplayInfo | None:
    hint = name_hint.lower()
    for display in displays:
        if hint and hint in (display.adapter + " " + display.monitor).lower():
            return display
    return None


# --------------------------------------------------------------------------- #
# 进程
# --------------------------------------------------------------------------- #

TH32CS_SNAPPROCESS = 0x00000002


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * MAX_PATH),
    ]


def list_process_names() -> set[str]:
    names: set[str] = set()
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        invalid = ctypes.c_void_p(-1).value
        if not snapshot or snapshot == invalid:
            return names
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while more:
                names.add(entry.szExeFile.lower())
                more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(snapshot))
    except Exception:
        return names
    return names


def process_running(*exe_names: str) -> bool:
    names = list_process_names()
    return any(name.lower() in names for name in exe_names)


# --------------------------------------------------------------------------- #
# 网络
# --------------------------------------------------------------------------- #

def port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _is_public(ip: str) -> bool:
    if ip.startswith(("127.", "169.254.", "0.")):
        return False
    return True


def get_ipv4_addresses() -> list[str]:
    """枚举本机 IPv4，不依赖外部命令。

    优先用 UDP connect 取默认出口地址（不会真的发包），再补充 hostname
    解析和 ipconfig 输出。这样即使子进程被系统策略禁止也能拿到局域网地址。
    """
    ips: list[str] = []
    for probe in ("8.8.8.8", "1.1.1.1", "223.5.5.5", "192.168.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.25)
                sock.connect((probe, 53))
                ip = sock.getsockname()[0]
        except OSError:
            continue
        if _is_public(ip) and ip not in ips:
            ips.append(ip)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if _is_public(ip) and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    code, output = run(["ipconfig"], timeout=6)
    if code == 0 and output:
        for line in output.splitlines():
            if "IPv4" not in line and "IP" not in line:
                continue
            match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", line)
            if match:
                ip = match.group(1)
                if _is_public(ip) and ip not in ips:
                    ips.append(ip)
    return ips


def is_tailscale_ip(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        return parts[0] == "100" and 64 <= int(parts[1]) <= 127
    except ValueError:
        return False


def lan_ip() -> str:
    """默认路由使用的本机地址；不实际发包。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        ips = get_ipv4_addresses()
        return ips[0] if ips else "127.0.0.1"


def tcp_latency_ms(host: str, port: int, samples: int = 4, timeout: float = 1.0) -> dict:
    """用 TCP 建连时间估算网络往返（与平板端体检口径一致）。"""
    import time

    timings: list[float] = []
    failed = 0
    for _ in range(max(1, samples)):
        start = time.perf_counter()
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                timings.append((time.perf_counter() - start) * 1000.0)
        except OSError:
            failed += 1
    if not timings:
        return {"ok": False, "min": 0.0, "avg": 0.0, "jitter": 0.0, "loss": 100.0}
    avg = sum(timings) / len(timings)
    jitter = 0.0
    if len(timings) > 1:
        jitter = sum(abs(timings[i] - timings[i - 1]) for i in range(1, len(timings))) / (len(timings) - 1)
    return {
        "ok": True,
        "min": round(min(timings), 1),
        "avg": round(avg, 1),
        "jitter": round(jitter, 1),
        "loss": round(100.0 * failed / (len(timings) + failed), 1),
    }


class _MIB_IPFORWARDROW(ctypes.Structure):
    _fields_ = [
        ("dwForwardDest", ctypes.c_ulong),
        ("dwForwardMask", ctypes.c_ulong),
        ("dwForwardPolicy", ctypes.c_ulong),
        ("dwForwardNextHop", ctypes.c_ulong),
        ("dwForwardIfIndex", ctypes.c_ulong),
        ("dwForwardType", ctypes.c_ulong),
        ("dwForwardProto", ctypes.c_ulong),
        ("dwForwardAge", ctypes.c_ulong),
        ("dwForwardNextHopAS", ctypes.c_ulong),
        ("dwForwardMetric1", ctypes.c_ulong),
        ("dwForwardMetric2", ctypes.c_ulong),
        ("dwForwardMetric3", ctypes.c_ulong),
        ("dwForwardMetric4", ctypes.c_ulong),
        ("dwForwardMetric5", ctypes.c_ulong),
    ]


class _MIB_IPFORWARDTABLE(ctypes.Structure):
    _fields_ = [("dwNumEntries", ctypes.c_ulong), ("table", _MIB_IPFORWARDROW * 1)]


def default_gateway() -> str:
    """用 GetIpForwardTable 取默认路由下一跳（不依赖外部命令）。"""
    try:
        table_size = ctypes.c_ulong(0)
        iphlpapi = ctypes.windll.iphlpapi
        iphlpapi.GetIpForwardTable(None, ctypes.byref(table_size), False)
        buffer = ctypes.create_string_buffer(table_size.value)
        if iphlpapi.GetIpForwardTable(buffer, ctypes.byref(table_size), False) != 0:
            return ""
        table = ctypes.cast(buffer, ctypes.POINTER(_MIB_IPFORWARDTABLE)).contents
        for index in range(table.dwNumEntries):
            row = table.table[index]
            if row.dwForwardDest == 0 and row.dwForwardMask == 0 and row.dwForwardNextHop:
                return socket.inet_ntoa(struct.pack("<L", row.dwForwardNextHop))
    except (AttributeError, OSError, ValueError):
        pass
    # 兜底：解析 ipconfig（子进程被禁用时自然失败）
    code, out = run(["ipconfig"], timeout=6)
    if code != 0:
        return ""
    match = re.search(
        r"(?:Default Gateway|默认网关)[^\n:]*:\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})",
        out,
    )
    if match and match.group(1) != "0.0.0.0":
        return match.group(1)
    return ""


def ping_ms(host: str, count: int = 4, timeout_ms: int = 1000) -> dict:
    """调用系统 ping，解析平均延迟；中英文输出都兼容。"""
    code, out = run(["ping", "-n", str(count), "-w", str(timeout_ms), host], timeout=count * 2 + 4)
    if code != 0 or not out:
        return {"ok": False, "host": host, "avg": 0.0, "loss": 100.0}
    avg = 0.0
    match = re.search(r"(?:Average|平均)\s*=\s*([0-9]+)\s*ms", out)
    if match:
        avg = float(match.group(1))
    else:
        samples = [float(value) for value in re.findall(r"(?:time|时间)[=<]\s*([0-9]+)\s*ms", out)]
        if samples:
            avg = sum(samples) / len(samples)
    loss_match = re.search(r"\(([0-9]+)%", out)
    loss = float(loss_match.group(1)) if loss_match else (0.0 if avg else 100.0)
    return {"ok": avg > 0, "host": host, "avg": round(avg, 1), "loss": loss}


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)
