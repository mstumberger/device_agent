"""MQTT client wrapper with LWT and connection retry support."""

import asyncio
import json
from typing import Optional

from aiomqtt import Client, Will, MqttError

from cybergrid.helpers.logging import Logger
from cybergrid.config import ConfigManager


class MQTTClientWrapper(Logger):
    """MQTT client wrapper with automatic reconnection and LWT."""

    def __init__(self, config: ConfigManager) -> None:
        """Initialize MQTT client wrapper."""
        super().__init__()
        self.config = config
        self._client: Optional[Client] = None
        self._connected = False
        self._reconnect_requested = False
        self._running = False

    async def start(self) -> None:
        """Start connection management (runs in background task)."""
        self._running = True
        while self._running:
            if not self._connected:
                await self._connect_with_retry()
            self._reconnect_requested = False
            await asyncio.sleep(1)

    async def _connect_with_retry(self) -> bool:
        """Connect with exponential backoff retry."""
        retry_count = 0
        backoff = 5

        while not self._connected and not self._reconnect_requested and self._running:
            try:
                await self._connect()
                return True
            except (OSError, MqttError) as e:
                retry_count += 1
                self.warning(f"Connection failed (attempt {retry_count}), retrying in {backoff}s: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
        return False

    async def _connect(self) -> None:
        """Connect to MQTT broker with LWT."""
        mqtt = self.config.mqtt
        device_id = self.config.device.id

        will = Will(
            topic=f"device/{device_id}/status",
            payload=json.dumps({"status": "offline"}),
            qos=1,
            retain=True
        )

        self._client = Client(
            hostname=mqtt.host,
            port=mqtt.port,
            identifier=device_id,
            will=will
        )

        await self._client.__aenter__()
        self._connected = True
        self.info(f"Connected to MQTT broker at {mqtt.host}:{mqtt.port}")
        await self.publish_status("online")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._running = False
        self._connected = False

        if self._client:
            try:
                await self.publish_status("offline")
            except Exception:
                pass
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass

    async def reconnect(self) -> None:
        """Trigger reconnection (for config changes)."""
        if self._client:
            try:
                await self.publish_status("offline")
            except Exception:
                pass
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass

        self._connected = False
        self._reconnect_requested = True

    async def publish_status(self, status: str) -> None:
        """Publish device status."""
        topic = f"device/{self.config.device.id}/status"
        await self.publish(topic, json.dumps({"status": status}), qos=1, retain=True)

    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> None:
        """Publish a message."""
        if not self._connected or not self._client:
            return

        self.debug(f"Publishing: {topic} | QoS={qos} | retain={retain} | payload={payload}")
        await self._client.publish(topic, payload, qos=qos, retain=retain)

    @property
    def connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected
