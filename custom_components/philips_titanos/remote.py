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


MAX_REPEATS = 10
MAX_DELAY_SECS = 2.0

_KEYS = (
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
_KEYS_BY_NAME = {name.casefold(): name for name in _KEYS}
_ALIASES = {
    "up": "CursorUp",
    "down": "CursorDown",
    "left": "CursorLeft",
    "right": "CursorRight",
    "ok": "Confirm",
    "back": "Back",
    "home": "Home",
}


def _resolve_key(name: str) -> str:
    """Return the JointSpace key for a name or alias, case-insensitively."""
    folded = name.casefold()
    if folded in _ALIASES:
        return _ALIASES[folded]
    if folded in _KEYS_BY_NAME:
        return _KEYS_BY_NAME[folded]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_key",
        translation_placeholders={"key": name},
    )


class TitanOSRemote(TitanOSEntity, RemoteEntity):
    """The TV's remote control keys."""

    _attr_name = None

    def __init__(self, coordinator: TitanOSCoordinator) -> None:
        """Initialize the remote."""
        super().__init__(coordinator, "remote")

    def _require_remote_enabled(self) -> None:
        """Normal production commands do not require a validation/test flag."""
        self.coordinator.ensure_controls_enabled()

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
        """Send JointSpace key names such as CursorUp or Confirm.

        Everything is validated before the first key is sent, so an unknown
        name cannot leave a partial sequence on the TV.
        """
        self._require_remote_enabled()
        if kwargs.get(ATTR_HOLD_SECS):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="hold_not_supported"
            )
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        if not 1 <= num_repeats <= MAX_REPEATS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_repeats",
                translation_placeholders={"max": str(MAX_REPEATS)},
            )
        if not 0 <= delay_secs <= MAX_DELAY_SECS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_delay",
                translation_placeholders={"max": str(MAX_DELAY_SECS)},
            )
        names = [command] if isinstance(command, str) else list(command)
        keys = [_resolve_key(name) for name in names] * num_repeats
        for index, key in enumerate(keys):
            if index:
                await asyncio.sleep(delay_secs)
            if key == "Standby":
                await self.coordinator.async_turn_off()
            else:
                await self.coordinator.async_command(
                    self.coordinator.client.send_key(key)
                )
