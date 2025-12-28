import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from cybergrid.cli import parse_args, setup_logging, validate_config_file, show_version
from cybergrid.config import ConfigManager
from cybergrid.mqtt.client import MQTTClientWrapper
from cybergrid.helpers.logging import Logger
from cybergrid.readings import FakeReadings


class DeviceAgent(Logger):
    def __init__(
        self,
        project_root: Path
    ):
        super().__init__()
        self.project_root = project_root
        self.config = ConfigManager(project_root)
        self.mqtt_client: Optional[MQTTClientWrapper] = None
        self._readings = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        """Run the device agent."""
        self.info("Initializing CyberGrid Device Agent")
        self.info(f"Device ID: {self.config.device.id}")
        self.info(f"Power Rating: {self.config.device.power}W")
        self.info(f"MQTT Broker: {self.config.mqtt.host}:{self.config.mqtt.port}")
        self.info(f"Poll Interval: {self.config.app.poll_interval}s")
        self.info(f"Heartbeat Interval: {self.config.app.heartbeat_interval}s")

        self._running = True

        # Config hot-reload
        self.config.on_change(self._on_config_changed)
        await self.config.watch_config()

        # Readings generator
        self._readings = FakeReadings(self.config)

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
        while self._running:
            if self.mqtt_client and self.mqtt_client.connected:
                measurement = await self._readings.get_reading()

                payload = {
                    "timestamp": measurement.timestamp,
                    "power": measurement.power
                }

                topic = f"device/{self.config.device.id}/state"
                await self.mqtt_client.publish(topic, json.dumps(payload), qos=0)

            await asyncio.sleep(self.config.app.poll_interval)

    def _on_config_changed(self, changes: Dict[str, Any]) -> None:
        """Handle config.yaml changes."""
        if not changes:
            return

        if any(k in changes for k in ('host', 'port', 'username', 'password')) and self.mqtt_client:
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


async def main(argv: Optional[list[str]] = None) -> int:
    """Entry point."""
    args = parse_args(argv)

    if args.version:
        show_version()
        return 0

    # # Require 'run' command
    if args.command != "run":
        print("Error: No command specified. Use 'run' to start the agent.", file=sys.stderr)
        print("Use 'cybergrid-agent --help' for usage information.", file=sys.stderr)
        return 1

    setup_logging(args.log_level, args.log_format)

    # Validate configuration file exists
    config_path = validate_config_file(args.config)

    # Determine project root (config file's parent directory)
    project_root = config_path.parent

    # Create and run agent
    agent = DeviceAgent(project_root)

    # Setup signal handlers for graceful shutdown
    def signal_handler() -> None:
        agent._shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        await agent.run()
        return 0
    except KeyboardInterrupt:
        agent.info("Shutdown requested via SIGINT")
        await agent.shutdown()
        return 0
    except Exception as e:
        logging.error(f"Unhandled exception: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys_exit = asyncio.run(main(["run", "--log-level", "DEBUG"]))
    raise SystemExit(sys_exit)
