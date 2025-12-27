"""Configuration management with hot-reload support."""

import asyncio
import json
import logging
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any, Dict

import yaml

from cybergrid.helpers.logging import Logger


class Config(ABC):
    """Base config class."""
    pass


@dataclass
class DeviceConfig(Config):
    """Device-specific configuration from device.json."""
    # Unique device identifier - should come from device hardware (e.g., MAC, serial number)
    # This uniquely identifies this physical device in the system
    id: str = "device-001"

    # Power rating in watts (for PV simulators, etc.)
    power: int = 0


@dataclass
class MqttConfig(Config):
    """MQTT broker connection configuration."""
    host: str = "localhost"
    port: int = 1883


@dataclass
class AppConfig(Config):
    """Application settings from config.yaml."""
    poll_interval: int = 5
    heartbeat_interval: int = 30


def _merge_dataclass(instance: Config, data: dict[str, Any]) -> dict[str, Any]:
    """Merge dict into dataclass, returning changed values."""
    changed = {}
    for key, value in data.items():
        if hasattr(instance, key):
            old_value = getattr(instance, key)
            if old_value != value:
                changed[key] = {"old": old_value, "new": value}
                setattr(instance, key, value)
    return changed


class ConfigManager(Logger):
    """Configuration manager with hot-reload support."""

    def __init__(self, project_root: Path) -> None:
        """Initialize configuration manager.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__()
        self.project_root = project_root
        self.device = DeviceConfig()
        self.mqtt = MqttConfig()
        self.app = AppConfig()

        self._config_path = project_root / "config.yaml"
        self._watchers: list[Callable[[Dict[str, Any]], None]] = []
        self._watch_task: asyncio.Task | None = None
        self.load_device_config()

    def load_device_config(self) -> None:
        """Load device.json (static, one-time load)."""
        device_json = self.project_root / "device.json"
        if not device_json.exists():
            raise FileNotFoundError(f"device.json not found at {device_json}")

        with open(device_json) as f:
            data = json.load(f)
        # Map device_id to id for config compatibility
        if "device_id" in data:
            data["id"] = data.pop("device_id")
        _merge_dataclass(self.device, data)

    async def watch_config(self) -> None:
        """Watch config.yaml for changes."""
        if self._config_path.exists():
            self._reload_config()
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def _watch_loop(self) -> None:
        """Monitor config.yaml for changes."""
        last_mtime = 0
        if self._config_path.exists():
            last_mtime = self._config_path.stat().st_mtime

        while True:
            try:
                if self._config_path.exists():
                    mtime = self._config_path.stat().st_mtime
                    if mtime > last_mtime:
                        last_mtime = mtime
                        changes = self._reload_config()
                        self._notify_changes(changes)
            except Exception:
                pass
            await asyncio.sleep(1)

    def _notify_changes(self, changes: Dict[str, Any]) -> None:
        """Notify watchers of config changes."""
        if not changes:
            self.info("Config reloaded: no changes detected")
            return

        parts = [f"{k}: {v['old']} → {v['new']}" for k, v in changes.items()]
        self.info(f"Config reloaded: {', '.join(parts)}")

        for cb in self._watchers:
            cb(changes)

    def _reload_config(self) -> dict[str, Config]:
        """Reload config.yaml, handling errors gracefully."""
        try:
            with open(self._config_path) as f:
                data = yaml.safe_load(f) or {}

            changes = {}
            if "mqtt" in data:
                changes.update(_merge_dataclass(self.mqtt, data["mqtt"]))
            if "app" in data:
                changes.update(_merge_dataclass(self.app, data["app"]))
            return changes
        except (yaml.YAMLError, IOError):
            return {}

    def on_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback for config changes."""
        self._watchers.append(callback)

    async def stop(self) -> None:
        """Stop watching config file."""
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
