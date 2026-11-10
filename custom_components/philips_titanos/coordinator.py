# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Coordinator for the Philips Titan OS TV integration."""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ApiError,
    InvalidAuth,
    SystemInfo,
    TitanOSClient,
    TitanOSError,
    find_menu_node,
    wake_on_lan,
)
from .const import DOMAIN
from .dial import DialClient
from .power import PowerEvidence, PowerState
from .settings import option_enabled

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)
# The TV lists no settings for FOLLOW_VIDEO; these are the ones its menu sets.
# Its "AI" style also reads as NATURAL.
VIDEO_SETTINGS = ["STANDARD", "SPORTS", "NATURAL", "GAME"]

# Menu list items by string ID, and the style each sets.
MENU_STYLES = {
    "MLM_PHM_KEY_MAIN_AMBILIGHT_STYLE_VIDEO_1_2K20": ("FOLLOW_VIDEO", "STANDARD"),
    "MLM_PHM_KEY_MAIN_AMBILIGHT_STYLE_VIDEO_3_2K20": ("FOLLOW_VIDEO", "SPORTS"),
    "MLM_PHM_KEY_MAIN_AMBILIGHT_CINEMA": ("FOLLOW_VIDEO", "NATURAL"),
    "MLM_PHM_KEY_MAIN_AMBILIGHT_GAME_2K23": ("FOLLOW_VIDEO", "GAME"),
    "MLM_PHM_KEY_MAIN_AMBILIGHT_STYLE_AUDIO_1_2K20": (
        "FOLLOW_AUDIO",
        "ENERGY_ADAPTIVE_BRIGHTNESS",
    ),
    "MLM_PHM_KEY_MAIN_FOLLOW_AUDIO_STYLE_3_2K23": ("FOLLOW_AUDIO", "PARTY"),
    "MLM_PHM_KEY_MAIN_AMBILIGHT_STYLE_AUDIO_3_2K20": (
        "FOLLOW_AUDIO",
        "RANDOM_PIXEL_FLASH",
    ),
}


@dataclass(frozen=True, slots=True)
class TitanOSData:
    """State of the TV."""

    is_on: bool | None
    activity: str | None
    muted: bool | None = None
    ambilight: dict[str, Any] | None = None
    ambilight_rgb: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class AmbilightStyle:
    """An Ambilight style with one of its settings."""

    style: str
    setting: str

    @property
    def effect(self) -> str:
        """Return the effect name used in Home Assistant."""
        prefix = "video" if self.style == "FOLLOW_VIDEO" else "audio"
        return f"{prefix}_{self.setting.lower()}"


@dataclass(frozen=True, slots=True)
class Channel:
    """A channel the TV can tune to."""

    ccid: int
    name: str
    list_id: str


type TitanOSConfigEntry = ConfigEntry[TitanOSCoordinator]


def _average_rgb(pixels: dict[str, Any]) -> tuple[int, int, int] | None:
    """Return the mean color over all LEDs."""
    colors = [
        (pixel["r"], pixel["g"], pixel["b"])
        for layer in pixels.values()
        for side in layer.values()
        for pixel in side.values()
    ]
    if not colors:
        return None
    return tuple(round(sum(c[i] for c in colors) / len(colors)) for i in range(3))


