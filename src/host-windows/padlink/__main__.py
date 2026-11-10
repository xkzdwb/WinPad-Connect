"""命令行入口：``python -m padlink`` 打开窗口，``--smoke-test`` 跑无界面自检。"""

from __future__ import annotations

import argparse
import json
import sys


def smoke_test(port: int | None = None, pairing: bool | None = None) -> int:
    from . import checks, profile
    from .handoff import HandoffService
    from .settings import Settings
    from .snapshot import collect
    from .version import APP_NAME, APP_VERSION, PROTOCOL_VERSION

    settings = Settings.load()
    if port:
        settings.port = port
    if pairing is not None:
        settings.pairing_enabled = pairing
    settings.normalize()

    service = HandoffService(
        profile_provider=lambda: profile.build(snapshot, service, result, score),
        code_provider=lambda: settings.pairing_code,
    )
    snapshot = collect(settings.sunshine_path or None)
    result, score = checks.evaluate(snapshot, service)
    payload = profile.build(snapshot, service, result, score)

    print(f"{APP_NAME} {APP_VERSION} 协议 v{PROTOCOL_VERSION}")
    print(f"主机      : {snapshot.os.hostname}  {snapshot.os.name} build {snapshot.os.build}")
    print(f"显卡      : {' / '.join(g['name'] for g in snapshot.gpus) or '未识别'}")
    print(f"编码器    : {snapshot.encoder_label}")
    print(f"虚拟显示器: {snapshot.vdd_kind or '未检测到'}")
    print(f"局域网    : {', '.join(snapshot.lan_ips()) or '未发现'}")
    print(f"Tailscale : {snapshot.tailscale.link}")
    print(f"体检得分  : {score}/100")
    for check in result:
        print(f"  [{check.status:7}] {check.title}: {check.detail}")
    print(f"profile   : {len(json.dumps(payload, ensure_ascii=False))} 字符, "
          f"{len(payload.get('client', {}).get('tiers', []))} 个档位")
    print("自检完成：探测、体检、协议构造均未抛异常。")
    return 0


def _setup_console() -> None:
    """让中文在 Windows 控制台与重定向管道里都按 UTF-8 输出。"""
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="padlink", description="PadLink Host — Windows 主机端")
    parser.add_argument("--smoke-test", action="store_true", help="不打开窗口，跑一遍自检")
    parser.add_argument("--port", type=int, default=None, help="接入服务端口（默认 47800）")
    parser.add_argument("--no-pairing", action="store_true", help="关闭配对码")
    parser.add_argument("--version", action="store_true", help="打印版本")
    parser.add_argument("--exit-after", type=float, default=0,
                        help="运行若干秒后自动退出（截图验收用）")
    parser.add_argument("--page", default=None,
                        help="启动后直接打开某页（overview/service/sunshine/network/report/about，用于截图验收）")
    _setup_console()
    args = parser.parse_args(argv)

    from .version import APP_NAME, APP_VERSION, PROTOCOL_VERSION

    if args.version:
        print(f"{APP_NAME} {APP_VERSION} (protocol v{PROTOCOL_VERSION})")
        return 0
    if args.smoke_test:
        return smoke_test(args.port, False if args.no_pairing else None)
    if sys.platform != "win32":
        print("PadLink Host 仅支持 Windows。")
        return 1

    from .ui.app import App

    app = App()
    if args.port:
        app.settings.port = args.port
    if args.no_pairing:
        app.settings.pairing_enabled = False
    if args.page:
        app.after(500, lambda: app.show_page(args.page))
    if args.exit_after > 0:
        app.after(int(args.exit_after * 1000), app.destroy)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
