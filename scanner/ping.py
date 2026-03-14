import asyncio
from dataclasses import dataclass

from mcstatus import JavaServer


@dataclass
class PingResult:
    is_online: bool
    latency_ms: float | None = None
    players_online: int | None = None
    players_max: int | None = None
    version_name: str | None = None
    version_protocol: int | None = None
    motd: str | None = None
    error_message: str | None = None


async def ping_server(host: str, port: int, timeout: float = 5.0) -> PingResult:
    """Ping a Minecraft server using the SLP protocol."""
    try:
        server = JavaServer(host, port, timeout=timeout)
        status = await asyncio.wait_for(
            server.async_status(tries=1),
            timeout=timeout + 1.0,
        )
        return PingResult(
            is_online=True,
            latency_ms=status.latency,
            players_online=status.players.online,
            players_max=status.players.max,
            version_name=status.version.name,
            version_protocol=status.version.protocol,
            motd=status.motd.to_plain(),
        )
    except asyncio.TimeoutError:
        return PingResult(is_online=False, error_message="timeout")
    except ConnectionRefusedError:
        return PingResult(is_online=False, error_message="connection_refused")
    except OSError as e:
        return PingResult(is_online=False, error_message=f"os_error: {e}")
    except Exception as e:
        return PingResult(is_online=False, error_message=f"{type(e).__name__}: {e}")
