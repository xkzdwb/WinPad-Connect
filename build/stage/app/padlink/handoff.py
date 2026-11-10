"""平板端接入服务：HTTP 下发 profile + UDP 局域网发现。

设计约束：
* 只监听 GET，只读，不接受任何上传
* 配对码可选；开启时所有 profile / 测速请求都要带 ``code``
* 不碰 Sunshine 的 47989/47990 端口，避免和基线抢端口
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .version import APP_VERSION, PROTOCOL_VERSION

DISCOVERY_PORT = 47801
DISCOVERY_QUERY = b"PADLINK?1"
CHUNK = 64 * 1024
CHUNK_CACHE = os.urandom(CHUNK)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"Win-Pad Connect/{APP_VERSION}"
    sys_version = ""
    timeout = 20

    # 默认实现会把每条请求写到 stderr，这里交给控制器统一记录
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return

    # -- 工具 -------------------------------------------------------------

    @property
    def controller(self):
        return self.server.controller  # type: ignore[attr-defined]

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(body, "application/json; charset=utf-8", status)

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else "?"

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        if not self.controller.code_required:
            return True
        supplied = (query.get("code") or [""])[0] or self.headers.get("X-Win-Pad Connect-Code", "")
        return self.controller.authorize(supplied)

    # -- 路由 -------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        self.controller.note_request(self._client_ip(), path)

        if path == "/":
            self._send(self._index_html(), "text/html; charset=utf-8")
            return
        if path == "/padlink/ping":
            self._json(self.controller.ping_payload())
            return
        if path == "/padlink/health":
            self._json(self.controller.health_payload())
            return
        if path == "/padlink/profile.json":
            if not self._authorized(query):
                self._json({"error": "pairing_code_required", "message": "需要 6 位配对码"}, 401)
                return
            self._json(self.controller.profile())
            return
        if path == "/padlink/download":
            if not self._authorized(query):
                self._json({"error": "pairing_code_required", "message": "需要 6 位配对码"}, 401)
                return
            self._download(query)
            return
        self._json({"error": "not_found", "path": path}, 404)

    def _download(self, query: dict[str, list[str]]) -> None:
        try:
            megabytes = int((query.get("mb") or ["4"])[0])
        except ValueError:
            megabytes = 4
        megabytes = max(1, min(64, megabytes))
        total = megabytes * 1024 * 1024
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(total))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            remaining = total
            while remaining > 0:
                piece = CHUNK_CACHE[: min(CHUNK, remaining)]
                self.wfile.write(piece)
                remaining -= len(piece)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _index_html(self) -> bytes:
        name = self.controller.host_name
        html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Win-Pad Connect</title>
<style>
 body{{margin:0;background:#080f1a;color:#e8eff9;font:15px/1.7 "Segoe UI","Microsoft YaHei",sans-serif}}
 main{{max-width:640px;margin:8vh auto;padding:32px;background:#101b2d;border:1px solid #1e2e47;border-radius:18px}}
 h1{{margin:0 0 6px;font-size:26px}} .muted{{color:#9fb0c7}} code{{background:#0b1424;padding:2px 6px;border-radius:6px}}
 .ok{{color:#3ddc97}} a{{color:#4cc2ff}}
</style></head><body><main>
<h1>Win-Pad Connect</h1>
<p class="muted">Windows 基线装配台 · v{APP_VERSION} · 协议 v{PROTOCOL_VERSION}</p>
<p>主机：<b>{name}</b>　服务：<span class="ok">运行中</span></p>
<p>平板端请在同一局域网内打开 Win-Pad Connect Pad，或手动填写本机地址与此端口。</p>
<p>接口：<code>/padlink/ping</code> · <code>/padlink/profile.json?code=******</code> · <code>/padlink/download?mb=4</code></p>
</main></body></html>"""
        return html.encode("utf-8")


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, controller):
        self.controller = controller
        super().__init__(address, handler)


class HandoffService:
    """HTTP + UDP 服务。所有回调都在调用方给的函数里取实时状态。"""

    def __init__(self, profile_provider, code_provider, event_sink=None, code_required_provider=None):
        self._profile_provider = profile_provider
        self._code_provider = code_provider
        self._code_required_provider = code_required_provider
        self._event = event_sink or (lambda level, text: None)
        self._httpd: _Server | None = None
        self._thread: threading.Thread | None = None
        self._udp_thread: threading.Thread | None = None
        self._udp_stop = threading.Event()
        self._lock = threading.Lock()
        self.port = 47800
        self.host_name = socket.gethostname()
        self.last_client: dict | None = None
        self.request_count = 0
        self.discovery_count = 0
        self.started_at = 0.0
        self.error = ""

    # -- 状态 -------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def set_event_sink(self, sink) -> None:
        self._event = sink or (lambda level, text: None)

    @property
    def code_required(self) -> bool:
        if self._code_required_provider is not None:
            return bool(self._code_required_provider())
        return bool(self._code_provider())

    def authorize(self, supplied: str) -> bool:
        expected = self._code_provider()
        if not expected:
            return True
        return supplied.strip() == expected

    # -- 生命周期 ---------------------------------------------------------

    def start(self, port: int) -> tuple[bool, str]:
        if self.running:
            return True, "接入服务已在运行"
        port = int(port)
        try:
            httpd = _Server(("0.0.0.0", port), _Handler, self)
        except OSError as exc:
            self.error = str(exc)
            return False, f"端口 {port} 无法监听：{exc}"
        self._httpd = httpd
        self.port = port
        self.error = ""
        self.started_at = time.time()
        self._thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.2},
            name="padlink-http", daemon=True,
        )
        self._thread.start()
        self._start_discovery()
        self._event("info", f"平板接入服务已启动：0.0.0.0:{port}")
        return True, f"已监听 0.0.0.0:{port}"

    def stop(self) -> tuple[bool, str]:
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._stop_discovery()
        self._event("info", "平板接入服务已停止")
        return True, "已停止"

    # -- UDP 发现 ---------------------------------------------------------

    def _start_discovery(self) -> None:
        self._udp_stop.clear()
        self._udp_thread = threading.Thread(target=self._udp_loop, name="padlink-udp", daemon=True)
        self._udp_thread.start()

    def _stop_discovery(self) -> None:
        self._udp_stop.set()
        if self._udp_thread is not None:
            self._udp_thread.join(timeout=1.5)
            self._udp_thread = None

    def _udp_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(0.4)
        except OSError as exc:
            self._event("warn", f"UDP 发现端口 {DISCOVERY_PORT} 不可用：{exc}")
            sock.close()
            return
        while not self._udp_stop.is_set():
            try:
                data, addr = sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            if data.strip() != DISCOVERY_QUERY:
                continue
            payload = self.discovery_payload()
            try:
                sock.sendto(json.dumps(payload, ensure_ascii=False).encode("utf-8"), addr)
                self.discovery_count += 1
            except OSError:
                continue
        sock.close()

    # -- 载荷 -------------------------------------------------------------

    def discovery_payload(self) -> dict:
        return {
            "service": "padlink",
            "protocol": PROTOCOL_VERSION,
            "app": f"Win-Pad Connect {APP_VERSION}",
            "name": self.host_name,
            "port": self.port,
            "code_required": self.code_required,
            "ips": self._local_ips(),
        }

    def ping_payload(self) -> dict:
        return {
            "service": "padlink",
            "protocol": PROTOCOL_VERSION,
            "time": int(time.time()),
            "name": self.host_name,
            "port": self.port,
            "code_required": self.code_required,
            "app": f"Win-Pad Connect {APP_VERSION}",
        }

    def health_payload(self) -> dict:
        payload = self.ping_payload()
        payload["uptime_s"] = int(time.time() - self.started_at) if self.started_at else 0
        payload["requests"] = self.request_count
        payload["discoveries"] = self.discovery_count
        return payload

    def profile(self) -> dict:
        return self._profile_provider()

    def _local_ips(self) -> list[str]:
        from .platform_windows import get_ipv4_addresses

        return get_ipv4_addresses()

    def note_request(self, ip: str, path: str) -> None:
        with self._lock:
            self.request_count += 1
            self.last_client = {"ip": ip, "path": path, "time": time.time()}
        if path.startswith("/padlink/"):
            self._event("client", f"{ip} → {path}")
