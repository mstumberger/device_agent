"""Abstract base class for readings sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Measurement:
    """A single measurement reading."""
    timestamp: str
    power: float


class ReadingsSource(ABC):
    """Abstract interface for reading power measurements."""

    @abstractmethod
    async def get_reading(self) -> Measurement:
        """Get a single power measurement.

        Returns:
            A Measurement with timestamp and power value.
        """
        ...