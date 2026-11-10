# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Remote for the Philips Titan OS TV integration."""

import asyncio
from collections.abc import Iterable
from typing import Any, override

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TitanOSConfigEntry, TitanOSCoordinator
from .entity import TitanOSEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TitanOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the remote."""
    async_add_entities([TitanOSRemote(entry.runtime_data)])


class TitanOSRemote(TitanOSEntity, RemoteEntity):
    """The TV's remote control keys."""

    _attr_name = None

    def __init__(self, coordinator: TitanOSCoordinator) -> None:
        """Initialize the remote."""
        super().__init__(coordinator, "remote")

    def _require_remote_enabled(self) -> None:
        """Unverified keys require an explicit user-controlled test mode."""
        options = self.coordinator.config_entry.options
        if not (options.get("keys_verified") or options.get("remote_testing")):
            raise ServiceValidationError(
                "Remote keys are not validated; enable remote testing in options "
                "for an authorized hardware test"
            )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the TV is on."""
        return self.coordinator.data.is_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the TV."""
        await self.coordinator.async_turn_on()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the TV into standby."""
        self._require_remote_enabled()
        await self.coordinator.async_turn_off()

    @override
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send JointSpace key names such as CursorUp or Confirm."""
        self._require_remote_enabled()
        if kwargs.get(ATTR_HOLD_SECS):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="hold_not_supported"
            )
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        keys = ([command] if isinstance(command, str) else list(command)) * num_repeats
        aliases = {
            "up": "CursorUp",
            "down": "CursorDown",
            "left": "CursorLeft",
            "right": "CursorRight",
            "ok": "Confirm",
            "back": "Back",
            "home": "Home",
        }
        for index, key in enumerate(keys):
            if index:
                await asyncio.sleep(delay_secs)
            known = {
                name.casefold(): name
                for name in (
                    "Standby",
                    "Home",
                    "Back",
                    "Confirm",
                    "CursorUp",
                    "CursorDown",
                    "CursorLeft",
                    "CursorRight",
                    "VolumeUp",
                    "VolumeDown",
                    "Mute",
                    "Source",
                    "Play",
                    "Pause",
                    "Stop",
                    "FastForward",
                    "Rewind",
                    "ChannelStepUp",
                    "ChannelStepDown",
                    "RedColour",
                    "GreenColour",
                    "YellowColour",
                    "BlueColour",
                    "Info",
                    "Options",
                    "WatchTV",
                    *(f"Digit{i}" for i in range(10)),
                )
            }
            key = aliases.get(key.casefold(), known.get(key.casefold(), key))
            if key not in known.values():
                raise ServiceValidationError("Unknown JointSpace remote key")
            if key == "Standby":
                await self.coordinator.async_turn_off()
            else:
                await self.coordinator.async_command(
                    self.coordinator.client.send_key(key)
                )
