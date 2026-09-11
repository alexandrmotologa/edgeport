"""Configuration loader and environment settings for EdgePort."""

import os
import tomllib
from pathlib import Path
from typing import Any


class Config:
    """Reads settings from CLI flags, environment variables, or config.toml."""

    CONFIG_FILE = Path.home() / ".edgeport" / "config.toml"

    DEFAULT_RELAY_URL = "ws://localhost:8000/ws/tunnel"
    DEFAULT_RELAY_DOMAIN = "localhost"
    DEFAULT_RELAY_PORT = 8000
    DEFAULT_WEB_PORT = 4040

    @classmethod
    def load(cls) -> dict[str, Any]:
        settings: dict[str, Any] = {
            "relay_url": os.getenv("EDGEPORT_RELAY", cls.DEFAULT_RELAY_URL),
            "relay_domain": os.getenv("EDGEPORT_DOMAIN", cls.DEFAULT_RELAY_DOMAIN),
            "relay_token": os.getenv("EDGEPORT_TOKEN"),
            "web_port": int(os.getenv("EDGEPORT_WEB_PORT", cls.DEFAULT_WEB_PORT)),
        }

        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "rb") as f:
                    file_data = tomllib.load(f)
                    for k, v in file_data.items():
                        if v is not None:
                            settings[k] = v
            except Exception:
                pass

        return settings
