"""离线回归测试：不依赖 Sunshine / Tailscale / 管理员权限。

运行：在 host-windows 目录执行 ``python -m unittest discover -s tests -v``
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 测试不写用户配置目录：覆盖数据目录，避免污染真实设置
os.environ["PADLINK_DATA_DIR"] = str(
    (Path(__file__).resolve().parent / ".tmp" / "data").resolve()
)

from padlink import checks, handoff, profile, sunshine, tailscale  # noqa: E402
from padlink import platform_windows as win  # noqa: E402
from padlink.settings import Settings, new_pairing_code  # noqa: E402
from padlink.snapshot import Snapshot  # noqa: E402


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def temp_dir():
    """系统 %TEMP% 与 mkdtemp 的 0700 ACL 在部分沙箱里不可写，测试临时目录放在工程内。"""
    root = Path(__file__).resolve().parent / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case-{uuid.uuid4().hex[:12]}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def fake_snapshot(**overrides) -> Snapshot:
    base = Snapshot(
        os=win.OsInfo(name="Windows 11", version="24H2", build=26100, hostname="TEST-PC"),
        cpu="Test CPU",
        ram_gb=32.0,
        gpus=[{"name": "NVIDIA GeForce RTX 5060 Laptop GPU", "vendor": "NVIDIA", "driver": "1"}],
        displays=[],
        ips=["192.168.1.20"],
        admin=True,
        sunshine=sunshine.SunshineState(installed=False),
        tailscale=tailscale.TailscaleState(),
        recommended_encoder="nvenc",
        generated_at=time.time(),
    )
    for key, value in overrides.items():
        base = replace(base, **{key: value})
    return base


class SunshineConfigTests(unittest.TestCase):
    def test_read_conf(self) -> None:
        with temp_dir() as tmp:
            path = Path(tmp) / "sunshine.conf"
            path.write_text(
                "# 注释\nencoder = software\nfps = 60\n\n[unrelated]\nkey = value\n",
                encoding="utf-8",
            )
            values, error = sunshine.read_conf(str(path))
            self.assertEqual(error, "")
            self.assertEqual(values["encoder"], "software")
            self.assertEqual(values["fps"], "60")
            self.assertEqual(values["key"], "value")

    def test_apply_profile_is_incremental_and_backs_up(self) -> None:
        with temp_dir() as tmp:
            path = Path(tmp) / "sunshine.conf"
            original = "# 用户注释\nencoder = software\nmin_log_level = info\n"
            path.write_text(original, encoding="utf-8")

            ok, message = sunshine.apply_profile(str(path), "nvenc")
            self.assertTrue(ok, message)

            text = path.read_text(encoding="utf-8")
            self.assertIn("# 用户注释", text)
            self.assertIn("encoder = nvenc", text)
            self.assertIn("nvenc_preset = p4", text)
            self.assertIn("min_log_level = info", text)
            self.assertEqual(text.count("encoder ="), 1)
            self.assertIn(sunshine.PADLINK_MARKER, text)

            backups = list(Path(tmp).glob("sunshine.conf.*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), original)

            ok, message = sunshine.restore_backup(str(path))
            self.assertTrue(ok, message)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_apply_profile_unknown_encoder(self) -> None:
        with temp_dir() as tmp:
            path = Path(tmp) / "sunshine.conf"
            path.write_text("a=1\n", encoding="utf-8")
            ok, message = sunshine.apply_profile(str(path), "voodoo")
            self.assertFalse(ok)
            self.assertIn("未知编码器", message)


class ChecksTests(unittest.TestCase):
    def test_not_installed_blocks_readiness(self) -> None:
        snapshot = fake_snapshot()
        result, score = checks.evaluate(snapshot, None)
        by_key = {item.key: item for item in result}
        self.assertEqual(by_key["install"].status, checks.STATUS_FAIL)
        self.assertLess(score, 70)

    def test_ready_baseline_scores_high(self) -> None:
        config = {
            "encoder": "nvenc",
            "nvenc_preset": "p4",
            "nvenc_tune": "ll",
            "nvenc_rc": "cbr",
            "nvenc_realtime_hags": "enabled",
        }
        state = sunshine.SunshineState(
            installed=True, root=r"C:\Program Files\Sunshine",
            conf=r"C:\Program Files\Sunshine\config\sunshine.conf",
            running=True, web_https=True, config=config,
        )
        display = win.DisplayInfo(
            device=r"\\.\DISPLAY2", adapter="ZakoVDD", monitor="Zako Virtual Display",
            width=3392, height=2400, refresh=60, virtual=True,
            modes=[(3392, 2400, 60)],
        )
        ts = tailscale.TailscaleState(
            installed=True, backend="Running", ips=["100.100.1.2"],
            peers_direct=1, peers_relay=0,
        )
        snapshot = fake_snapshot(
            sunshine=state, displays=[display], tailscale=ts, firewall_rule=True,
        )

        class Service:
            running = True
            port = 47800

        result, score = checks.evaluate(snapshot, Service())
        self.assertGreaterEqual(score, 90, [(c.key, c.status) for c in result])
        self.assertTrue(snapshot.supports_pad_native)
        self.assertEqual(snapshot.vdd_kind, "ZakoVDD")

    def test_relay_network_is_warned(self) -> None:
        ts = tailscale.TailscaleState(
            installed=True, backend="Running", ips=["100.100.1.2"],
            peers_direct=0, peers_relay=1,
        )
        snapshot = fake_snapshot(tailscale=ts)
        result, _ = checks.evaluate(snapshot, None)
        network = next(item for item in result if item.key == "network")
        self.assertEqual(network.status, checks.STATUS_WARN)
        self.assertIn("中继", network.detail)


class ProfileTests(unittest.TestCase):
    def test_profile_is_json_serializable_and_complete(self) -> None:
        snapshot = fake_snapshot()
        result, score = checks.evaluate(snapshot, None)

        class Service:
            running = False
            port = 47800
            code_required = True

        payload = profile.build(snapshot, Service(), result, score)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertIn("padlink", encoded)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["protocol"], 1)
        self.assertEqual(decoded["service_info"]["port"], 47800)
        self.assertEqual(len(decoded["client"]["tiers"]), 3)
        self.assertTrue(decoded["code_required"])


class HandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.code = "123456"
        snapshot = fake_snapshot()
        result, score = checks.evaluate(snapshot, None)

        class Service:
            running = True
            port = 0
            code_required = True

        self.service = handoff.HandoffService(
            profile_provider=lambda: profile.build(snapshot, Service(), result, score),
            code_provider=lambda: self.code,
        )
        self.port = free_port()
        ok, message = self.service.start(self.port)
        self.assertTrue(ok, message)
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.service.stop()

    def get(self, path: str) -> tuple[int, bytes]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read()
            finally:
                exc.close()

    def test_ping_needs_no_code(self) -> None:
        status, body = self.get("/padlink/ping")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["service"], "padlink")
        self.assertTrue(payload["code_required"])

    def test_profile_rejects_wrong_code(self) -> None:
        status, body = self.get("/padlink/profile.json?code=000000")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["error"], "pairing_code_required")

    def test_profile_with_code(self) -> None:
        status, body = self.get(f"/padlink/profile.json?code={self.code}")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["host"]["name"], "TEST-PC")
        self.assertGreaterEqual(len(payload["readiness"]["checks"]), 8)

    def test_download_size(self) -> None:
        status, body = self.get(f"/padlink/download?mb=2&code={self.code}")
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 2 * 1024 * 1024)

    def test_unknown_route(self) -> None:
        status, body = self.get("/nope")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "not_found")

    def test_request_tracking(self) -> None:
        self.get("/padlink/ping")
        self.assertIsNotNone(self.service.last_client)
        self.assertGreaterEqual(self.service.request_count, 1)


class SettingsTests(unittest.TestCase):
    def test_code_normalization(self) -> None:
        settings = Settings(pairing_code="")
        settings.normalize()
        self.assertEqual(len(settings.pairing_code), 6)
        self.assertTrue(settings.pairing_code.isdigit())
        self.assertNotEqual(new_pairing_code(), "")

    def test_port_normalization(self) -> None:
        settings = Settings(port=80)
        settings.normalize()
        self.assertEqual(settings.port, 47800)


class PlatformTests(unittest.TestCase):
    def test_os_info(self) -> None:
        info = win.get_os_info()
        self.assertTrue(info.name)
        self.assertGreater(info.build, 0)
        self.assertIn("Windows", info.display)

    def test_gpu_and_encoder(self) -> None:
        gpus = win.get_gpus()
        self.assertIsInstance(gpus, list)
        self.assertIn(win.pick_encoder(gpus), {"nvenc", "qsv", "amdvce", "software"})

    def test_displays(self) -> None:
        displays = win.get_displays(include_modes=False)
        self.assertIsInstance(displays, list)
        for display in displays:
            self.assertTrue(display.device)

    def test_port_probe(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            self.assertTrue(win.port_open("127.0.0.1", port, 0.5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
