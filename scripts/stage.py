"""构建 Win-Pad Connect 的安装载荷（在 DSH 沙箱内无需子进程即可完成）。

用法：
    python build/stage.py            # 生成 build/stage/app 与图标
    python build/stage.py --zip      # 再把 stage 打成 build/payload.zip

C# 的 csc 编译必须由 ops_bash 执行（沙箱禁止 Python 建子进程），编译产物放进
build/stage 后再次运行 --zip 即可。
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

APP_NAME = "Win-Pad Connect"
VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "host-windows"
STAGE = ROOT / "build" / "stage"
PAYLOAD = ROOT / "build" / "payload.zip"
ICON = ROOT / "build" / "winpad.ico"

SKIP_DIRS = {"__pycache__", ".tmp", ".padlink-data", "shots"}
SKIP_FILES = {".DS_Store"}


def copy_app() -> None:
    target = STAGE / "app"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    shutil.copytree(SRC / "padlink", target / "padlink", ignore=shutil.ignore_patterns(*SKIP_DIRS))
    for name in ("run.bat",):
        shutil.copy2(SRC / name, target / name)

    # 安装版只带运行所需文档
    docs = target / "docs"
    docs.mkdir()
    for name in ("deployment.md", "protocol-v1.md", "moonlight-android-integration.md", "acceptance.md"):
        dst = docs / name
        shutil.copy2(ROOT / "docs" / name, dst)
        text = dst.read_text(encoding="utf-8")
        text = text.replace("PadLink Host", APP_NAME).replace("PadLink Pad", APP_NAME + " Pad")
        text = text.replace("PadLink 只读写", APP_NAME + " 只读写").replace("PadLink 需要", APP_NAME + " 需要")
        dst.write_text(text, encoding="utf-8")
    shutil.copy2(SRC / "README.md", target / "README.md")

    # 品牌替换：只改用户可见名称与数据目录，协议标识 padlink 保持不变
    replacements = {
        '"PadLink Host"': '"Win-Pad Connect"',
        '"Windows → OPPO Pad 4 Pro 基线装配台"': '"Windows 主机端 · Moonlight / Sunshine 装配台"',
        "PadLink Host": APP_NAME,
        "%APPDATA%\\\\PadLink": "%APPDATA%\\\\Win-Pad Connect",
        '"PadLink"': f'"{APP_NAME}"',
        ".padlink-data": ".winpad-data",
        "PadLink": APP_NAME,
    }
    for py in (target / "padlink").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        py.write_text(text, encoding="utf-8")

    readme = target / "README.md"
    text = readme.read_text(encoding="utf-8").replace("PadLink Host", APP_NAME)
    readme.write_text(text, encoding="utf-8")

    bat = target / "run.bat"
    text = bat.read_text(encoding="utf-8").replace("PadLink Host", APP_NAME)
    bat.write_text(text, encoding="utf-8")

    (target / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (target / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2026 Win-Pad Connect contributors\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\"), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n",
        encoding="utf-8",
    )
    (target / "快速开始.txt").write_text(
        "Win-Pad Connect 1.0.0\n"
        "=====================\n\n"
        "1. 双击 Win-Pad Connect.exe 启动（需要 Python 3.10+）。\n"
        "2. 首次启动会自动开启接入服务，端口 47800，配对码在“接入服务”页。\n"
        "3. Sunshine 未安装时，先按 docs/deployment.md 安装 Foundation Sunshine。\n"
        "4. 平板端安装 Win-Pad Connect Pad，与电脑同一 Wi-Fi 后发现主机。\n\n"
        "数据目录：%APPDATA%\\Win-Pad Connect\n"
        "卸载：开始菜单 → Win-Pad Connect → 卸载，或设置 → 应用。\n",
        encoding="utf-8",
    )


def make_icon() -> None:
    from PIL import Image, ImageDraw

    scale = 4
    size = 256 * scale
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = 56 * scale
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=(11, 18, 32, 255))
    # 细边框
    d.rounded_rectangle([2 * scale, 2 * scale, size - 2 * scale, size - 2 * scale],
                        radius=r, outline=(34, 50, 79, 255), width=2 * scale)
    # 连接点
    for cx, cy in ((104, 128), (152, 128)):
        d.ellipse([(cx - 9) * scale, (cy - 9) * scale, (cx + 9) * scale, (cy + 9) * scale],
                  fill=(61, 220, 151, 255))
    d.line([(104 * scale, 128 * scale), (152 * scale, 128 * scale)],
           fill=(61, 220, 151, 255), width=6 * scale)
    img = img.resize((256, 256), Image.LANCZOS)
    img.save(ICON, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def make_payload() -> None:
    if PAYLOAD.exists():
        PAYLOAD.unlink()
    if not (STAGE / "app").exists():
        raise SystemExit("先运行 python build/stage.py 生成 app")
    count = 0
    with zipfile.ZipFile(PAYLOAD, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(STAGE.rglob("*")):
            if p == PAYLOAD or p.is_dir():
                continue
            if p.name.lower().endswith((".pyc", ".zip")):
                continue
            z.write(p, p.relative_to(STAGE).as_posix())
            count += 1
    print(f"payload: {PAYLOAD} ({count} files, {PAYLOAD.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()
    STAGE.mkdir(parents=True, exist_ok=True)
    if args.zip:
        make_payload()
        return
    copy_app()
    make_icon()
    print(f"staged: {STAGE}")
    print(f"icon:   {ICON}")


if __name__ == "__main__":
    main()
