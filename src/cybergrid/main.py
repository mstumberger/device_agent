import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from cybergrid.helpers.logging import Logger

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
        self.config = None
        self.mqtt_client = None
        self._running = False
        self._tasks = []

    async def run(self) -> None:
        self.info("Initializing CyberGrid Device Agent")
        self._running = True

        # Create scheduled tasks here
        self._tasks.append(asyncio.create_task(self._heartbeat_task(interval=5)))

        try:
            # Wait until shutdown is requested
            while self._running:
                await asyncio.sleep(1)
        except Exception as e:
            self.error(f"Fatal error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def _heartbeat_task(self, interval: int = 5) -> None:
        while self._running:
            self.info("Heartbeat - agent is running")
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

        # TODO: Disconnect MQTT client when implemented
        # if self.mqtt_client:
        #     await self.mqtt_client.disconnect()

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
