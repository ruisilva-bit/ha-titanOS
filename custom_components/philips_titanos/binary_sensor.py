"""LAN connectivity diagnostic entity."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TitanOSConfigEntry, TitanOSCoordinator
from .entity import TitanOSEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TitanOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose connectivity separately from screen power."""
    async_add_entities([TitanOSConnectivity(entry.runtime_data)])


class TitanOSConnectivity(TitanOSEntity, BinarySensorEntity):
    """Transport status: on means API communication, not a lit screen."""

    _attr_name = "LAN connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TitanOSCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "connection")

    @property
    def available(self) -> bool:
        """Remain available so a failed connection can be reported as off."""
        return True

    @property
    def is_on(self) -> bool:
        """Report the last authenticated poll result."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict:
        """No host, credentials, raw API response or exception messages."""
        return {
            "protocol": "jointspace_v6_https_digest",
            "power_evidence": self.coordinator.power.state.value,
            "last_success": self.coordinator.last_success,
            "last_error": self.coordinator.last_error,
        }
