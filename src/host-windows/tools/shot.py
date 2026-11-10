"""对正在运行的 PadLink Host 窗口截图（Windows，仅开发验收用）。

用 PrintWindow 抓取窗口自身位图，即使被其它窗口遮挡也能得到干净画面。
用法：python tools/shot.py 输出.png [宽 高]
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

from PIL import Image

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
PW_RENDERFULLCONTENT = 0x00000002


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def find_window(prefix: str = "PadLink Host") -> int:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value.startswith(prefix) and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else 0


def grab(hwnd: int) -> Image.Image:
    """抓取窗口客户区（PrintWindow 会连边框一起画，这里按客户区裁掉）。"""
    window_rect = wt.RECT()
    client_rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
    user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    width = window_rect.right - window_rect.left
    height = window_rect.bottom - window_rect.top

    origin = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    offset_x = origin.x - window_rect.left
    offset_y = origin.y - window_rect.top

    window_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)
    user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height  # 自上而下
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, window_dc)

    image = Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    box = (offset_x, offset_y, offset_x + client_rect.right, offset_y + client_rect.bottom)
    return image.crop(box)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "shots/window.png")
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 960
    prefix = sys.argv[4] if len(sys.argv) > 4 else "PadLink Host"
    out.parent.mkdir(parents=True, exist_ok=True)
    hwnd = find_window(prefix)
    if not hwnd:
        print(f"没有找到标题以 {prefix!r} 开头的窗口")
        return 1
    user32.ShowWindow(hwnd, 9)
    if width > 0 and height > 0:
        user32.MoveWindow(hwnd, 80, 40, width, height, True)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.9)
    image = grab(hwnd)
    image.save(out)
    print(f"saved {out} {image.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
