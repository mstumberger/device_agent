import asyncio
import json
import logging
import signal
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict

from cybergrid.helpers.logging import Logger
from cybergrid.mqtt.client import MQTTClientWrapper
from cybergrid.config import ConfigManager

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class DeviceAgent(Logger):
    def __init__(
        self,
        project_root: Optional[Path] = None
    ):
        super().__init__()
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent

        self.config = ConfigManager(project_root)
        self.mqtt_client: Optional[MQTTClientWrapper] = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        """Run the device agent."""
        self.info("Initializing CyberGrid Device Agent")
        self.info(f"Device ID: {self.config.device.id}, Power: {self.config.device.power}W")
        self._running = True

        # Config hot-reload
        self.config.on_change(self._on_config_changed)
        await self.config.watch_config()

        # MQTT connection with retry
        self.mqtt_client = MQTTClientWrapper(self.config)
        self._tasks.append(asyncio.create_task(self.mqtt_client.start(), name="mqtt_connection"))

        # Start background tasks
        self._tasks.append(asyncio.create_task(self._heartbeat_task(), name="heartbeat"))
        self._tasks.append(asyncio.create_task(self._measurement_task(), name="measurement"))

        try:
            await self._shutdown_event.wait()
        except Exception as e:
            self.error(f"Fatal error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def _heartbeat_task(self) -> None:
        """Send heartbeat at configured interval."""
        while self._running:
            if self.mqtt_client and self.mqtt_client.connected:
                await self.mqtt_client.publish_status("online")
            await asyncio.sleep(self.config.app.heartbeat_interval)

    async def _measurement_task(self) -> None:
        """Generate and publish power measurements."""

        base_power = self.config.device.power

        while self._running:
            if self.mqtt_client and self.mqtt_client.connected:
                # Vary power by ±5%
                variation = random.uniform(-0.05, 0.05)
                simulated_power = base_power * (1 + variation)

                measurement = {
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "power": round(simulated_power, 1)
                }

                topic = f"device/{self.config.device.id}/measurement"
                await self.mqtt_client.publish(topic, json.dumps(measurement), qos=0)

            await asyncio.sleep(self.config.app.poll_interval)

    def _on_config_changed(self, changes: Dict[str, Any]) -> None:
        """Handle config.yaml changes."""
        if not changes:
            return

        if any(k in changes for k in ('host', 'port')) and self.mqtt_client:
            self.info("MQTT settings changed, reconnecting...")
            asyncio.create_task(self._reconnect_mqtt())

    async def _reconnect_mqtt(self) -> None:
        """Reconnect MQTT with new settings."""
        if self.mqtt_client:
            await self.mqtt_client.reconnect()

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent."""
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()
        self.info("Shutting down")

        # Stop config watcher
        await self.config.stop()

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Disconnect MQTT client
        if self.mqtt_client:
            await self.mqtt_client.disconnect()

        self.info("Shutdown complete")


async def main() -> None:
    """Entry point."""
    agent = DeviceAgent()

    def signal_handler() -> None:
        agent._shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        await agent.run()
    except KeyboardInterrupt:
        agent.info("Shutdown requested...")
        await agent.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
