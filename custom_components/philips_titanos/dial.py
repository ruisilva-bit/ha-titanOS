"""Optional local DIAL app launch using documented Titan OS registrations.

Independent implementation from protocol observations in the reference projects.
A registered/running DIAL app is not proof of the foreground app or screen power.
"""

import asyncio
import xml.etree.ElementTree as ET

import aiohttp

from .api import ApiError, CannotConnect, TitanOSError

APPS = {
    "YouTube": "https://www.youtube.com",
    "Netflix": "https://www.netflix.com",
    "AmazonInstantVideo": None,
}


class DialClient:
    """No pairing or cloud calls; always address the configured local TV."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        """Initialize."""
        self.session = session
        self.base = f"http://{host}:56789/apps/"

    async def _request(self, method: str, app: str) -> tuple[int, bytes]:
        if app not in APPS:
            raise TitanOSError("Unknown DIAL application")
        origin = APPS[app]
        try:
            async with self.session.request(
                method,
                self.base + app,
                headers={"Origin": origin} if origin else {},
                timeout=aiohttp.ClientTimeout(total=5),
                allow_redirects=False,
            ) as response:
                body = await response.content.read(65537)
                if len(body) > 65536:
                    raise TitanOSError("DIAL response too large")
                if response.status not in (200, 201, 202):
                    raise ApiError(method, "/apps/" + app, response.status)
                return response.status, body
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise CannotConnect("DIAL connection failed") from err

    async def get_state(self, app: str) -> str | None:
        """Read DIAL state only; no assumption that the app is in the foreground."""
        _, body = await self._request("GET", app)
        try:
            if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
                raise ValueError
            root = ET.fromstring(body)
        except (ET.ParseError, ValueError) as err:
            raise TitanOSError("Invalid DIAL response") from err
        state = next(
            (e.text for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "state"),
            None,
        )
        return state if state in ("running", "stopped") else None

    async def discover(self) -> list[str]:
        """List only supported, responsive registrations; no launch attempts."""
        apps = []
        for app in APPS:
            try:
                if await self.get_state(app) is not None:
                    apps.append(app)
            except TitanOSError:
                pass
            await asyncio.sleep(0.2)
        return apps

    async def launch(self, app: str) -> None:
        """Send exactly one POST. An acknowledgement is not proof of execution."""
        await self._request("POST", app)
