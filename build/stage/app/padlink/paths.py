"""运行期目录：配置、备份、报告、日志。

默认放在 ``%APPDATA%\\Win-Pad Connect``（便携版可用环境变量 ``PADLINK_DATA_DIR`` 覆盖）。
若用户配置目录因权限策略不可写，依次尝试 ``%LOCALAPPDATA%`` 和程序目录下的
``.winpad-data``，避免程序因为一个目录权限而完全无法启动。
"""

from __future__ import annotations

import os
from pathlib import Path

_cached: Path | None = None


def _candidates():
    override = os.environ.get("PADLINK_DATA_DIR")
    if override:
        yield Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        yield Path(appdata) / "Win-Pad Connect"
    local = os.environ.get("LOCALAPPDATA")
    if local:
        yield Path(local) / "Win-Pad Connect"
    yield Path(__file__).resolve().parent.parent / ".winpad-data"


def app_data_dir() -> Path:
    global _cached
    if _cached is not None:
        return _cached
    errors = []
    for candidate in _candidates():
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")
            continue
        _cached = candidate
        return candidate
    raise OSError("没有可写的数据目录：" + "; ".join(errors))


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def backups_dir() -> Path:
    path = app_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir() -> Path:
    path = app_data_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def documents_dir() -> Path:
    docs = Path.home() / "Documents" / "Win-Pad Connect"
    try:
        docs.mkdir(parents=True, exist_ok=True)
    except OSError:
        docs = app_data_dir()
    return docs
