from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_path: Path = Path("/data/mc_scanner.db")

    # Scanning
    scan_interval_minutes: int = 12
    scan_concurrency: int = 150
    scan_timeout_seconds: float = 10.0

    # Scraping
    scrape_interval_hours: int = 24
    target_countries: list[str] = [
        "NL", "DE", "BE", "GB", "FR",         # current
        "PL", "SE", "NO", "DK", "FI",         # nordics + poland
        "ES", "PT", "IT", "AT", "CH",         # south/central
        "CZ", "RO", "HU", "IE", "LU",         # central/east + ireland
        "SK", "BG", "HR", "LT", "LV", "EE",  # baltics + balkans
    ]
    primary_countries: list[str] = ["NL"]

    # Scoring
    scoring_window_hours: int = 168  # 7 days
    min_scans_for_scoring: int = 20

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    # Rate limiting
    max_pings_per_second: float = 100.0

    model_config = {"env_prefix": "MCS_", "env_file": ".env"}
