"""本机设置（%APPDATA%\\Win-Pad Connect\\settings.json）。"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, fields

from .paths import settings_file


def new_pairing_code() -> str:
    return str(secrets.randbelow(900000) + 100000)


@dataclass
class Settings:
    port: int = 47800
    pairing_code: str = ""
    pairing_enabled: bool = True
    sunshine_path: str = ""
    last_client_ip: str = ""
    start_service_on_launch: bool = True
    last_page: str = "overview"
    geometry: str = ""

    def normalize(self) -> None:
        if not self.pairing_code or not self.pairing_code.isdigit() or len(self.pairing_code) != 6:
            self.pairing_code = new_pairing_code()
        if not (1024 <= int(self.port or 0) <= 65535):
            self.port = 47800
        self.port = int(self.port)

    @classmethod
    def load(cls) -> "Settings":
        path = settings_file()
        data: dict = {}
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        valid = {field.name for field in fields(cls)}
        settings = cls(**{key: value for key, value in data.items() if key in valid})
        settings.normalize()
        return settings

    def save(self) -> None:
        try:
            settings_file().write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass
