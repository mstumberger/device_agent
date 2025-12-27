import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cybergrid.helpers.logging import Logger
from cybergrid.mqtt.client import MQTTClientWrapper
from cybergrid.config import Config

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class DeviceAgent(Logger):
    def __init__(
        self,
        config_path: Optional[Path] = None,
    ):
        super().__init__()
        self.config = self._load_config(config_path)
        self.mqtt_client: Optional[MQTTClientWrapper] = None
        self._running = False
        self._tasks = []

    def _load_config(self, device_json_path: Optional[Path] = None) -> Config:
        if device_json_path is None:
            # Default to device.json in project root (../ from src/cybergrid/)
            project_root = Path(__file__).parent.parent.parent
            device_json_path = project_root / "device.json"

        if not device_json_path.exists():
            self.error(f"device.json not found at {device_json_path}")
            raise FileNotFoundError(f"device.json not found at {device_json_path}")

        try:
            return Config.load(device_json_path)
        except json.JSONDecodeError as e:
            self.error(f"device.json is malformed: {e}")
            raise
        except (KeyError, ValueError) as e:
            self.error(f"device.json missing required fields: {e}")
            raise ValueError(f"Invalid device.json: {e}")

    async def run(self) -> None:
        self.info("Initializing CyberGrid Device Agent")
        self.info(f"Device ID: {self.config.device.id}, Power: {self.config.device.power}W")
        self._running = True

        # Initialize MQTT client
        self.mqtt_client = MQTTClientWrapper(self.config)
        await self.mqtt_client.connect()

        # Create scheduled tasks
        self._tasks.append(asyncio.create_task(self._heartbeat_task(interval=30)))
        self._tasks.append(asyncio.create_task(self._measurement_task(interval=5)))

        try:
            # Wait until shutdown is requested
            while self._running:
                await asyncio.sleep(1)
        except Exception as e:
            self.error(f"Fatal error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def _heartbeat_task(self, interval: int = 30) -> None:
        """Send heartbeat (online status) every 30 seconds."""
        while self._running:
            if self.mqtt_client and self.mqtt_client.connected:
                await self.mqtt_client.publish_status("online")
            await asyncio.sleep(interval)

    async def _measurement_task(self, interval: int = 5) -> None:
        """Generate and publish simulated power measurements every 5 seconds."""
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
                payload = json.dumps(measurement)
                await self.mqtt_client.publish(topic, payload, qos=0)

                self.info(f"Published measurement: {payload}")

            await asyncio.sleep(interval)

    async def shutdown(self) -> None:
        """Gracefully shutdown all tasks and disconnect."""
        if not self._running:
            return  # Already shutting down

        self._running = False
        self.info("Shutting down")

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
    try:
        await agent.run()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        await agent.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
