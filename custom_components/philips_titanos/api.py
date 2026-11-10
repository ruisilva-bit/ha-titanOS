# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Async client for the JointSpace v6 API of Philips Titan OS TVs.

Firmware may return stale values and the API may remain reachable in standby.
Neither HTTP success nor Cast reachability proves that the screen is on.
Power evidence is evaluated separately by the coordinator.
"""

import asyncio
import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import secrets
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)

PORT = 1926
CAST_PORT = 8009
DEFAULT_TIMEOUT = 10

# Philips' app secret: signs pairing grants and encrypts the /system fields.
_SHARED_KEY = base64.b64decode(
    "ZmVay1EQVFOaZhwQ4Kv81ypLAZNczV9sG4KkseXWn1NEk6cXmPKO/MCa9sryslvLCFMnNe4Z4CPXzToowvhHvA=="
)
_PAIRING_SCOPE = ["read", "write", "control"]


class TitanOSError(Exception):
    """Base class for errors talking to the TV."""


class CannotConnect(TitanOSError):
    """The TV is not reachable."""


class InvalidAuth(TitanOSError):
    """The TV rejected the stored credentials."""


class PairingError(TitanOSError):
    """Pairing was refused, e.g. because of a wrong or expired PIN."""


class ApiError(TitanOSError):
    """The TV answered with an unexpected HTTP status."""

    def __init__(self, method: str, path: str, status: int) -> None:
        """Initialize the error."""
        super().__init__(f"{method} {path}: HTTP {status}")
        self.status = status


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """Device data from the unauthenticated /system endpoint."""

    name: str
    model: str | None
    serial_number: str | None
    software_version: str | None
    api_version: str
    featuring: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> SystemInfo:
        """Build from a /system response."""
        version = data.get("api_version", {})
        return cls(
            name=data.get("name", ""),
            model=decrypt(data.get("model_encrypted")),
            serial_number=decrypt(data.get("serialnumber_encrypted")),
            software_version=decrypt(data.get("softwareversion_encrypted")),
            api_version=".".join(
                str(version.get(part, 0)) for part in ("Major", "Minor", "Patch")
            ),
            featuring=data.get("featuring", {}),
        )


@dataclass(frozen=True, slots=True)
class PairingSession:
    """State between pairing request and grant."""

    device_id: str
    auth_key: str
    timestamp: int
    timeout: int


def decrypt(value: str | None) -> str | None:
    """Decrypt an AES-CBC encrypted /system field."""
    if not value:
        return None
    raw = base64.b64decode(value)
    decryptor = Cipher(
        algorithms.AES(_SHARED_KEY[:16]), modes.CBC(raw[:16])
    ).decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    padded = decryptor.update(raw[16:]) + decryptor.finalize()
    return (unpadder.update(padded) + unpadder.finalize()).decode()


def find_menu_node(node: dict[str, Any], context: str) -> dict[str, Any] | None:
    """Return the settings menu node with this context."""
    if node.get("context") == context:
        return node
    for child in (node.get("data") or {}).get("nodes") or []:
        if (found := find_menu_node(child, context)) is not None:
            return found
    return None


def _device(device_id: str) -> dict[str, str]:
    return {
        "device_name": "Home Assistant",
        "device_os": "Home Assistant",
        "app_name": "Home Assistant",
        "app_id": "homeassistant",
        "type": "native",
        "id": device_id,
    }


class TitanOSClient:
    """JointSpace v6 client over HTTPS with digest authentication."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        device_id: str | None = None,
        auth_key: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.host = host
        self._base = f"https://{host}:{PORT}/6"
        self._request_lock = asyncio.Lock()
        self._last_request = 0.0
        self._auth: aiohttp.DigestAuthMiddleware | None = None
        if device_id and auth_key:
            self.set_credentials(device_id, auth_key)

    def set_credentials(self, device_id: str, auth_key: str) -> None:
        """Use these credentials for all further requests."""
        self._auth = aiohttp.DigestAuthMiddleware(device_id, auth_key)

    async def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        """Serialize requests; never retry a possibly executed write."""
        async with self._request_lock:
            loop = asyncio.get_running_loop()
            await asyncio.sleep(max(0, 0.7 - (loop.time() - self._last_request)))
            try:
                return await self._request_once(method, path, body, **kwargs)
            finally:
                self._last_request = loop.time()

    async def _request_once(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        auth: bool = True,
        request_timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        middlewares = (self._auth,) if auth and self._auth else ()
        try:
            async with self._session.request(
                method,
                self._base + path,
                json=body,
                # Self-signed certificate without SAN.
                ssl=False,
                allow_redirects=False,
                middlewares=middlewares,
                timeout=aiohttp.ClientTimeout(total=request_timeout),
            ) as resp:
                text = await resp.text()
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise CannotConnect(f"{method} {path}: connection failed") from err
        # Never log response bodies: pairing responses contain credentials.
        _LOGGER.debug("%s %s -> %s", method, path, resp.status)
        if resp.status == 401 and auth:
            raise InvalidAuth(f"{method} {path}")
        if resp.status != 200:
            raise ApiError(method, path, resp.status)
        text = text.strip()
        # Setters answer with an empty body, "Ok" or a tiny HTML page.
        if not text or text[0] not in "[{":
            if method == "GET" and path != "/ambilight/currentconfiguration":
                raise TitanOSError("Unexpected API response")
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # TPN256E sends malformed JSON for activities/tv.
            _LOGGER.debug("Ignoring malformed JSON from %s %s", method, path)
            raise TitanOSError("Malformed API JSON") from None

    async def get_system(self) -> dict[str, Any]:
        """Return the raw /system response, no credentials needed."""
        data = await self._request("GET", "/system", auth=False)
        if not isinstance(data, dict):
            raise TitanOSError("Invalid system response")
        return data

    async def pair_request(self, featuring: dict[str, Any]) -> PairingSession:
        """Make the TV show a PIN."""
        device_id = secrets.token_hex(8)
        data = await self._request(
            "POST",
            "/pair/request",
            {
                "access": {"scope": _PAIRING_SCOPE, "featuring": featuring},
                "device": _device(device_id),
            },
            auth=False,
        )
        if not isinstance(data, dict) or data.get("error_id") != "SUCCESS":
            raise PairingError("Pairing rejected")
        try:
            if not isinstance(data["auth_key"], str) or not data["auth_key"]:
                raise ValueError
            return PairingSession(
                device_id=device_id,
                auth_key=data["auth_key"],
                timestamp=int(data["timestamp"]),
                timeout=int(data.get("timeout", 30)),
            )
        except (KeyError, ValueError, TypeError) as err:
            raise PairingError("Invalid pairing response") from err

    async def pair_grant(self, pairing: PairingSession, pin: str) -> str:
        """Confirm the PIN and return the auth key to store."""
        signature = hmac.new(
            _SHARED_KEY, f"{pairing.timestamp}{pin}".encode(), hashlib.sha1
        ).digest()
        self.set_credentials(pairing.device_id, pairing.auth_key)
        try:
            data = await self._request(
                "POST",
                "/pair/grant",
                {
                    "auth": {
                        "pin": pin,
                        "auth_timestamp": pairing.timestamp,
                        "auth_signature": base64.b64encode(signature).decode(),
                        "auth_appId": "1",
                        "auth_key": pairing.auth_key,
                    },
                    "device": _device(pairing.device_id),
                },
            )
        except (InvalidAuth, ApiError) as err:
            self._auth = None
            raise PairingError("Pairing authentication failed") from err
        if not isinstance(data, dict) or data.get("error_id") != "SUCCESS":
            self._auth = None
            raise PairingError("Pairing rejected")
        auth_key = data.get("auth_key") or pairing.auth_key
        self.set_credentials(pairing.device_id, auth_key)
        return auth_key

    async def get_power_state(self) -> str | None:
        """Read JointSpace power; caller decides whether it is trustworthy."""
        data = await self._request("GET", "/powerstate")
        if isinstance(data, dict) and isinstance(data.get("powerstate"), str):
            return data["powerstate"].casefold()
        return None

    async def is_on(self) -> bool:
        """Legacy Cast probe, not a screen-state signal; unused by this integration."""
        try:
            async with asyncio.timeout(2):
                _, writer = await asyncio.open_connection(self.host, CAST_PORT)
        except OSError, TimeoutError:
            return False
        writer.close()
        return True

    async def get_network_devices(self) -> list[dict[str, Any]]:
        """Return the network interfaces including MAC and WoL state."""
        data = await self._request("GET", "/network/devices")
        if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
            raise TitanOSError("Invalid network devices response")
        return data

    async def get_current_activity(self) -> str | None:
        """Return "watchtv", "extension" (HDMI) or "browser" (home screen)."""
        data = await self._request("GET", "/activities/current")
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            raise TitanOSError("Invalid activity response")
        return data["id"]

    async def is_muted(self) -> bool | None:
        """Return whether the TV is muted.

        The volume the same endpoint reports does not follow the remote.
        """
        data = await self._request("GET", "/audio/volume")
        if isinstance(data, dict) and isinstance(data.get("muted"), bool):
            return data["muted"]
        return None

    async def send_key(self, key: str) -> None:
        """Send a remote control key."""
        result = await self._request("POST", "/input/key", {"key": key})
        if isinstance(result, dict) and (
            "error" in result or result.get("error_id", "SUCCESS") != "SUCCESS"
        ):
            raise TitanOSError("Remote key rejected by API")

    async def get_ambilight_styles(self) -> list[dict[str, Any]]:
        """Return the supported styles with their algorithms."""
        data = await self._request("GET", "/ambilight/supportedstyles")
        if not isinstance(data, dict):
            raise TitanOSError("Invalid Ambilight styles response")
        styles = data.get("supportedStyles", [])
        if not isinstance(styles, list) or not all(isinstance(s, dict) for s in styles):
            raise TitanOSError("Invalid Ambilight styles response")
        return styles

    async def get_ambilight_configuration(self) -> dict[str, Any] | None:
        """Return the active style, or None while Ambilight is off."""
        data = await self._request("GET", "/ambilight/currentconfiguration")
        if data is not None and not isinstance(data, dict):
            raise TitanOSError("Invalid Ambilight configuration")
        return data or None

    async def get_ambilight_processed(self) -> dict[str, Any]:
        """Return the colors the LEDs show, by layer, side and pixel."""
        return await self._request("GET", "/ambilight/processed") or {}

    async def set_ambilight_style(self, style: str, setting: str | None) -> None:
        """Switch Ambilight on with a style and optional algorithm."""
        body: dict[str, Any] = {"styleName": style, "isExpert": False}
        if setting:
            body["menuSetting"] = setting
        await self._request("POST", "/ambilight/currentconfiguration", body)

    async def set_ambilight_color(
        self, hue: int, saturation: int, brightness: int
    ) -> None:
        """Switch Ambilight on with a fixed color, each channel 0-255."""
        await self._request(
            "POST",
            "/ambilight/currentconfiguration",
            {
                "styleName": "FOLLOW_COLOR",
                "isExpert": True,
                "algorithm": "MANUAL_HUE",
                "colorSettings": {
                    "color": {
                        "hue": hue,
                        "saturation": saturation,
                        "brightness": brightness,
                    },
                    "colorDelta": {"hue": 0, "saturation": 0, "brightness": 0},
                    "speed": 255,
                },
            },
        )

    async def get_menu_structure(self) -> dict[str, Any]:
        """Return the root node of the settings menu."""
        data = await self._request("GET", "/menuitems/settings/structure")
        return (data or {}).get("node", {})

    async def get_menu_values(self, node_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Return the current data of settings menu nodes, such as the item
        selected in a list node."""
        data = await self._request(
            "POST",
            "/menuitems/settings/current",
            {"nodes": [{"nodeid": node_id} for node_id in node_ids]},
        )
        return {
            value["value"]["Nodeid"]: value["value"].get("data", {})
            for value in (data or {}).get("values", [])
        }

    async def activate_menu_node(self, node_id: int, item: int | None = None) -> None:
        """Trigger a settings menu node, or select one of its list items.

        Ambilight off works only this way; style OFF and ambilight/power are
        acknowledged but ignored. Unlike ambilight/currentconfiguration, this
        also updates the menu, which the TV restores after standby.
        """
        value: dict[str, Any] = {
            "Nodeid": node_id,
            "nodeid": node_id,
            "node_id": node_id,
        }
        if item is not None:
            value["data"] = {"selected_item": item}
        await self._request(
            "POST", "/menuitems/settings/update", {"values": [{"value": value}]}
        )

    async def get_channel_db(self) -> dict[str, Any]:
        """Return the channel and favorite lists."""
        return await self._request("GET", "/channeldb/tv")

    async def get_channels(self, list_id: str) -> list[dict[str, Any]]:
        """Return the channels of a list."""
        data = await self._request(
            "GET", f"/channeldb/tv/channelLists/{list_id}", request_timeout=60
        )
        return (data or {}).get("Channel", [])

    async def set_channel(self, ccid: int, list_id: str) -> None:
        """Tune to a channel, switching to live TV if needed."""
        await self._request(
            "POST",
            "/activities/tv",
            {"channel": {"ccid": ccid}, "channelList": {"id": list_id}},
        )


class _WakeOnLanProtocol(asyncio.DatagramProtocol):
    pass


async def wake_on_lan(mac: str, broadcast: str = "255.255.255.255") -> None:
    """Send a magic packet."""
    raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(raw) != 6:
        raise ValueError("Invalid MAC address")
    payload = b"\xff" * 6 + raw * 16
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        _WakeOnLanProtocol, remote_addr=(broadcast, 9), allow_broadcast=True
    )
    try:
        transport.sendto(payload)
    finally:
        transport.close()
