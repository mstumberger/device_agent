import json
from abc import ABC
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Any


class Config(ABC):
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
    client_id: str = "cybergrid-device"


def _merge_dataclass(instance: Config, data: dict[str, Any]) -> None:
    """Merge dictionary values into a dataclass instance."""
    for key, value in data.items():
        if hasattr(instance, key):
            setattr(instance, key, value)


@dataclass
class Config:
    """Main configuration container."""
    device: DeviceConfig = field(default_factory=DeviceConfig)
    mqtt: MqttConfig = field(default_factory=MqttConfig)

    @classmethod
    def load(cls, device_json_path: Optional[Path] = None) -> "Config":
        config = cls()
        if device_json_path and device_json_path.exists():
            try:
                with open(device_json_path, "r") as f:
                    device_data = json.load(f)

                # Dynamically merge device settings
                _merge_dataclass(config.device, device_data)

            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {device_json_path}: {e}")

        # Generate client_id from device_id
        config.mqtt.client_id = f"cybergrid-{config.device.id}"

        return config

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)
