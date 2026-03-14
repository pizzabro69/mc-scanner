from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DiscoveredServer:
    host: str
    port: int = 25565
    country_code: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None


class BaseScraper(ABC):
    """Abstract base class for server list scrapers."""

    name: str = "base"

    @abstractmethod
    async def scrape(self, countries: list[str]) -> list[DiscoveredServer]:
        """Scrape server list and return discovered servers."""
        ...
