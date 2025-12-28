import random
from datetime import datetime, timezone

from cybergrid.readings.base import ReadingsSource, Measurement
from cybergrid.config import ConfigManager


class FakeReadings(ReadingsSource):
    """Generates fake power measurements with configurable variation."""

    def __init__(self, config: ConfigManager) -> None:
        self._config = config

    async def get_reading(self) -> Measurement:
        """Generate a simulated power measurement."""
        base_power = self._config.device.power

        # Check if faker is enabled
        if not self._config.readings.faker.enabled:
            # Return exact base power when disabled
            simulated_power = float(base_power)
        else:
            # Apply configured variation when enabled
            variation = random.uniform(-self._config.readings.faker.variation, self._config.readings.faker.variation)
            simulated_power = base_power * (1 + variation)

        return Measurement(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            power=round(simulated_power, 1)
        )