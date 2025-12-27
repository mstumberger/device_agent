import asyncio
import json
from typing import Optional, Callable, Dict, Any, TYPE_CHECKING

from aiomqtt import Client, Will

from cybergrid.helpers.logging import Logger

if TYPE_CHECKING:
    from cybergrid.config import Config


class MQTTClientWrapper(Logger):

    def __init__(
        self,
        config: "Config"
    ):
        super().__init__()
        self.config = config

        # MQTT client instance (None until we connect)
        self._client: Optional[Client] = None

        # Connection state tracking
        self._connected = False
        self._should_reconnect = True  # Set to False to stop reconnection loop

        # Subscription registry: topic -> callback function
        # We store these to re-subscribe after reconnection
        self._subscriptions: Dict[str, Callable[[str], None]] = {}

        # Background task that listens for incoming messages
        self._subscription_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Connect to MQTT broker with LWT configured."""
        mqtt = self.config.mqtt
        device_id = self.config.device.id

        self.info(f"Connecting to MQTT broker at {mqtt.host}:{mqtt.port}")

        lwt_topic = f"device/{device_id}/status"
        lwt_payload = json.dumps({"status": "offline"})

        # Create Last Will Testament
        will = Will(
            topic=lwt_topic,
            payload=lwt_payload,
            qos=1,
            retain=True
        )

        self._client = Client(
            hostname=mqtt.host,
            port=mqtt.port,
            identifier=mqtt.client_id,
            will=will
        )

        try:
            await self._client.__aenter__()
            self._connected = True
            self.info("Connected to MQTT broker")

            # Publish online status
            await self.publish_status("online")
        except Exception as e:
            self.error(f"Failed to connect to MQTT broker: {e}", exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._should_reconnect = False

        if self._client and self._connected:
            # Publish offline status before disconnecting
            await self.publish_status("offline")

            self.info("Disconnecting from MQTT broker")
            await self._client.__aexit__(None, None, None)
            self._connected = False
            self.info("Disconnected from MQTT broker")

    async def publish_status(self, status: str) -> None:
        """Publish device status to the status topic."""
        device_id = self.config.device.id
        topic = f"device/{device_id}/status"
        payload = json.dumps({"status": status})
        await self.publish(topic, payload, qos=1, retain=True)

    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> None:
        """Publish a message to a topic."""
        if not self._connected:
            self.warning(f"Not connected, cannot publish to {topic}")
            return

        try:
            await self._client.publish(topic, payload, qos=qos, retain=retain)
            self.debug(f"Published to {topic}: {payload}")
        except Exception as e:
            self.error(f"Failed to publish to {topic}: {e}", exc_info=True)

    @property
    def connected(self) -> bool:
        """Check if currently connected to the broker."""
        return self._connected