class TitanOSCoordinator(DataUpdateCoordinator[TitanOSData]):
    """Poll power and activity of the TV."""

    config_entry: TitanOSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TitanOSConfigEntry,
        client: TitanOSClient,
        system: SystemInfo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.system = system
        self.channels: list[Channel] = []
        self.last_channel: Channel | None = None
        self.ambilight_styles: list[AmbilightStyle] = []
        self.ambilight_off_node: int | None = None
        # Menu node and list item for each style that has one.
        self.ambilight_menu: dict[AmbilightStyle, tuple[int, int]] = {}
        self._ambilight_style_node: int | None = None
        self.has_ambilight = bool(
            system.featuring.get("jsonfeatures", {}).get("ambilight")
        )
        self.has_ambilight = self.has_ambilight and bool(
            option_enabled(entry.options, "enable_ambilight")
        )
        self.dial: DialClient | None = None
        self.dial_apps: list[str] = []
        self._next_dial_discovery = 0.0
        self.power = PowerEvidence()
        self._power_lock = asyncio.Lock()
        self.last_success: str | None = None
        self.last_error: str | None = None
        self.failures = 0
        self.optional_unavailable: set[str] = set()

    async def _async_setup(self) -> None:
        """Discover DIAL registrations only when opted in; never launch on startup."""
        if option_enabled(self.config_entry.options, "enable_dial") and self.dial:
            self.dial_apps = await self.dial.discover()
            self._next_dial_discovery = time.monotonic() + 300

    async def async_command(self, command: Awaitable[Any]) -> None:
        """Run a command and report its failure to the user."""
        try:
            await command
        except (TitanOSError, OSError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    def ensure_controls_enabled(self) -> None:
        """Honor the explicit production control opt-out in every entry point."""
        if not option_enabled(self.config_entry.options, "enable_controls"):
            raise ServiceValidationError(
                "Remote and media controls are disabled in options"
            )

    async def async_turn_on(self) -> None:
        """Serialize WOL and standby intent."""
        self.ensure_controls_enabled()
        async with self._power_lock:
            await self._async_turn_on_locked()

    async def _async_turn_on_locked(self) -> None:
        """Wake the TV."""
        if not (mac := self.config_entry.data.get(CONF_MAC)):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_mac"
            )
        if not option_enabled(self.config_entry.options, "enable_wol"):
            raise ServiceValidationError("Wake-on-LAN is disabled in options")
        if (
            self.power.state == PowerState.WAKING
            and time.monotonic() < self.power.pending_until
        ):
            return
        await self.async_command(
            wake_on_lan(
                mac, self.config_entry.options.get("broadcast", "255.255.255.255")
            )
        )
        self.power.requested(True)
        self.async_set_updated_data(replace(self.data, is_on=None))

    async def async_turn_off(self) -> None:
        """Serialize concurrent power requests before probing or toggling."""
        self.ensure_controls_enabled()
        async with self._power_lock:
            await self._async_turn_off_locked()

    async def _async_turn_off_locked(self) -> None:
        """Put the TV into standby."""
        # Standby is the remote's power key and may wake a TV in standby.
        if self.power.is_on is False:
            return
        if self.power.uncertain_standby_sent:
            raise HomeAssistantError(
                "Standby already sent without confirmation; use the physical remote "
                "or reload after checking the screen before retrying"
            )
        # Probe the authenticated API, not Cast. Connectivity is not screen state.
        await self.async_command(self.client.get_current_activity())
        # Latch before writing: a timeout may mean the toggle was executed.
        self.power.requested(False)
        try:
            await self.async_command(self.client.send_key("Standby"))
        finally:
            self.async_set_updated_data(replace(self.data, is_on=None))

    async def _optional(self, name: str, call: Any, default: Any = None) -> Any:
        """Cache unsupported endpoints until reload, without hiding auth failures."""
        if name in self.optional_unavailable:
            return default
        try:
            return await call()
        except ApiError as err:
            if err.status not in (403, 404, 405, 501):
                raise
            self.optional_unavailable.add(name)
            return default

    async def _async_update_data(self) -> TitanOSData:
        """Poll authenticated reachability, never infer power from Cast or HTTP 200."""
        try:
            activity = await self.client.get_current_activity()
            if (
                option_enabled(self.config_entry.options, "enable_dial")
                and self.dial
                and time.monotonic() >= self._next_dial_discovery
            ):
                self.dial_apps = await self.dial.discover()
                self._next_dial_discovery = time.monotonic() + 300
            observed = None
            if option_enabled(self.config_entry.options, "trust_powerstate"):
                observed = await self._optional(
                    "powerstate", self.client.get_power_state
                )
            self.power.observe(observed)
            muted = None
            if option_enabled(self.config_entry.options, "trust_mute_state"):
                muted = await self._optional("mute", self.client.is_muted)
            # No channel database dumps on startup: firmware can wedge under load.
            ambilight = rgb = None
            if self.has_ambilight:
                if (
                    not self.ambilight_styles
                    and "ambilight_styles" not in self.optional_unavailable
                ):
                    await self._optional(
                        "ambilight_styles", self._async_fetch_ambilight
                    )
                if not self.ambilight_styles:
                    self.has_ambilight = False
                ambilight = await self._optional(
                    "ambilight", self.client.get_ambilight_configuration
                )
                if "ambilight" in self.optional_unavailable:
                    self.has_ambilight = False
                if ambilight and ambilight.get("styleName") == "FOLLOW_COLOR":
                    pixels = await self._optional(
                        "ambilight_processed", self.client.get_ambilight_processed, {}
                    )
                    rgb = _average_rgb(pixels)
        except InvalidAuth as err:
            self.last_error = "authentication_failed"
            raise ConfigEntryAuthFailed from err
        except (
            TitanOSError,
            TimeoutError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as err:
            self.failures += 1
            self.last_error = type(err).__name__
            self.update_interval = timedelta(
                seconds=min(300, 30 * 2 ** min(self.failures, 4))
            )
            self.power.disconnected()
            raise UpdateFailed(self.last_error) from err
        self.failures = 0
        self.last_error = None
        self.last_success = datetime.now(UTC).isoformat()
        self.update_interval = UPDATE_INTERVAL
        return TitanOSData(
            is_on=self.power.is_on,
            activity=activity if self.power.is_on is True else None,
            muted=muted,
            ambilight=ambilight,
            ambilight_rgb=rgb,
        )

    async def _async_fetch_channels(self) -> list[Channel]:
        db: dict[str, Any] = await self.client.get_channel_db() or {}
        channels: list[Channel] = []
        for channel_list in db.get("channelLists", []):
            list_id = channel_list["id"]
            channels.extend(
                Channel(ccid=int(c["ccid"]), name=c["name"], list_id=list_id)
                for c in await self.client.get_channels(list_id)
            )
        return channels

    async def _async_fetch_ambilight(self) -> None:
        styles = await self.client.get_ambilight_styles()
        settings = {s["styleName"]: s.get("algorithms", []) for s in styles}
        result = []
        if "FOLLOW_VIDEO" in settings:
            result += [AmbilightStyle("FOLLOW_VIDEO", s) for s in VIDEO_SETTINGS]
        result += [
            AmbilightStyle("FOLLOW_AUDIO", s) for s in settings.get("FOLLOW_AUDIO", [])
        ]
        self.ambilight_styles = result
        menu = await self.client.get_menu_structure()
        if off := find_menu_node(menu, "ambilight_off"):
            self.ambilight_off_node = off["node_id"]
        if style_node := find_menu_node(menu, "ambilight_style"):
            self._ambilight_style_node = style_node["node_id"]
        for context in ("ambilight_follow_video", "ambilight_follow_audio"):
            if not (node := find_menu_node(menu, context)):
                continue
            for item in node.get("data", {}).get("enums", []):
                if style := MENU_STYLES.get(item.get("string_id")):
                    self.ambilight_menu[AmbilightStyle(*style)] = (
                        node["node_id"],
                        item["enum_id"],
                    )
